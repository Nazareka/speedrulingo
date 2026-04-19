from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete
from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.queries.planning import GeneratedWordSentenceRow, LessonWithPlan, PlanningQueries
from course_builder.sentence_processing import (
    VocabItem,
    build_japanese_sentence_analysis,
    normalize_sentence_texts,
    tokenize_english_sentence,
)
from course_builder.stages.planning.section_curriculum import list_lessons_with_plan
from domain.content.models import (
    LessonSentence,
    Sentence,
    SentencePatternLink,
    SentenceUnit,
    SentenceWordLink,
)


@dataclass(frozen=True, slots=True)
class PatternExampleSentenceStats:
    sentences_created: int
    lesson_attachments_created: int
    word_links_created: int
    pattern_links_created: int
    sentence_units_created: int


@dataclass(frozen=True, slots=True)
class SentenceAttachmentCandidate:
    earliest_lesson_id: str
    sentence_id: str
    priority: int
    sort_key: str


def _build_example_vocab_items(
    *,
    example_lexicon_used: tuple[tuple[str, str, str], ...],
) -> list[VocabItem]:
    return [
        VocabItem(
            word_id=None,
            canonical_writing_ja=canonical_writing_ja,
            reading_kana=reading_kana,
            gloss_primary_en="",
            gloss_alternatives_en=(),
            usage_note_en=None,
            pos=pos,
        )
        for canonical_writing_ja, reading_kana, pos in example_lexicon_used
    ]


def _sentence_key(
    *,
    ja_text: str,
    en_text: str,
    target_word_id: str | None,
    target_pattern_id: str | None,
) -> tuple[str, str, str | None, str | None]:
    return (ja_text, en_text, target_word_id, target_pattern_id)


def _assign_sentence_candidates(
    *,
    lesson_rows: list[LessonWithPlan],
    generated_sentence_rows: list[GeneratedWordSentenceRow],
    pattern_candidates: list[SentenceAttachmentCandidate],
    max_sentence_items_per_normal_lesson: int,
) -> dict[str, list[str]]:
    lesson_ids = [lesson_with_plan.lesson.id for lesson_with_plan in lesson_rows]
    lesson_order_by_id = {lesson_id: index for index, lesson_id in enumerate(lesson_ids)}
    lesson_row_by_id = {lesson_with_plan.lesson.id: lesson_with_plan for lesson_with_plan in lesson_rows}
    assignable_lesson_ids = [
        lesson_with_plan.lesson.id
        for lesson_with_plan in lesson_rows
        if lesson_with_plan.planned_lesson.lesson_kind != "kanji_activation"
    ]
    assignable_lesson_id_set = set(assignable_lesson_ids)
    intro_lesson_id_by_lemma = {
        lemma: lesson_with_plan.lesson.id
        for lesson_with_plan in lesson_rows
        for lemma in lesson_with_plan.planned_lesson.introduced_word_lemmas
    }
    sentence_capacity_by_lesson_id = {
        lesson_with_plan.lesson.id: max_sentence_items_per_normal_lesson
        for lesson_with_plan in lesson_rows
    }
    candidates = list(pattern_candidates)
    for generated_sentence in generated_sentence_rows:
        earliest_lesson_id = intro_lesson_id_by_lemma.get(generated_sentence.canonical_writing_ja)
        if earliest_lesson_id is None:
            continue
        candidates.append(
            SentenceAttachmentCandidate(
                earliest_lesson_id=earliest_lesson_id,
                sentence_id=generated_sentence.sentence_id,
                priority=1,
                sort_key=f"{generated_sentence.canonical_writing_ja}:{generated_sentence.sentence_id}",
            )
        )

    assigned_sentence_ids_by_lesson_id: dict[str, list[str]] = {lesson_id: [] for lesson_id in lesson_ids}
    assigned_keys: set[tuple[str, str]] = set()
    for candidate in sorted(
        candidates,
        key=lambda item: (lesson_order_by_id[item.earliest_lesson_id], item.priority, item.sort_key),
    ):
        assigned = False
        start_index = lesson_order_by_id[candidate.earliest_lesson_id]
        fallback_lesson_id: str | None = None
        for lesson_id in lesson_ids[start_index:]:
            if lesson_id not in assignable_lesson_id_set:
                continue
            fallback_lesson_id = lesson_id
            assignment_key = (lesson_id, candidate.sentence_id)
            if assignment_key in assigned_keys:
                assigned = True
                break
            if len(assigned_sentence_ids_by_lesson_id[lesson_id]) >= sentence_capacity_by_lesson_id[lesson_id]:
                continue
            assigned_sentence_ids_by_lesson_id[lesson_id].append(candidate.sentence_id)
            assigned_keys.add(assignment_key)
            assigned = True
            break
        if not assigned and fallback_lesson_id is not None:
            assignment_key = (fallback_lesson_id, candidate.sentence_id)
            if assignment_key not in assigned_keys:
                assigned_sentence_ids_by_lesson_id[fallback_lesson_id].append(candidate.sentence_id)
                assigned_keys.add(assignment_key)
            assigned = True
        if not assigned:
            earliest_lesson = lesson_row_by_id[candidate.earliest_lesson_id]
            msg = (
                "Could not assign section sentence within bounded lesson capacity: "
                f"sentence_id={candidate.sentence_id} earliest_lesson_id={candidate.earliest_lesson_id}"
                f" earliest_lesson_kind={earliest_lesson.planned_lesson.lesson_kind}"
            )
            raise ValueError(msg)
    return assigned_sentence_ids_by_lesson_id


