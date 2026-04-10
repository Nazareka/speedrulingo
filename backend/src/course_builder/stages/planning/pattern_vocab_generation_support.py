from __future__ import annotations

from sqlalchemy.orm import Session

from course_builder.config import AnchorWordRefConfig
from course_builder.lexicon import LexemePos
from course_builder.llm.anchored_word_generation.json_schema import AnchoredWordPayload
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.mechanical_word_generation import MechanicalLexemePromptInfo
from course_builder.llm.mechanical_word_generation.json_schema import MechanicalWordPayload
from course_builder.llm.pattern_vocab_generation.json_schema import WordBatchItemPayload
from course_builder.queries.planning import PlanningQueries
from course_builder.runtime.models import BuildContext
from course_builder.sentence_processing import (
    VocabItem,
    build_japanese_sentence_analysis,
    normalize_sentence_texts,
    tokenize_english_sentence,
)
from domain.content.models import (
    SectionWord,
    Sentence,
    SentenceUnit,
    SentenceWordLink,
    Word,
    WordThemeLink,
)


def build_vocab_items_from_word_rows(
    word_rows: list[tuple[str, str, str, str, str, tuple[str, ...], str | None]],
) -> list[VocabItem]:
    return [
        VocabItem(
            word_id=word_id,
            canonical_writing_ja=canonical_writing_ja,
            reading_kana=reading_kana,
            gloss_primary_en=gloss_primary_en,
            gloss_alternatives_en=gloss_alternatives_en,
            usage_note_en=usage_note_en,
            pos=pos,
        )
        for word_id, canonical_writing_ja, reading_kana, pos, gloss_primary_en, gloss_alternatives_en, usage_note_en in word_rows
    ]


def iter_pattern_example_lexemes(*, context: BuildContext) -> list[AnchorWordRefConfig]:
    scoped_codes = set(context.config.current_section.patterns_scope)
    lexemes: list[AnchorWordRefConfig] = []
    for pattern in context.config.patterns:
        if pattern.code not in scoped_codes:
            continue
        for example in pattern.examples:
            lexemes.extend(example.lexicon_used)
    return lexemes


def prepare_missing_mechanical_lexemes(
    db: Session,
    *,
    context: BuildContext,
) -> list[MechanicalLexemePromptInfo]:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    existing_pairs = q.list_existing_word_pos_triplets()
    seen_pairs: set[tuple[str, str, str]] = set()
    missing_lexemes: list[MechanicalLexemePromptInfo] = []
    for lexeme in iter_pattern_example_lexemes(context=context):
        if not LexemePos.is_mechanical(lexeme.pos):
            continue
        pair = (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value)
        if pair in existing_pairs or pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        missing_lexemes.append(
            MechanicalLexemePromptInfo(
                canonical_writing_ja=lexeme.canonical_writing_ja,
                reading_kana=lexeme.reading_kana,
                pos=lexeme.pos,
            )
        )
    return missing_lexemes


def prepare_missing_anchored_lexemes(
    db: Session,
    *,
    context: BuildContext,
) -> list[AnchorWordRefConfig]:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    existing_pairs = q.list_existing_word_pos_triplets()
    seen_pairs: set[tuple[str, str, str]] = set()
    missing_lexemes: list[AnchorWordRefConfig] = []
    for lexeme in iter_pattern_example_lexemes(context=context):
        if LexemePos.is_mechanical(lexeme.pos):
            continue
        pair = (lexeme.canonical_writing_ja, lexeme.reading_kana, lexeme.pos.value)
        if pair in existing_pairs or pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        missing_lexemes.append(lexeme)
    return missing_lexemes


