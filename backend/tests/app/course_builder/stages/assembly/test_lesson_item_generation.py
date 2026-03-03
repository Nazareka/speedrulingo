from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course_builder.queries.planning import CurriculumLesson
from course_builder.stages.assembly.lesson_item_generation import (
    PlannedItemSpec,
    _build_normal_lesson_item_specs,
    _shuffle_item_specs,
    _spread_duplicate_word_choice_specs,
    generate_lesson_items,
)
from course_builder.stages.assembly.review_exam_lesson_creation import create_algorithmic_review_exam_lessons
from course_builder.stages.assembly.tile_generation import build_tile_sets
from domain.content.models import (
    Item,
    ItemKanjiKanaMatch,
    ItemSentenceTiles,
    ItemWordChoice,
    Lesson,
    LessonWord,
    SentenceWordLink,
    Unit,
    Word,
)
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_sentence_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload

build_context = create_test_build_context
load_config = load_test_config


def item_test_config() -> str:
    return build_test_config_yaml(
        updates={
            ("lessons", "normal_lessons_per_unit"): 1,
            ("items", "word_translation", "item_count"): 4,
            ("items", "sentence_translation", "item_count"): 4,
            ("items", "review_previous_units", "item_count"): 2,
            ("items", "exam", "item_count"): 2,
        }
    )


