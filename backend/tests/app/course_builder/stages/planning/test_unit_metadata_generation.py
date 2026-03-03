from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.llm.unit_metadata_generation import graph as unit_metadata_generation_graph
from course_builder.queries.planning import CurriculumPattern, CurriculumPatternExample, CurriculumWord
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags
from course_builder.stages.planning.section_curriculum import (
    KANJI_ACTIVATION_WORDS_PER_LESSON,
    MAX_NORMAL_LESSONS_PER_UNIT,
    MIN_NORMAL_LESSONS_PER_UNIT,
    _split_sentence_introductions,
    build_pattern_bundles,
    build_section_curriculum,
)
from course_builder.stages.planning.section_curriculum_planning import persist_section_curriculum
from course_builder.stages.planning.unit_metadata_generation import generate_unit_metadata
from domain.content.models import Unit
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.fake_llms import SequentialStructuredLlm
from tests.helpers.scenarios import single_intro_unit_plan_payload


def _make_pattern(*, code: str, intro_order: int, lemma: str, reading: str, ja_text: str) -> CurriculumPattern:
    return CurriculumPattern(
        pattern_id=code,
        code=code,
        name=code,
        templates=(code,),
        short_description=code,
        intro_order=intro_order,
        examples=(
            CurriculumPatternExample(
                pattern_code=code,
                ja_text=ja_text,
                en_text="Example.",
                lexicon_used=((lemma, reading, "noun"),),
            ),
        ),
    )


def _make_word(
    *,
    word_id: str,
    lemma: str,
    reading: str,
    intro_order: int,
    pattern_code: str,
    source_kind: str = "llm",
    pos: str = "noun",
    example_pattern_codes: tuple[str, ...] | None = None,
) -> CurriculumWord:
    return CurriculumWord(
        word_id=word_id,
        canonical_writing_ja=lemma,
        reading_kana=reading,
        pos=pos,
        intro_order=intro_order,
        is_bootstrap_seed=False,
        source_kind=source_kind,
        example_pattern_codes=example_pattern_codes or (pattern_code,),
    )