def persist_generated_mechanical_words(
    db: Session,
    *,
    context: BuildContext,
    generated_words_payload: list[MechanicalWordPayload],
    source_kind: str = "llm",
) -> int:
    if not generated_words_payload:
        return 0
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section_id = q.get_section_id()
    if section_id is None:
        msg = f"Section config must be imported before section word generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    existing_pairs = q.list_existing_word_pairs()
    next_intro_order = q.get_next_word_intro_order()
    words_created = 0
    for candidate in generated_words_payload:
        pair = (candidate.canonical_writing_ja, candidate.reading_kana)
        if pair in existing_pairs:
            continue
        word = Word(
            course_version_id=context.course_version_id,
            intro_order=next_intro_order,
            canonical_writing_ja=candidate.canonical_writing_ja,
            reading_kana=candidate.reading_kana,
            gloss_primary_en=candidate.gloss_primary_en,
            gloss_alternatives_en=candidate.gloss_alternatives_en,
            usage_note_en=candidate.usage_note_en,
            pos=candidate.pos.value,
            is_safe_pool=False,
            is_bootstrap_seed=False,
            source_kind=source_kind,
        )
        db.add(word)
        db.flush()
        db.add(SectionWord(section_id=section_id, word_id=word.id, role="new"))
        existing_pairs.add(pair)
        next_intro_order += 1
        words_created += 1
    db.flush()
    return words_created


def persist_generated_words(
    db: Session,
    *,
    context: BuildContext,
    generated_words_payload: tuple[AnchoredWordPayload | WordBatchItemPayload, ...],
    assign_all_section_themes: bool = False,
    source_kind: str = "llm",
) -> int:
    if not generated_words_payload:
        return 0

    q = PlanningQueries(db, context.course_version_id, context.section_code)
    section_id = q.get_section_id()
    if section_id is None:
        msg = f"Section config must be imported before section word generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    theme_code_to_id = q.map_theme_tag_id_by_code()
    section_theme_codes = list(
        dict.fromkeys(
            [
                *context.config.current_section.primary_themes,
                *context.config.current_section.secondary_themes,
            ]
        )
    )
    section_theme_ids = [
        theme_code_to_id[theme_code] for theme_code in section_theme_codes if theme_code in theme_code_to_id
    ]
    existing_pairs = q.list_existing_word_pairs()
    next_intro_order = q.get_next_word_intro_order()
    created_word_theme_links = 0
    for candidate in generated_words_payload:
        pair = (candidate.canonical_writing_ja, candidate.reading_kana)
        if pair in existing_pairs:
            continue
        word = Word(
            course_version_id=context.course_version_id,
            intro_order=next_intro_order,
            canonical_writing_ja=candidate.canonical_writing_ja,
            reading_kana=candidate.reading_kana,
            gloss_primary_en=candidate.gloss_primary_en,
            gloss_alternatives_en=candidate.gloss_alternatives_en,
            usage_note_en=candidate.usage_note_en,
            pos=candidate.pos.value,
            is_safe_pool=False,
            is_bootstrap_seed=False,
            source_kind=source_kind,
        )
        db.add(word)
        db.flush()
        next_intro_order += 1
        existing_pairs.add(pair)
        db.add(SectionWord(section_id=section_id, word_id=word.id, role="new"))
        theme_tag_ids = section_theme_ids if assign_all_section_themes else []
        for theme_tag_id in theme_tag_ids:
            db.add(WordThemeLink(word_id=word.id, theme_tag_id=theme_tag_id))
            created_word_theme_links += 1
    db.flush()
    return created_word_theme_links


def matched_lexical_word_ids(*, sentence_text: str, lexical_rows: list[tuple[str, str]]) -> list[str]:
    matched_pairs = [
        (canonical_writing_ja, word_id)
        for canonical_writing_ja, word_id in lexical_rows
        if canonical_writing_ja in sentence_text
    ]
    return [
        word_id
        for canonical_writing_ja, word_id in sorted(
            matched_pairs,
            key=lambda item: len(item[0]),
            reverse=True,
        )
    ]


