from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.llm.anchored_word_generation import PreparedAnchoredWordGenerationInput
from course_builder.llm.master_pattern_vocab_generation import (
    PreparedMasterPatternVocabGenerationInput,
    PreparedPatternRun,
    run_master_pattern_vocab_generation,
)
from course_builder.llm.mechanical_word_generation import PreparedMechanicalWordGenerationInput
from course_builder.llm.pattern_vocab_generation.models import PreparedPatternVocabGenerationInput
from course_builder.queries.planning import PlanningQueries
from course_builder.stages.planning.pattern_vocab_generation_support import (
    load_existing_word_prompt_info,
    persist_generated_mechanical_words,
    persist_generated_word_example_sentences,
    persist_generated_words,
    prepare_missing_anchored_lexemes,
    prepare_missing_mechanical_lexemes,
)


@dataclass(frozen=True, slots=True)
class PatternVocabGenerationStats:
    words_created: int
    generated_word_theme_links_created: int


def _prepare_pattern_vocab_generation_input(
    db: Session,
    *,
    context: BuildContext,
    min_words: int,
    max_words: int,
    allowed_pattern_codes: list[str],
) -> PreparedPatternVocabGenerationInput:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = f"Section config must be imported before section word generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)

    return PreparedPatternVocabGenerationInput(
        course_version_id=context.course_version_id,
        min_words=min_words,
        max_words=max_words,
        existing_words=[],
        allowed_pattern_codes=allowed_pattern_codes,
    )


def _prepare_pattern_runs(
    db: Session,
    *,
    context: BuildContext,
) -> list[PreparedPatternRun]:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    batch_size = context.config.generation.words.batch_size
    learned_pattern_codes = q.list_previously_introduced_pattern_codes()
    remaining_mechanical_lexemes = prepare_missing_mechanical_lexemes(db, context=context)
    remaining_anchored_lexemes = prepare_missing_anchored_lexemes(db, context=context)
    prepared_runs: list[PreparedPatternRun] = []

    for pattern in context.config.patterns:
        if pattern.code not in context.config.current_section.patterns_scope:
            continue
        pattern_generation_stage = pattern.min_extra_words is not None or pattern.max_extra_words is not None
        if not pattern_generation_stage:
            learned_pattern_codes.append(pattern.code)
            continue

        current_allowed_pattern_codes = list(dict.fromkeys([*learned_pattern_codes, pattern.code]))
        pattern_mechanical_lexemes = [
            lexeme
            for lexeme in remaining_mechanical_lexemes
            if any(
                (candidate.canonical_writing_ja, candidate.reading_kana, candidate.pos)
                == (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos)
                for example in pattern.examples
                for candidate in example.lexicon_used
            )
        ]
        pattern_anchored_lexemes = [
            lexeme
            for lexeme in remaining_anchored_lexemes
            if any(
                (candidate.canonical_writing_ja, candidate.reading_kana, candidate.pos)
                == (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos)
                for example in pattern.examples
                for candidate in example.lexicon_used
            )
        ]
        prepared_runs.append(
            PreparedPatternRun(
                pattern_code=pattern.code,
                mechanical_batches=[
                    PreparedMechanicalWordGenerationInput(
                        lexemes=pattern_mechanical_lexemes[batch_start : batch_start + batch_size]
                    )
                    for batch_start in range(0, len(pattern_mechanical_lexemes), batch_size)
                ],
                anchored_batches=[
                    PreparedAnchoredWordGenerationInput(
                        targets=pattern_anchored_lexemes[batch_start : batch_start + batch_size],
                        existing_words=[],
                        allowed_pattern_codes=current_allowed_pattern_codes,
                    )
                    for batch_start in range(0, len(pattern_anchored_lexemes), batch_size)
                ],
                lexical_input=(
                    _prepare_pattern_vocab_generation_input(
                        db,
                        context=context,
                        min_words=pattern.min_extra_words or 0,
                        max_words=pattern.max_extra_words or 0,
                        allowed_pattern_codes=current_allowed_pattern_codes,
                    )
                    if (pattern.max_extra_words or 0) > 0
                    else None
                ),
            )
        )
        assigned_mechanical_pairs = {
            (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value) for lexeme in pattern_mechanical_lexemes
        }
        assigned_anchored_pairs = {
            (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value) for lexeme in pattern_anchored_lexemes
        }
        remaining_mechanical_lexemes = [
            lexeme
            for lexeme in remaining_mechanical_lexemes
            if (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value) not in assigned_mechanical_pairs
        ]
        remaining_anchored_lexemes = [
            lexeme
            for lexeme in remaining_anchored_lexemes
            if (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value) not in assigned_anchored_pairs
        ]
        learned_pattern_codes.append(pattern.code)
    return prepared_runs


def generate_pattern_vocab(
    db: Session,
    *,
    context: BuildContext,
) -> PatternVocabGenerationStats:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section_id = q.get_section_id()
    if section_id is None:
        msg = f"Section config must be imported before section word generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    prepared_input = PreparedMasterPatternVocabGenerationInput(
        existing_words=load_existing_word_prompt_info(
            db,
            course_version_id=context.course_version_id,
            section_code=context.section_code,
        ),
        prepared_patterns=_prepare_pattern_runs(db, context=context),
    )
    with asyncio.Runner() as runner:
        generation_result = runner.run(
            run_master_pattern_vocab_generation(
                config=context.config,
                prepared_input=prepared_input,
            )
        )

    mechanical_words_created = 0
    anchored_words_created = 0
    lexical_words_created = 0
    lexical_word_theme_links_created = 0
    for pattern_result in generation_result.pattern_results:
        for mechanical_result in pattern_result.mechanical_results:
            mechanical_words_created += persist_generated_mechanical_words(
                db,
                context=context,
                generated_words_payload=mechanical_result.words,
                source_kind=f"pattern:{pattern_result.pattern_code}",
            )
        for anchored_result in pattern_result.anchored_results:
            persist_generated_words(
                db,
                context=context,
                generated_words_payload=tuple(anchored_result.words),
                source_kind=f"pattern:{pattern_result.pattern_code}",
            )
            persist_generated_word_example_sentences(
                db,
                context=context,
                generated_words_payload=tuple(anchored_result.words),
            )
            anchored_words_created += len(anchored_result.words)
        if pattern_result.lexical_result is None:
            continue
        lexical_word_theme_links_created += persist_generated_words(
            db,
            context=context,
            generated_words_payload=tuple(pattern_result.lexical_result.generated_words),
            assign_all_section_themes=True,
            source_kind=f"pattern:{pattern_result.pattern_code}",
        )
        persist_generated_word_example_sentences(
            db,
            context=context,
            generated_words_payload=tuple(pattern_result.lexical_result.generated_words),
        )
        lexical_words_created += pattern_result.lexical_result.words_created

    return PatternVocabGenerationStats(
        words_created=mechanical_words_created + anchored_words_created + lexical_words_created,
        generated_word_theme_links_created=lexical_word_theme_links_created,
    )


class PatternVocabGenerationStage(BuildStep):
    name = "pattern_vocab_generation"

    @override
    def run(self, *, db: Session, context: BuildContext) -> PatternVocabGenerationStats:
        return generate_pattern_vocab(db, context=context)
