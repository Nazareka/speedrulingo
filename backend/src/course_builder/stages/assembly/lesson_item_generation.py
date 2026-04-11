from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from core.lexicon import LexemePos, extract_kanji_chars
from course_builder.engine.models import BuildContext
from course_builder.queries.assembly import AssemblyQueries
from course_builder.queries.planning import CurriculumLesson, PlanningQueries
from course_builder.stages.planning.section_curriculum import list_lessons_with_plan
from domain.content.models import (
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Lesson,
    LessonSentence,
    Unit,
    Word,
)


@dataclass(frozen=True, slots=True)
class LessonItemGenerationStats:
    items_created: int
    word_choice_items_created: int
    sentence_tiles_items_created: int
    kanji_kana_match_items_created: int


@dataclass(frozen=True, slots=True)
class ItemGenerationCounters:
    items_created: int = 0
    word_choice_items_created: int = 0
    sentence_tiles_items_created: int = 0
    kanji_kana_match_items_created: int = 0


@dataclass(frozen=True, slots=True)
class PlannedItemSpec:
    item_type: str
    prompt_lang: str
    answer_lang: str
    prompt_script: str | None = None
    answer_script: str | None = None
    word_id: str | None = None
    sentence_id: str | None = None
    tile_set_id: str | None = None
    unit_index: int | None = None
    order_group: int = 0


@dataclass(frozen=True, slots=True)
class NormalLessonBuildResult:
    item_specs: list[PlannedItemSpec]
    overflow_sentence_ids: list[str]


def _merge_counters(*, left: ItemGenerationCounters, right: ItemGenerationCounters) -> ItemGenerationCounters:
    return ItemGenerationCounters(
        items_created=left.items_created + right.items_created,
        word_choice_items_created=left.word_choice_items_created + right.word_choice_items_created,
        sentence_tiles_items_created=left.sentence_tiles_items_created + right.sentence_tiles_items_created,
        kanji_kana_match_items_created=left.kanji_kana_match_items_created + right.kanji_kana_match_items_created,
    )


def _add_word_choice_item(
    db: Session,
    *,
    lesson_id: str,
    order_index: int,
    prompt_lang: str,
    answer_lang: str,
    word_id: str,
) -> None:
    item = Item(
        lesson_id=lesson_id,
        order_index=order_index,
        type="word_choice",
        prompt_lang=prompt_lang,
        answer_lang=answer_lang,
    )
    db.add(item)
    db.flush()
    db.add(ItemWordChoice(item_id=item.id, word_id=word_id))


def _add_sentence_tiles_item(
    db: Session,
    *,
    lesson_id: str,
    order_index: int,
    prompt_lang: str,
    answer_lang: str,
    sentence_id: str,
    tile_set_id: str,
) -> None:
    item = Item(
        lesson_id=lesson_id,
        order_index=order_index,
        type="sentence_tiles",
        prompt_lang=prompt_lang,
        answer_lang=answer_lang,
    )
    db.add(item)
    db.flush()
    db.add(ItemSentenceTiles(item_id=item.id, sentence_id=sentence_id, tile_set_id=tile_set_id))


def _add_kanji_kana_match_item(
    db: Session,
    *,
    lesson_id: str,
    order_index: int,
    word_id: str,
    prompt_script: str,
    answer_script: str,
) -> None:
    item = Item(
        lesson_id=lesson_id,
        order_index=order_index,
        type="kanji_kana_match",
        prompt_lang="ja",
        answer_lang="ja",
    )
    db.add(item)
    db.flush()
    db.add(
        ItemKanjiKanaMatch(
            item_id=item.id,
            word_id=word_id,
            prompt_script=prompt_script,
            answer_script=answer_script,
        )
    )


def _delete_existing_section_items(db: Session, *, section_id: str) -> None:
    lesson_ids = list(
        db.scalars(select(Lesson.id).join(Unit, Unit.id == Lesson.unit_id).where(Unit.section_id == section_id))
    )
    if not lesson_ids:
        return
    item_ids = list(db.scalars(select(Item.id).where(Item.lesson_id.in_(lesson_ids))))
    if item_ids:
        db.execute(delete(ItemWordChoice).where(ItemWordChoice.item_id.in_(item_ids)))
        db.execute(delete(ItemSentenceTiles).where(ItemSentenceTiles.item_id.in_(item_ids)))
        db.execute(delete(ItemKanjiKanaMatch).where(ItemKanjiKanaMatch.item_id.in_(item_ids)))
    db.execute(delete(Item).where(Item.lesson_id.in_(lesson_ids)))


