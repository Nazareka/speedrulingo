from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfigLoader
from course_builder.engine.models import BuildContext, compute_config_hash
from course_builder.stages.assembly.tile_generation import (
    TileSpec,
    _build_english_tiles,
    _validate_tile_specs,
    build_tile_sets,
)
from domain.content.models import CourseVersion, ItemSentenceTiles, SentenceTile, SentenceTileSet, SentenceUnit
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.pipeline import build_seeded_section, build_sentence_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload
from tests.helpers.test_config_source import TEST_CONFIG_YAML

build_context = create_test_build_context
load_config = load_test_config


def tile_test_config() -> str:
    return TEST_CONFIG_YAML


def test_build_tile_sets_creates_tiles_for_both_answer_languages(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=tile_test_config())
    build_sentence_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    stats = build_tile_sets(db_session, context=context)

    assert stats.tile_sets_created == 4
    assert stats.tiles_created > 0
    assert db_session.scalar(select(SentenceTileSet.id).limit(1)) is not None
    assert db_session.scalar(select(SentenceTile.id).limit(1)) is not None


def test_validate_tile_specs_ignores_incidental_japanese_whitespace() -> None:
    tile_specs = [
        TileSpec(text="いえは", unit_start=0, unit_end=1),
        TileSpec(text="いえです", unit_start=2, unit_end=3),
    ]

    _validate_tile_specs(
        tile_specs,
        original_text="いえは いえです。",
        answer_lang="ja",
    )


def test_validate_tile_specs_handles_apostrophe_spacing_in_english() -> None:
    tile_specs = [
        TileSpec(text="That", unit_start=0, unit_end=0),
        TileSpec(text="over", unit_start=1, unit_end=1),
        TileSpec(text="there", unit_start=2, unit_end=2),
        TileSpec(text="is", unit_start=3, unit_end=3),
        TileSpec(text="Sakura's", unit_start=4, unit_end=4),
        TileSpec(text="bag", unit_start=5, unit_end=5),
    ]

    _validate_tile_specs(
        tile_specs,
        original_text="That over there is Sakura's bag.",
        answer_lang="en",
    )


def test_validate_tile_specs_handles_quoted_english_text() -> None:
    tile_specs = [
        TileSpec(text="This", unit_start=0, unit_end=0),
        TileSpec(text="is", unit_start=1, unit_end=1),
        TileSpec(text="you're", unit_start=3, unit_end=3),
        TileSpec(text="welcome", unit_start=4, unit_end=4),
    ]

    _validate_tile_specs(
        tile_specs,
        original_text='This is "you\'re welcome."',
        answer_lang="en",
    )


def test_build_english_tiles_merges_single_letter_abbreviation_units() -> None:
    tile_specs = _build_english_tiles(
        [
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=0,
                surface="I",
                lemma="i",
                reading=None,
                pos="word",
            ),
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=1,
                surface="go",
                lemma="go",
                reading=None,
                pos="word",
            ),
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=2,
                surface="at",
                lemma="at",
                reading=None,
                pos="word",
            ),
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=3,
                surface="3",
                lemma="3",
                reading=None,
                pos="number",
            ),
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=4,
                surface="p",
                lemma="p",
                reading=None,
                pos="word",
            ),
            SentenceUnit(
                sentence_id="sentence-1",
                lang="en",
                unit_index=5,
                surface="m",
                lemma="m",
                reading=None,
                pos="word",
            ),
        ]
    )

    assert [tile.text for tile in tile_specs] == ["I", "go", "at", "3", "pm"]
    assert tile_specs[-1].unit_start == 4
    assert tile_specs[-1].unit_end == 5


def test_build_tile_sets_for_later_section_does_not_delete_previous_section_payloads(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pre_a1_context = build_context(db_session, tmp_path, content=tile_test_config(), section_code="PRE_A1")
    build_sentence_ready_course(
        db_session=db_session,
        context=pre_a1_context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )
    build_tile_sets(db_session, context=pre_a1_context)

    from course_builder.stages.assembly.lesson_item_generation import generate_lesson_items
    from course_builder.stages.assembly.review_exam_lesson_creation import (
        create_algorithmic_review_exam_lessons,
    )

    create_algorithmic_review_exam_lessons(db_session, context=pre_a1_context)
    generate_lesson_items(db_session, context=pre_a1_context)
    payload_count_before = int(db_session.scalar(select(func.count()).select_from(ItemSentenceTiles)) or 0)
    assert payload_count_before > 0

    real_config_root = Path(__file__).resolve().parents[5] / "config" / "en-ja-v1"
    a1_1_config = CourseBuildConfigLoader.load_and_validate(real_config_root, section_code="A1_1")
    course_version = db_session.get(CourseVersion, pre_a1_context.course_version_id)
    assert course_version is not None
    a1_1_context = BuildContext(
        config=a1_1_config,
        config_hash=compute_config_hash(a1_1_config),
        course_version=course_version,
        course_version_id=course_version.id,
        section_code="A1_1",
    )
    build_seeded_section(db_session=db_session, context=a1_1_context)

    stats = build_tile_sets(db_session, context=a1_1_context)

    assert stats.tile_sets_created == 0
    payload_count_after = int(db_session.scalar(select(func.count()).select_from(ItemSentenceTiles)) or 0)
    assert payload_count_after == payload_count_before