def test_generate_lesson_items_persists_expected_item_mix(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=item_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    build_tile_sets(db_session, context=context)
    create_algorithmic_review_exam_lessons(db_session, context=context)

    stats = generate_lesson_items(db_session, context=context)

    assert stats.items_created > 0
    assert stats.word_choice_items_created > 0

    total_items = int(db_session.scalar(select(func.count()).select_from(Item)) or 0)
    total_word_choice = int(db_session.scalar(select(func.count()).select_from(ItemWordChoice)) or 0)
    total_sentence_tiles = int(db_session.scalar(select(func.count()).select_from(ItemSentenceTiles)) or 0)
    total_kanji_kana = int(db_session.scalar(select(func.count()).select_from(ItemKanjiKanaMatch)) or 0)
    assert total_items == stats.items_created
    assert total_word_choice == stats.word_choice_items_created
    assert total_sentence_tiles == stats.sentence_tiles_items_created
    assert total_kanji_kana == stats.kanji_kana_match_items_created

    lessons = db_session.scalars(
        select(Lesson).join(Unit, Unit.id == Lesson.unit_id).order_by(Unit.order_index, Lesson.order_index)
    ).all()
    total_sentence_tiles_in_lessons = 0
    for lesson in lessons:
        item_types = list(
            db_session.scalars(select(Item.type).where(Item.lesson_id == lesson.id).order_by(Item.order_index))
        )
        assert 0 < len(item_types) <= lesson.target_item_count
        assert set(item_types).issubset({"word_choice", "sentence_tiles", "kanji_kana_match"})
        total_sentence_tiles_in_lessons += item_types.count("sentence_tiles")

    assert total_sentence_tiles_in_lessons == stats.sentence_tiles_items_created

    exam_lesson = db_session.scalar(
        select(Lesson)
        .join(Unit, Unit.id == Lesson.unit_id)
        .where(Unit.order_index == 1, Lesson.kind == "exam")
        .limit(1)
    )
    assert exam_lesson is not None
    exam_prompt_answer_pairs = list(
        db_session.execute(
            select(Item.prompt_lang, Item.answer_lang)
            .where(Item.lesson_id == exam_lesson.id)
            .order_by(Item.order_index)
        ).all()
    )
    assert exam_prompt_answer_pairs == [
        ("ja", "en"),
        ("ja", "en"),
    ]


def test_generate_lesson_items_rebuilds_section_cleanly(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=item_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    build_tile_sets(db_session, context=context)
    create_algorithmic_review_exam_lessons(db_session, context=context)

    first_stats = generate_lesson_items(db_session, context=context)
    second_stats = generate_lesson_items(db_session, context=context)

    total_items = int(db_session.scalar(select(func.count()).select_from(Item)) or 0)
    total_word_choice = int(db_session.scalar(select(func.count()).select_from(ItemWordChoice)) or 0)
    total_sentence_tiles = int(db_session.scalar(select(func.count()).select_from(ItemSentenceTiles)) or 0)
    total_kanji_kana = int(db_session.scalar(select(func.count()).select_from(ItemKanjiKanaMatch)) or 0)

    assert first_stats.items_created == second_stats.items_created
    assert total_items == second_stats.items_created
    assert total_word_choice == second_stats.word_choice_items_created
    assert total_sentence_tiles == second_stats.sentence_tiles_items_created
    assert total_kanji_kana == second_stats.kanji_kana_match_items_created


def test_generate_lesson_items_keeps_word_choice_before_sentence_for_new_words(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=item_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    build_tile_sets(db_session, context=context)
    create_algorithmic_review_exam_lessons(db_session, context=context)
    generate_lesson_items(db_session, context=context)

    lesson = db_session.scalar(
        select(Lesson)
        .join(Unit, Unit.id == Lesson.unit_id)
        .where(Unit.order_index == 1, Lesson.kind == "normal")
        .order_by(Lesson.order_index)
        .limit(1)
    )
    assert lesson is not None

    word_choice_rows = db_session.execute(
        select(Item.order_index, ItemWordChoice.word_id)
        .join(ItemWordChoice, ItemWordChoice.item_id == Item.id)
        .where(Item.lesson_id == lesson.id, Item.type == "word_choice")
        .order_by(Item.order_index)
    ).all()
    sentence_item_rows = db_session.execute(
        select(
            Item.order_index,
            ItemSentenceTiles.sentence_id.label("sentence_tiles_sentence_id"),
        )
        .outerjoin(ItemSentenceTiles, ItemSentenceTiles.item_id == Item.id)
        .where(Item.lesson_id == lesson.id, Item.type == "sentence_tiles")
        .order_by(Item.order_index)
    ).all()
    sentence_word_ids_by_sentence_id: dict[str, set[str]] = {}
    sentence_ids = [row.sentence_tiles_sentence_id for row in sentence_item_rows]
    for sentence_word_row in db_session.execute(
        select(SentenceWordLink.sentence_id, SentenceWordLink.word_id).where(
            SentenceWordLink.sentence_id.in_(sentence_ids)
        )
    ).all():
        sentence_word_ids_by_sentence_id.setdefault(sentence_word_row.sentence_id, set()).add(sentence_word_row.word_id)

    introduced_word_ids = set(
        db_session.scalars(
            select(LessonWord.word_id).where(LessonWord.lesson_id == lesson.id, LessonWord.role == "new")
        )
    )
    word_choice_order_by_word_id = {
        word_choice_row.word_id: word_choice_row.order_index
        for word_choice_row in word_choice_rows
        if word_choice_row.word_id in introduced_word_ids
    }

    for sentence_item_row in sentence_item_rows:
        sentence_id = sentence_item_row.sentence_tiles_sentence_id
        assert sentence_id is not None
        for word_id in sentence_word_ids_by_sentence_id.get(sentence_id, set()):
            if word_id in word_choice_order_by_word_id:
                assert word_choice_order_by_word_id[word_id] < sentence_item_row.order_index


def test_generate_lesson_items_review_exam_only_reuses_sentences_shown_in_normal_lessons(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=item_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    build_tile_sets(db_session, context=context)
    create_algorithmic_review_exam_lessons(db_session, context=context)
    generate_lesson_items(db_session, context=context)

    normal_lessons = db_session.scalars(
        select(Lesson)
        .join(Unit, Unit.id == Lesson.unit_id)
        .where(Unit.order_index == 1, Lesson.kind == "normal")
        .order_by(Lesson.order_index)
    ).all()
    surfaced_normal_sentence_ids: set[str] = set()
    for lesson in normal_lessons:
        surfaced_normal_sentence_ids.update(
            sentence_id
            for sentence_id in db_session.scalars(
                select(ItemSentenceTiles.sentence_id)
                .join(Item, Item.id == ItemSentenceTiles.item_id)
                .where(Item.lesson_id == lesson.id)
            ).all()
        )
    review_and_exam_lessons = db_session.scalars(
        select(Lesson)
        .join(Unit, Unit.id == Lesson.unit_id)
        .where(Unit.order_index == 1, Lesson.kind.in_(("review_previous_units", "exam")))
        .order_by(Lesson.order_index)
    ).all()
    for lesson in review_and_exam_lessons:
        sentence_ids = list(
            db_session.scalars(
                select(ItemSentenceTiles.sentence_id)
                .join(Item, Item.id == ItemSentenceTiles.item_id)
                .where(Item.lesson_id == lesson.id)
            ).all()
        )
        assert set(sentence_ids).issubset(surfaced_normal_sentence_ids)


def test_build_normal_lesson_item_specs_puts_kanji_intro_before_sentences(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        order_index=1,
        kind="normal",
        target_item_count=3,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=1,
        kind="normal",
        lesson_kind="unit_kernel",
        force_kana_display=False,
        target_item_count=3,
        introduced_word_lemmas=("学生",),
        kanji_focus_word_lemmas=(),
        target_word_lemmas=("学生",),
        target_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_code="WA_DESU_STATEMENT",
        target_pattern_examples=(),
        available_word_lemmas=("学生",),
        available_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_sentence_count=1,
    )
    lesson_words = [
        Word(
            id="word-student",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="学生",
            reading_kana="がくせい",
            gloss_primary_en="student",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="config_example",
        )
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids=set(),
        sentence_ids=["sentence-1"],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={"sentence-1": {"word-student"}},
        en_tile_sets={"sentence-1": "tile-set-1"},
        ja_tile_sets={"sentence-1": "tile-set-ja-1"},
    ).item_specs

    kanji_word_id = "word-student"
    kanji_item_indices = [
        index
        for index, item_spec in enumerate(item_specs)
        if item_spec.item_type == "kanji_kana_match" and item_spec.word_id == kanji_word_id
    ]
    word_choice_index = next(
        index
        for index, item_spec in enumerate(item_specs)
        if item_spec.item_type == "word_choice" and item_spec.word_id == kanji_word_id
    )
    sentence_index = next(
        index
        for index, item_spec in enumerate(item_specs)
        if item_spec.item_type == "sentence_tiles"
    )
    assert len(kanji_item_indices) == 1
    assert kanji_item_indices[0] < word_choice_index < sentence_index


def test_build_normal_lesson_item_specs_for_kanji_activation_builds_kana_to_kanji_then_word_choice(
    db_session: Session,
    tmp_path: Path,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-activation",
        unit_id="unit-1",
        order_index=3,
        kind="normal",
        target_item_count=2,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=3,
        kind="normal",
        lesson_kind="kanji_activation",
        force_kana_display=False,
        target_item_count=2,
        introduced_word_lemmas=(),
        kanji_focus_word_lemmas=("学生",),
        target_word_lemmas=(),
        target_pattern_codes=(),
        target_pattern_code=None,
        target_pattern_examples=(),
        available_word_lemmas=("学生",),
        available_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_sentence_count=0,
    )
    lesson_words = [
        Word(
            id="word-student",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="学生",
            reading_kana="がくせい",
            gloss_primary_en="student",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="config_example",
        )
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids={"word-student"},
        sentence_ids=[],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={},
        en_tile_sets={},
        ja_tile_sets={},
    ).item_specs

    assert [(item_spec.item_type, item_spec.prompt_script, item_spec.answer_script) for item_spec in item_specs] == [
        ("kanji_kana_match", "kana", "kanji"),
        ("word_choice", None, None),
    ]


def test_shuffle_item_specs_varies_by_lesson_id() -> None:
    item_specs = [
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w1"),
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w2"),
        PlannedItemSpec(
            item_type="sentence_tiles",
            prompt_lang="ja",
            answer_lang="en",
            sentence_id="s1",
            tile_set_id="t1",
        ),
        PlannedItemSpec(
            item_type="sentence_tiles",
            prompt_lang="ja",
            answer_lang="en",
            sentence_id="s2",
            tile_set_id="t2",
        ),
    ]

    first_order = [
        item_spec.item_type + (item_spec.word_id or item_spec.sentence_id or "")
        for item_spec in _shuffle_item_specs(lesson_id="lesson-a", item_specs=item_specs)
    ]
    second_order = [
        item_spec.item_type + (item_spec.word_id or item_spec.sentence_id or "")
        for item_spec in _shuffle_item_specs(lesson_id="lesson-b", item_specs=item_specs)
    ]

    assert first_order != second_order


def test_spread_duplicate_word_choice_specs_avoids_adjacent_duplicates_when_possible() -> None:
    item_specs = [
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w1"),
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w1"),
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w2"),
        PlannedItemSpec(item_type="word_choice", prompt_lang="ja", answer_lang="en", word_id="w3"),
    ]

    spread_specs = _spread_duplicate_word_choice_specs(item_specs=item_specs)
    spread_word_ids = [item_spec.word_id for item_spec in spread_specs]

    assert spread_word_ids[0] == "w1"
    assert all(left != right for left, right in pairwise(spread_word_ids))


def test_build_normal_lesson_item_specs_does_not_add_review_filler_word_choices(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        order_index=1,
        kind="normal",
        target_item_count=4,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=1,
        kind="normal",
        lesson_kind="unit_kernel",
        force_kana_display=False,
        target_item_count=4,
        introduced_word_lemmas=("学生",),
        kanji_focus_word_lemmas=(),
        target_word_lemmas=("学生",),
        target_pattern_codes=(),
        target_pattern_code=None,
        target_pattern_examples=(),
        available_word_lemmas=("学生", "先生", "本", "水"),
        available_pattern_codes=(),
        target_pattern_sentence_count=0,
    )
    lesson_words = [
        Word(
            id="w1",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="学生",
            reading_kana="がくせい",
            gloss_primary_en="student",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
        Word(
            id="w2",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="先生",
            reading_kana="せんせい",
            gloss_primary_en="teacher",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=2,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
        Word(
            id="w3",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="本",
            reading_kana="ほん",
            gloss_primary_en="book",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=3,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
        Word(
            id="w4",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="水",
            reading_kana="みず",
            gloss_primary_en="water",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=4,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids=set(),
        sentence_ids=[],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={},
        en_tile_sets={},
        ja_tile_sets={},
    ).item_specs

    word_choice_ids = [item_spec.word_id for item_spec in item_specs if item_spec.item_type == "word_choice"]
    assert word_choice_ids == ["w1"]


def test_build_normal_lesson_item_specs_adds_required_word_choice_intro_before_sentence(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        order_index=1,
        kind="normal",
        target_item_count=3,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=1,
        kind="normal",
        lesson_kind="unit_kernel",
        force_kana_display=False,
        target_item_count=3,
        introduced_word_lemmas=("学生", "先生"),
        kanji_focus_word_lemmas=(),
        target_word_lemmas=("学生",),
        target_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_code="WA_DESU_STATEMENT",
        target_pattern_examples=(),
        available_word_lemmas=("学生", "先生"),
        available_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_sentence_count=1,
    )
    lesson_words = [
        Word(
            id="word-student",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="学生",
            reading_kana="がくせい",
            gloss_primary_en="student",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
        Word(
            id="word-teacher",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="先生",
            reading_kana="せんせい",
            gloss_primary_en="teacher",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=2,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids=set(),
        sentence_ids=["sentence-1"],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={"sentence-1": {"word-student", "word-teacher"}},
        en_tile_sets={"sentence-1": "tile-set-1"},
        ja_tile_sets={"sentence-1": "tile-set-ja-1"},
    ).item_specs

    assert [item_spec.item_type for item_spec in item_specs].count("word_choice") == 2
    assert [item_spec.item_type for item_spec in item_specs].count("sentence_tiles") == 2


def test_build_normal_lesson_item_specs_does_not_surface_sentence_when_lesson_does_not_introduce_needed_words(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        order_index=1,
        kind="normal",
        target_item_count=3,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=1,
        kind="normal",
        lesson_kind="unit_kernel",
        force_kana_display=False,
        target_item_count=3,
        introduced_word_lemmas=(),
        kanji_focus_word_lemmas=(),
        target_word_lemmas=(),
        target_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_code="WA_DESU_STATEMENT",
        target_pattern_examples=(),
        available_word_lemmas=("これ", "本"),
        available_pattern_codes=("WA_DESU_STATEMENT",),
        target_pattern_sentence_count=1,
    )
    lesson_words = [
        Word(
            id="word-kore",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="これ",
            reading_kana="これ",
            gloss_primary_en="this",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="pronoun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
        Word(
            id="word-hon",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="本",
            reading_kana="ほん",
            gloss_primary_en="book",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=2,
            is_bootstrap_seed=False,
            source_kind="config_example",
        ),
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids=set(),
        sentence_ids=["sentence-1"],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={"sentence-1": {"word-kore", "word-hon"}},
        en_tile_sets={"sentence-1": "tile-set-1"},
        ja_tile_sets={"sentence-1": "tile-set-ja-1"},
    ).item_specs

    assert [item_spec.item_type for item_spec in item_specs].count("word_choice") == 0
    assert not any(item_spec.item_type == "sentence_tiles" for item_spec in item_specs)


def test_build_normal_lesson_item_specs_does_not_create_intro_for_non_target_word(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_context_obj = create_test_build_context(db_session, tmp_path, content=item_test_config())
    lesson = Lesson(
        id="lesson-1",
        unit_id="unit-1",
        order_index=1,
        kind="normal",
        target_item_count=2,
    )
    planned_lesson = CurriculumLesson(
        lesson_index_within_unit=1,
        kind="normal",
        lesson_kind="unit_kernel",
        force_kana_display=False,
        target_item_count=2,
        introduced_word_lemmas=(),
        kanji_focus_word_lemmas=(),
        target_word_lemmas=(),
        target_pattern_codes=(),
        target_pattern_code=None,
        target_pattern_examples=(),
        available_word_lemmas=("ソファ",),
        available_pattern_codes=(),
        target_pattern_sentence_count=0,
    )
    lesson_words = [
        Word(
            id="word-sofa",
            course_version_id=build_context_obj.course_version_id,
            canonical_writing_ja="ソファ",
            reading_kana="そふぁ",
            gloss_primary_en="sofa",
            gloss_alternatives_en=[],
            usage_note_en=None,
            pos="noun",
            intro_order=1,
            is_bootstrap_seed=False,
            source_kind="llm_generated",
        )
    ]

    item_specs = _build_normal_lesson_item_specs(
        lesson=lesson,
        planned_lesson=planned_lesson,
        previously_introduced_word_ids=set(),
        sentence_ids=[],
        lesson_words=lesson_words,
        sentence_word_ids_by_sentence_id={},
        en_tile_sets={},
        ja_tile_sets={},
    ).item_specs

    assert item_specs == []