def test_build_section_curriculum_uses_sentence_intro_bounds_for_unit_shapes(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    config.current_section.section_planning.min_sentence_introductions_per_normal_lesson = 2
    config.current_section.section_planning.max_sentence_introductions_per_normal_lesson = 3
    words = [
        _make_word(
            word_id=f"w{index}",
            lemma=f"語{index}",
            reading="ご",
            intro_order=index,
            pattern_code="WA_DESU_STATEMENT",
        )
        for index in range(1, 6)
    ]
    patterns = [
        _make_pattern(
            code="WA_DESU_STATEMENT",
            intro_order=1,
            lemma="語1",
            reading="ご",
            ja_text="語1です。",
        )
    ]

    section_curriculum = build_section_curriculum(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=[],
        previously_introduced_pattern_codes=[],
        current_section_bootstrap_expression_lemmas=[],
        generated_sentence_count_by_lemma={word.canonical_writing_ja: 2 for word in words},
    )

    lesson_counts = [len(unit.lessons) for unit in section_curriculum.units]
    assert lesson_counts == [2, 2]
    assert all(MIN_NORMAL_LESSONS_PER_UNIT <= count <= MAX_NORMAL_LESSONS_PER_UNIT for count in lesson_counts)


def test_split_sentence_introductions_falls_back_to_balanced_under_min_split() -> None:
    assert _split_sentence_introductions(sentence_count=6, min_per_lesson=4, max_per_lesson=5) == [3, 3]
    assert _split_sentence_introductions(sentence_count=7, min_per_lesson=4, max_per_lesson=5) == [4, 3]


def test_build_pattern_bundles_uses_origin_pattern_for_extra_words(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    second_pattern_config = config.patterns[0].model_copy(
        update={"code": "KA_QUESTION", "name": "KA_QUESTION", "templates": ["ですか"]}
    )
    config.patterns = [config.patterns[0], second_pattern_config]
    config.current_section.patterns_scope = ["WA_DESU_STATEMENT", "KA_QUESTION"]
    patterns = [
        _make_pattern(
            code="WA_DESU_STATEMENT",
            intro_order=1,
            lemma="私",
            reading="わたし",
            ja_text="私は学生です。",
        ),
        _make_pattern(
            code="KA_QUESTION",
            intro_order=2,
            lemma="誰",
            reading="だれ",
            ja_text="誰ですか。",
        ),
    ]
    words = [
        _make_word(word_id="w1", lemma="私", reading="わたし", intro_order=1, pattern_code="WA_DESU_STATEMENT"),
        _make_word(
            word_id="w2",
            lemma="誰",
            reading="だれ",
            intro_order=2,
            pattern_code="KA_QUESTION",
            source_kind="pattern:KA_QUESTION",
            example_pattern_codes=("WA_DESU_STATEMENT", "KA_QUESTION"),
        ),
    ]

    bundles = build_pattern_bundles(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=[],
        current_section_bootstrap_expression_lemmas=[],
    )

    bundle_words_by_code = {bundle.pattern_code: set(bundle.new_word_lemmas) for bundle in bundles}
    assert "誰" not in bundle_words_by_code["WA_DESU_STATEMENT"]
    assert "誰" in bundle_words_by_code["KA_QUESTION"]


def test_build_pattern_bundles_keeps_new_expression_in_word_choice_intros(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    config.patterns[0] = config.patterns[0].model_copy(
        update={"required_support_forms": ["かったです"]}
    )
    patterns = [
        _make_pattern(
            code="WA_DESU_STATEMENT",
            intro_order=1,
            lemma="私",
            reading="わたし",
            ja_text="私は学生です。",
        ),
    ]
    words = [
        _make_word(word_id="w1", lemma="私", reading="わたし", intro_order=1, pattern_code="WA_DESU_STATEMENT"),
        _make_word(
            word_id="w2",
            lemma="かったです",
            reading="かったです",
            intro_order=2,
            pattern_code="WA_DESU_STATEMENT",
            pos="expression",
            source_kind="pattern:WA_DESU_STATEMENT",
        ),
    ]

    bundles = build_pattern_bundles(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=[],
        current_section_bootstrap_expression_lemmas=[],
    )

    bundle = next(bundle for bundle in bundles if bundle.pattern_code == "WA_DESU_STATEMENT")
    assert "かったです" in bundle.new_word_lemmas
    assert "かったです" in bundle.word_choice_intro_lemmas


def test_build_section_curriculum_keeps_bootstrap_support_only_in_single_unit(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)

    section_curriculum = build_section_curriculum(
        config=config,
        words=[],
        patterns=[],
        previously_introduced_word_lemmas=[],
        previously_introduced_pattern_codes=[],
        current_section_bootstrap_expression_lemmas=["こんにちは", "ありがとう"],
        generated_sentence_count_by_lemma={},
    )

    assert len(section_curriculum.units) == 1
    assert len(section_curriculum.units[0].lessons) == 1
    assert section_curriculum.units[0].lessons[0].lesson_kind == "bootstrap_support_only"


def test_build_section_curriculum_inserts_kanji_activation_after_third_pattern(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    second_pattern_config = config.patterns[0].model_copy(
        update={"code": "KORE_WA_NAN_DESU_KA", "name": "KORE_WA_NAN_DESU_KA", "templates": ["これは何ですか"]}
    )
    third_pattern_config = config.patterns[0].model_copy(
        update={"code": "SORE_WA_NAN_DESU_KA", "name": "SORE_WA_NAN_DESU_KA", "templates": ["それは何ですか"]}
    )
    config.patterns = [config.patterns[0], second_pattern_config, third_pattern_config]
    config.current_section.patterns_scope = ["WA_DESU_STATEMENT", "KORE_WA_NAN_DESU_KA", "SORE_WA_NAN_DESU_KA"]
    words = [
        _make_word(word_id="w1", lemma="学生", reading="がくせい", intro_order=1, pattern_code="WA_DESU_STATEMENT"),
        _make_word(word_id="w2", lemma="先生", reading="せんせい", intro_order=2, pattern_code="KORE_WA_NAN_DESU_KA"),
        _make_word(word_id="w3", lemma="病院", reading="びょういん", intro_order=3, pattern_code="SORE_WA_NAN_DESU_KA"),
    ]
    patterns = [
        _make_pattern(code="WA_DESU_STATEMENT", intro_order=1, lemma="学生", reading="がくせい", ja_text="学生です。"),
        _make_pattern(code="KORE_WA_NAN_DESU_KA", intro_order=2, lemma="先生", reading="せんせい", ja_text="先生です。"),
        _make_pattern(code="SORE_WA_NAN_DESU_KA", intro_order=3, lemma="病院", reading="びょういん", ja_text="病院です。"),
    ]

    section_curriculum = build_section_curriculum(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=[],
        previously_introduced_pattern_codes=[],
        current_section_bootstrap_expression_lemmas=[],
        generated_sentence_count_by_lemma={},
    )

    flattened_lesson_kinds = [lesson.lesson_kind for unit in section_curriculum.units for lesson in unit.lessons]
    assert "kanji_activation" in flattened_lesson_kinds
    activation_lesson = next(
        lesson for unit in section_curriculum.units for lesson in unit.lessons if lesson.lesson_kind == "kanji_activation"
    )
    assert len(activation_lesson.kanji_focus_word_lemmas) <= KANJI_ACTIVATION_WORDS_PER_LESSON


def test_build_section_curriculum_skips_empty_pattern_bundles(tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    second_pattern_config = config.patterns[0].model_copy(
        update={"code": "KA_QUESTION", "name": "KA_QUESTION", "templates": ["ですか"]}
    )
    config.patterns = [config.patterns[0], second_pattern_config]
    config.current_section.patterns_scope = ["WA_DESU_STATEMENT", "KA_QUESTION"]
    words = [
        _make_word(
            word_id="w1",
            lemma="私",
            reading="わたし",
            intro_order=1,
            pattern_code="WA_DESU_STATEMENT",
        )
    ]
    patterns = [
        _make_pattern(
            code="WA_DESU_STATEMENT",
            intro_order=1,
            lemma="私",
            reading="わたし",
            ja_text="私は学生です。",
        ),
        CurriculumPattern(
            pattern_id="KA_QUESTION",
            code="KA_QUESTION",
            name="KA_QUESTION",
            templates=("ですか",),
            short_description="KA_QUESTION",
            intro_order=2,
            examples=(),
        ),
    ]

    section_curriculum = build_section_curriculum(
        config=config,
        words=words,
        patterns=patterns,
        previously_introduced_word_lemmas=[],
        previously_introduced_pattern_codes=[],
        current_section_bootstrap_expression_lemmas=[],
        generated_sentence_count_by_lemma={},
    )

    flattened_lessons = [lesson for unit in section_curriculum.units for lesson in unit.lessons]
    assert flattened_lessons
    assert all(lesson.target_item_count > 0 for lesson in flattened_lessons)


def test_generate_unit_metadata_persists_sentence_first_curriculum(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = create_test_build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    insert_bootstrap_seed_words(db_session, context=context)
    unit_llm = SequentialStructuredLlm(payloads=[single_intro_unit_plan_payload()])
    monkeypatch.setattr(unit_metadata_generation_graph, "create_chat_openai", lambda *, model: unit_llm)

    persist_section_curriculum(db_session, context=context)
    stats = generate_unit_metadata(db_session, context=context)

    assert stats.units_created >= 1
    persisted_units = db_session.scalars(select(Unit).order_by(Unit.order_index)).all()
    assert persisted_units