def persist_generated_word_example_sentences(
    db: Session,
    *,
    context: BuildContext,
    generated_words_payload: tuple[AnchoredWordPayload | WordBatchItemPayload, ...],
) -> None:
    if not generated_words_payload:
        return
    q = PlanningQueries(db, context.course_version_id, context.section_code)

    def sentence_key(
        *, ja_text: str, en_text: str, target_word_id: str | None, target_pattern_id: str | None
    ) -> tuple[str, str, str | None, str | None]:
        return (ja_text, en_text, target_word_id, target_pattern_id)

    word_rows = q.list_word_rows_for_sentence_matching()
    lexical_rows = [
        (canonical_writing_ja, word_id)
        for word_id, canonical_writing_ja, _reading_kana, _pos, _gloss_primary_en, _gloss_alternatives_en, _usage_note_en in word_rows
    ]
    tokenization_vocab = build_vocab_items_from_word_rows(word_rows)
    existing_sentence_data = q.load_existing_course_sentence_data()
    sentence_cache = {
        sentence_key(
            ja_text=ja_text,
            en_text=en_text,
            target_word_id=target_word_id,
            target_pattern_id=target_pattern_id,
        ): sentence
        for (
            ja_text,
            en_text,
            target_word_id,
            target_pattern_id,
        ), sentence in existing_sentence_data.sentences_by_key.items()
    }
    sentence_word_link_keys = existing_sentence_data.sentence_word_link_keys
    sentence_unit_keys = existing_sentence_data.sentence_unit_keys

    generated_words = q.list_generated_words_by_canonical_writing(
        canonical_writings=[word.canonical_writing_ja for word in generated_words_payload],
    )
    generated_words_payload_by_lemma = {
        word.canonical_writing_ja: word for word in generated_words_payload
    }
    for generated_word in generated_words:
        batch_word = generated_words_payload_by_lemma[generated_word.canonical_writing_ja]
        for example_sentence in batch_word.example_sentences:
            normalized_ja_text, normalized_en_text = normalize_sentence_texts(
                ja_text=example_sentence.ja_text,
                en_text=example_sentence.en_text,
            )
            current_sentence_key = sentence_key(
                ja_text=normalized_ja_text,
                en_text=normalized_en_text,
                target_word_id=generated_word.id,
                target_pattern_id=None,
            )
            sentence_row = sentence_cache.get(current_sentence_key)
            if sentence_row is None:
                sentence_row = Sentence(
                    course_version_id=context.course_version_id,
                    ja_text=normalized_ja_text,
                    en_text=normalized_en_text,
                    target_word_id=generated_word.id,
                    target_pattern_id=None,
                )
                db.add(sentence_row)
                db.flush()
                sentence_cache[current_sentence_key] = sentence_row

            used_word_ids = {
                generated_word.id,
                *(matched_lexical_word_ids(sentence_text=normalized_ja_text, lexical_rows=lexical_rows)),
            }
            for word_id in used_word_ids:
                sentence_word_key = (sentence_row.id, word_id)
                if sentence_word_key in sentence_word_link_keys:
                    continue
                db.add(
                    SentenceWordLink(
                        sentence_id=sentence_row.id,
                        word_id=word_id,
                        role="target" if word_id == generated_word.id else "support",
                    )
                )
                sentence_word_link_keys.add(sentence_word_key)

            japanese_analysis = build_japanese_sentence_analysis(
                sentence_ja=normalized_ja_text,
                vocab=tokenization_vocab,
            )
            for unit_index, chunk in enumerate(japanese_analysis.chunks):
                unit_key = (sentence_row.id, "ja", unit_index)
                if unit_key in sentence_unit_keys:
                    continue
                db.add(
                    SentenceUnit(
                        sentence_id=sentence_row.id,
                        lang="ja",
                        unit_index=unit_index,
                        surface=chunk.text,
                        lemma=chunk.lemma,
                        reading=chunk.reading,
                        pos=chunk.pos,
                    )
                )
                sentence_unit_keys.add(unit_key)
            for unit_index, token in enumerate(tokenize_english_sentence(normalized_en_text)):
                unit_key = (sentence_row.id, "en", unit_index)
                if unit_key in sentence_unit_keys:
                    continue
                db.add(
                    SentenceUnit(
                        sentence_id=sentence_row.id,
                        lang="en",
                        unit_index=unit_index,
                        surface=token.surface,
                        lemma=token.lemma,
                        reading=None,
                        pos=token.pos,
                    )
                )
                sentence_unit_keys.add(unit_key)

    db.flush()


def load_existing_word_prompt_info(
    db: Session,
    *,
    course_version_id: str,
    section_code: str,
) -> list[ExistingWordPromptInfo]:
    return PlanningQueries(db, course_version_id, section_code).list_existing_word_prompt_info()