def _is_kanji_intro_candidate(*, word: Word) -> bool:
    return (
        word.pos != "verb"
        and bool(extract_kanji_chars(word.canonical_writing_ja))
        and word.reading_kana != word.canonical_writing_ja
    )


def _ordered_unique_ids(*, values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _spread_duplicate_word_choice_specs(*, item_specs: list[PlannedItemSpec]) -> list[PlannedItemSpec]:
    remaining_specs = list(item_specs)
    ordered_specs: list[PlannedItemSpec] = []
    while remaining_specs:
        previous_word_id = ordered_specs[-1].word_id if ordered_specs else None
        next_index = next(
            (
                index
                for index, item_spec in enumerate(remaining_specs)
                if item_spec.item_type != "word_choice" or item_spec.word_id != previous_word_id
            ),
            0,
        )
        ordered_specs.append(remaining_specs.pop(next_index))
    return ordered_specs


def _shuffle_item_specs(*, lesson_id: str, item_specs: list[PlannedItemSpec]) -> list[PlannedItemSpec]:
    item_specs_by_group: dict[int, list[PlannedItemSpec]] = {}
    for item_spec in item_specs:
        item_specs_by_group.setdefault(item_spec.order_group, []).append(item_spec)

    ordered_item_specs: list[PlannedItemSpec] = []
    for order_group in sorted(item_specs_by_group):
        group_specs = list(item_specs_by_group[order_group])
        shuffled_group_specs = sorted(
            group_specs,
            key=lambda item_spec: sha256(
                (
                    f"{lesson_id}:{order_group}:{item_spec.item_type}:{item_spec.word_id or ''}:"
                    f"{item_spec.sentence_id or ''}:{item_spec.unit_index or ''}"
                ).encode()
            ).hexdigest(),
        )
        ordered_item_specs.extend(_spread_duplicate_word_choice_specs(item_specs=shuffled_group_specs))
    return ordered_item_specs


def _build_normal_lesson_item_specs(
    *,
    lesson: Lesson,
    planned_lesson: CurriculumLesson,
    previously_introduced_word_ids: set[str],
    sentence_ids: list[str],
    lesson_words: list[Word],
    sentence_word_ids_by_sentence_id: dict[str, set[str]],
    en_tile_sets: dict[str, str],
    ja_tile_sets: dict[str, str],
) -> NormalLessonBuildResult:
    if planned_lesson.lesson_kind == "kanji_activation":
        lesson_words_by_lemma = {word.canonical_writing_ja: word for word in lesson_words}
        activation_item_specs: list[PlannedItemSpec] = []
        for lemma in planned_lesson.kanji_focus_word_lemmas:
            if lemma not in lesson_words_by_lemma:
                continue
            word_id = lesson_words_by_lemma[lemma].id
            activation_item_specs.append(
                PlannedItemSpec(
                    item_type="kanji_kana_match",
                    prompt_lang="ja",
                    answer_lang="ja",
                    prompt_script="kana",
                    answer_script="kanji",
                    word_id=word_id,
                    order_group=0,
                )
            )
            activation_item_specs.append(
                PlannedItemSpec(
                    item_type="word_choice",
                    prompt_lang="ja",
                    answer_lang="en",
                    word_id=word_id,
                    order_group=1,
                )
            )
        return NormalLessonBuildResult(
            item_specs=_shuffle_item_specs(lesson_id=lesson.id, item_specs=activation_item_specs),
            overflow_sentence_ids=[],
        )

    lesson_words_by_id = {word.id: word for word in lesson_words}
    introduced_word_lemmas = set(planned_lesson.introduced_word_lemmas)
    target_word_ids = [
        word.id
        for word in lesson_words
        if word.canonical_writing_ja in introduced_word_lemmas
        and word.id not in previously_introduced_word_ids
    ]
    kanji_kana_word_ids = [
        word_id
        for word_id in target_word_ids
        if not planned_lesson.force_kana_display
        and word_id in lesson_words_by_id
        and _is_kanji_intro_candidate(word=lesson_words_by_id[word_id])
    ]
    word_choice_intro_id_set = set(target_word_ids)
    unavailable_teachable_word_ids = {
        word.id
        for word in lesson_words
        if not LexemePos.is_support(word.pos)
        and word.id not in previously_introduced_word_ids
        and word.id not in word_choice_intro_id_set
    }
    eligible_sentence_ids = [
        sentence_id
        for sentence_id in sentence_ids
        if not sentence_word_ids_by_sentence_id.get(sentence_id, set()).intersection(unavailable_teachable_word_ids)
    ]
    sentence_tile_ids = list(eligible_sentence_ids)
    eligible_sentence_id_set = set(eligible_sentence_ids)
    overflow_sentence_ids = [sentence_id for sentence_id in sentence_ids if sentence_id not in eligible_sentence_id_set]

    item_specs: list[PlannedItemSpec] = [
        PlannedItemSpec(
            item_type="kanji_kana_match",
            prompt_lang="ja",
            answer_lang="ja",
            prompt_script="kana",
            answer_script="kanji",
            word_id=word_id,
            order_group=0,
        )
        for word_id in kanji_kana_word_ids
    ]
    item_specs.extend(
        PlannedItemSpec(
            item_type="word_choice",
            prompt_lang="ja",
            answer_lang="en",
            word_id=word_id,
            order_group=1,
        )
        for word_id in target_word_ids
    )
    item_specs.extend(
        PlannedItemSpec(
            item_type="sentence_tiles",
            prompt_lang="ja",
            answer_lang="en",
            sentence_id=sentence_id,
            tile_set_id=en_tile_sets[sentence_id],
            order_group=2,
        )
        for sentence_id in sentence_tile_ids
        if sentence_id in en_tile_sets
    )
    item_specs.extend(
        PlannedItemSpec(
            item_type="sentence_tiles",
            prompt_lang="en",
            answer_lang="ja",
            sentence_id=sentence_id,
            tile_set_id=ja_tile_sets[sentence_id],
            order_group=2,
        )
        for sentence_id in sentence_tile_ids
        if sentence_id in ja_tile_sets
    )
    return NormalLessonBuildResult(
        item_specs=_shuffle_item_specs(lesson_id=lesson.id, item_specs=item_specs),
        overflow_sentence_ids=overflow_sentence_ids,
    )


def _build_review_exam_item_specs(
    *,
    lesson: Lesson,
    word_ids: list[str],
    sentence_ids: list[str],
    sentence_item_count: int,
    review_item_count: int,
    en_tile_sets: dict[str, str],
) -> list[PlannedItemSpec]:
    item_specs = [
        PlannedItemSpec(
            item_type="sentence_tiles",
            prompt_lang="ja",
            answer_lang="en",
            sentence_id=sentence_id,
            tile_set_id=en_tile_sets[sentence_id],
        )
        for sentence_id in sentence_ids[:sentence_item_count]
    ]
    remaining_item_count = max(0, review_item_count - len(item_specs))
    item_specs.extend(
        PlannedItemSpec(
            item_type="word_choice",
            prompt_lang="ja",
            answer_lang="en",
            word_id=word_id,
        )
        for word_id in (
            [] if remaining_item_count <= 0 or not word_ids else (word_ids * ((remaining_item_count + len(word_ids) - 1) // len(word_ids)))[:remaining_item_count]
        )
    )
    return _shuffle_item_specs(lesson_id=lesson.id, item_specs=item_specs)


def _persist_item_specs(
    db: Session,
    *,
    lesson_id: str,
    item_specs: list[PlannedItemSpec],
) -> ItemGenerationCounters:
    counters = ItemGenerationCounters()
    for order_index, item_spec in enumerate(item_specs, start=1):
        if item_spec.item_type == "word_choice":
            if item_spec.word_id is None:
                msg = f"word_choice item requires word_id for lesson_id={lesson_id}"
                raise ValueError(msg)
            _add_word_choice_item(
                db,
                lesson_id=lesson_id,
                order_index=order_index,
                prompt_lang=item_spec.prompt_lang,
                answer_lang=item_spec.answer_lang,
                word_id=item_spec.word_id,
            )
            counters = ItemGenerationCounters(
                items_created=counters.items_created + 1,
                word_choice_items_created=counters.word_choice_items_created + 1,
                sentence_tiles_items_created=counters.sentence_tiles_items_created,
                kanji_kana_match_items_created=counters.kanji_kana_match_items_created,
            )
            continue
        if item_spec.item_type == "sentence_tiles":
            if item_spec.sentence_id is None or item_spec.tile_set_id is None:
                msg = f"sentence_tiles item requires sentence_id and tile_set_id for lesson_id={lesson_id}"
                raise ValueError(msg)
            _add_sentence_tiles_item(
                db,
                lesson_id=lesson_id,
                order_index=order_index,
                prompt_lang=item_spec.prompt_lang,
                answer_lang=item_spec.answer_lang,
                sentence_id=item_spec.sentence_id,
                tile_set_id=item_spec.tile_set_id,
            )
            counters = ItemGenerationCounters(
                items_created=counters.items_created + 1,
                word_choice_items_created=counters.word_choice_items_created,
                sentence_tiles_items_created=counters.sentence_tiles_items_created + 1,
                kanji_kana_match_items_created=counters.kanji_kana_match_items_created,
            )
            continue
        if item_spec.item_type == "kanji_kana_match":
            if item_spec.word_id is None:
                msg = f"kanji_kana_match item requires word_id for lesson_id={lesson_id}"
                raise ValueError(msg)
            if item_spec.prompt_script is None or item_spec.answer_script is None:
                msg = f"kanji_kana_match item requires prompt_script and answer_script for lesson_id={lesson_id}"
                raise ValueError(msg)
            _add_kanji_kana_match_item(
                db,
                lesson_id=lesson_id,
                order_index=order_index,
                word_id=item_spec.word_id,
                prompt_script=item_spec.prompt_script,
                answer_script=item_spec.answer_script,
            )
            counters = ItemGenerationCounters(
                items_created=counters.items_created + 1,
                word_choice_items_created=counters.word_choice_items_created,
                sentence_tiles_items_created=counters.sentence_tiles_items_created,
                kanji_kana_match_items_created=counters.kanji_kana_match_items_created + 1,
            )
            continue
        msg = f"Unsupported item type {item_spec.item_type!r} for lesson_id={lesson_id}"
        raise ValueError(msg)
    return counters


def generate_lesson_items(
    db: Session,
    *,
    context: BuildContext,
) -> LessonItemGenerationStats:
    q = AssemblyQueries(db, context.course_version_id, context.section_code)
    section = q.get_section()
    if section is None:
        msg = (
            f"Section config must exist before lesson item generation for course_version_id={context.course_version_id}"
        )
        raise ValueError(msg)
    if q.count_lessons_for_section(section_id=section.id) == 0:
        msg = f"Lessons must exist before lesson item generation for course_version_id={context.course_version_id}"
        raise ValueError(msg)
    _delete_existing_section_items(db, section_id=section.id)
    lessons = q.list_section_lessons(section_id=section.id)
    planned_lesson_by_lesson_id = {
        lesson_with_plan.lesson.id: lesson_with_plan.planned_lesson
        for lesson_with_plan in list_lessons_with_plan(
            context=context,
            q=PlanningQueries(db, context.course_version_id, context.section_code),
        )
    }

    counters = ItemGenerationCounters()
    introduced_word_choice_ids: set[str] = set(q.list_previously_introduced_word_ids())
    surfaced_normal_sentence_ids: set[str] = set()
    normal_lessons = [lesson for lesson in lessons if lesson.kind == "normal"]
    next_normal_lesson_id_by_lesson_id: dict[str, str] = {}
    for index, lesson in enumerate(normal_lessons[:-1]):
        next_normal_lesson_id_by_lesson_id[lesson.id] = normal_lessons[index + 1].id
    pending_sentence_ids_by_lesson_id: dict[str, list[str]] = {lesson.id: [] for lesson in normal_lessons}
    final_sentence_ids_by_lesson_id: dict[str, list[str]] = {lesson.id: [] for lesson in normal_lessons}
    for lesson in lessons:
        word_ids = q.list_word_ids_for_lesson(lesson_id=lesson.id)
        sentence_ids = list(
            dict.fromkeys(
                [
                    *pending_sentence_ids_by_lesson_id.get(lesson.id, []),
                    *q.list_sentence_ids_for_lesson(lesson_id=lesson.id),
                ]
            )
        )
        lesson_words = q.list_word_rows_for_lesson(lesson_id=lesson.id)
        sentence_word_ids_by_sentence_id = q.map_word_ids_by_sentence_id(sentence_ids=sentence_ids)

        if lesson.kind == "normal":
            planned_lesson = planned_lesson_by_lesson_id[lesson.id]
            en_tile_sets = q.map_tile_set_id_by_sentence_id(
                sentence_ids=sentence_ids,
                answer_lang="en",
            )
            ja_tile_sets = q.map_tile_set_id_by_sentence_id(
                sentence_ids=sentence_ids,
                answer_lang="ja",
            )
            normal_item_specs = _build_normal_lesson_item_specs(
                lesson=lesson,
                planned_lesson=planned_lesson,
                previously_introduced_word_ids=introduced_word_choice_ids,
                sentence_ids=sentence_ids,
                lesson_words=lesson_words,
                sentence_word_ids_by_sentence_id=sentence_word_ids_by_sentence_id,
                en_tile_sets=en_tile_sets,
                ja_tile_sets=ja_tile_sets,
            )
            final_sentence_ids_by_lesson_id[lesson.id] = _ordered_unique_ids(
                values=[
                    item_spec.sentence_id
                    for item_spec in normal_item_specs.item_specs
                    if item_spec.item_type == "sentence_tiles" and item_spec.sentence_id is not None
                ]
            )
            if normal_item_specs.overflow_sentence_ids:
                next_lesson_id = next_normal_lesson_id_by_lesson_id.get(lesson.id)
                if next_lesson_id is None:
                    msg = (
                        "Normal lesson exceeds bounded item capacity after enforcing sentence coverage: "
                        f"lesson_id={lesson.id} overflow_sentence_count={len(normal_item_specs.overflow_sentence_ids)} "
                        "and there is no later normal lesson"
                    )
                    raise ValueError(msg)
                pending_sentence_ids_by_lesson_id[next_lesson_id] = list(
                    dict.fromkeys(
                        [
                            *pending_sentence_ids_by_lesson_id[next_lesson_id],
                            *normal_item_specs.overflow_sentence_ids,
                        ]
                    )
                )
            lesson_counters = _persist_item_specs(
                db,
                lesson_id=lesson.id,
                item_specs=normal_item_specs.item_specs,
            )
            lesson.target_item_count = len(normal_item_specs.item_specs)
            counters = _merge_counters(left=counters, right=lesson_counters)
            introduced_word_choice_ids.update(
                item_spec.word_id
                for item_spec in normal_item_specs.item_specs
                if item_spec.item_type == "word_choice" and item_spec.word_id is not None
            )
            surfaced_normal_sentence_ids.update(
                item_spec.sentence_id
                for item_spec in normal_item_specs.item_specs
                if item_spec.item_type == "sentence_tiles" and item_spec.sentence_id is not None
            )
            continue

        review_item_count = (
            context.config.items.review_previous_units.item_count
            if lesson.kind == "review_previous_units"
            else context.config.items.exam.item_count
        )
        half = review_item_count // 2
        surfaced_sentence_ids = [sentence_id for sentence_id in sentence_ids if sentence_id in surfaced_normal_sentence_ids]
        en_tile_sets = q.map_tile_set_id_by_sentence_id(
            sentence_ids=surfaced_sentence_ids,
            answer_lang="en",
        )
        review_exam_item_specs = _build_review_exam_item_specs(
            lesson=lesson,
            word_ids=word_ids,
            sentence_ids=surfaced_sentence_ids,
            sentence_item_count=half,
            review_item_count=review_item_count,
            en_tile_sets=en_tile_sets,
        )
        lesson_counters = _persist_item_specs(
            db,
            lesson_id=lesson.id,
            item_specs=review_exam_item_specs,
        )
        lesson.target_item_count = len(review_exam_item_specs)
        counters = _merge_counters(left=counters, right=lesson_counters)

    if normal_lessons:
        db.execute(delete(LessonSentence).where(LessonSentence.lesson_id.in_([lesson.id for lesson in normal_lessons])))
        for lesson in normal_lessons:
            for order_index, sentence_id in enumerate(final_sentence_ids_by_lesson_id[lesson.id], start=1):
                db.add(
                    LessonSentence(
                        lesson_id=lesson.id,
                        sentence_id=sentence_id,
                        order_index=order_index,
                        role="core",
                    )
                )
    db.commit()
    return LessonItemGenerationStats(
        items_created=counters.items_created,
        word_choice_items_created=counters.word_choice_items_created,
        sentence_tiles_items_created=counters.sentence_tiles_items_created,
        kanji_kana_match_items_created=counters.kanji_kana_match_items_created,
    )