def persist_pattern_example_sentences(
    db: Session,
    *,
    context: BuildContext,
) -> PatternExampleSentenceStats:
    q = PlanningQueries(db, context.course_version_id, context.section_code)
    lesson_rows = list_lessons_with_plan(context=context, q=q)
    lesson_ids = [lesson_with_plan.lesson.id for lesson_with_plan in lesson_rows]
    if not lesson_ids:
        return PatternExampleSentenceStats(0, 0, 0, 0, 0)

    word_id_by_form = q.map_word_id_by_form()
    pattern_id_by_code = q.map_pattern_id_by_code()
    existing_sentence_data = q.load_existing_course_sentence_data()
    sentence_cache = existing_sentence_data.sentences_by_key
    sentence_word_link_keys = existing_sentence_data.sentence_word_link_keys
    sentence_pattern_link_keys = existing_sentence_data.sentence_pattern_link_keys
    sentence_unit_keys = existing_sentence_data.sentence_unit_keys
    if q.list_lesson_sentence_keys(lesson_ids=lesson_ids):
        msg = "Configured pattern example sentence is duplicated within the same lesson"
        raise ValueError(msg)

    sentences_created = 0
    word_links_created = 0
    pattern_links_created = 0
    sentence_units_created = 0
    pattern_candidates: list[SentenceAttachmentCandidate] = []
    seen_pattern_candidate_keys: set[tuple[str, str]] = set()

    for lesson_with_plan in lesson_rows:
        for example in lesson_with_plan.planned_lesson.target_pattern_examples:
            target_pattern_id = pattern_id_by_code.get(example.pattern_code)
            if target_pattern_id is None:
                continue
            normalized_ja_text, normalized_en_text = normalize_sentence_texts(
                ja_text=example.ja_text,
                en_text=example.en_text,
            )
            current_sentence_key = _sentence_key(
                ja_text=normalized_ja_text,
                en_text=normalized_en_text,
                target_word_id=None,
                target_pattern_id=target_pattern_id,
            )
            sentence_row = sentence_cache.get(current_sentence_key)
            if sentence_row is None:
                sentence_row = Sentence(
                    course_version_id=context.course_version_id,
                    ja_text=normalized_ja_text,
                    en_text=normalized_en_text,
                    target_word_id=None,
                    target_pattern_id=target_pattern_id,
                    source_kind="config_example",
                    generation_pipeline=None,
                )
                db.add(sentence_row)
                db.flush()
                sentence_cache[current_sentence_key] = sentence_row
                sentences_created += 1

            pattern_link_key = (sentence_row.id, target_pattern_id)
            if pattern_link_key not in sentence_pattern_link_keys:
                db.add(
                    SentencePatternLink(
                        sentence_id=sentence_row.id,
                        pattern_id=target_pattern_id,
                        role="target",
                    )
                )
                sentence_pattern_link_keys.add(pattern_link_key)
                pattern_links_created += 1

            for canonical_writing_ja, reading_kana, _pos in example.lexicon_used:
                word_id = word_id_by_form.get((canonical_writing_ja, reading_kana))
                if word_id is None:
                    continue
                link_key = (sentence_row.id, word_id)
                if link_key in sentence_word_link_keys:
                    continue
                db.add(
                    SentenceWordLink(
                        sentence_id=sentence_row.id,
                        word_id=word_id,
                        role="support",
                    )
                )
                sentence_word_link_keys.add(link_key)
                word_links_created += 1

            japanese_analysis = build_japanese_sentence_analysis(
                sentence_ja=normalized_ja_text,
                vocab=_build_example_vocab_items(example_lexicon_used=example.lexicon_used),
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
                sentence_units_created += 1
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
                sentence_units_created += 1
            pattern_candidates.append(
                SentenceAttachmentCandidate(
                    earliest_lesson_id=lesson_with_plan.lesson.id,
                    sentence_id=sentence_row.id,
                    priority=0,
                    sort_key=f"{example.pattern_code}:{normalized_ja_text}",
                )
            )
            pattern_candidate_key = (lesson_with_plan.lesson.id, sentence_row.id)
            if pattern_candidate_key in seen_pattern_candidate_keys:
                msg = (
                    "Configured pattern example sentence is duplicated within the same lesson: "
                    f"lesson_id={lesson_with_plan.lesson.id} "
                    f"ja_text={normalized_ja_text!r} "
                    f"en_text={normalized_en_text!r}"
                )
                raise ValueError(msg)
            seen_pattern_candidate_keys.add(pattern_candidate_key)

    assigned_sentence_ids_by_lesson_id = _assign_sentence_candidates(
        lesson_rows=lesson_rows,
        generated_sentence_rows=q.list_generated_word_sentences_for_section(),
        pattern_candidates=pattern_candidates,
        max_sentence_items_per_normal_lesson=context.config.current_section.section_planning.max_sentence_introductions_per_normal_lesson,
    )

    db.execute(delete(LessonSentence).where(LessonSentence.lesson_id.in_(lesson_ids)))
    lesson_attachments_created = 0
    for lesson_with_plan in lesson_rows:
        for order_index, sentence_id in enumerate(assigned_sentence_ids_by_lesson_id[lesson_with_plan.lesson.id], start=1):
            db.add(
                LessonSentence(
                    lesson_id=lesson_with_plan.lesson.id,
                    sentence_id=sentence_id,
                    order_index=order_index,
                    role="core",
                )
            )
            lesson_attachments_created += 1

    db.commit()
    return PatternExampleSentenceStats(
        sentences_created=sentences_created,
        lesson_attachments_created=lesson_attachments_created,
        word_links_created=word_links_created,
        pattern_links_created=pattern_links_created,
        sentence_units_created=sentence_units_created,
    )
