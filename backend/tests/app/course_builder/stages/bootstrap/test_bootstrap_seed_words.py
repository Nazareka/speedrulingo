from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.stages.bootstrap.bootstrap_seed_words import (
    BootstrapWordInsertStats,
    InsertBootstrapSeedWordsStep,
    insert_bootstrap_seed_words,
)
from course_builder.stages.bootstrap.pattern_catalog import ImportPatternCatalogStep, import_pattern_catalog
from course_builder.stages.bootstrap.sections import ImportSectionConfigStep, import_section_config
from course_builder.stages.bootstrap.theme_tags import ImportThemeTagsStep, import_theme_tags
from domain.content.models import SectionWord, Word
from tests.helpers.builder import CourseBuildTestRunner, create_test_build_context, load_test_config

build_context = create_test_build_context


def test_insert_bootstrap_seed_words_persists_words_and_section_scope(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)

    stats = insert_bootstrap_seed_words(db_session, context=context)

    assert stats == BootstrapWordInsertStats(words_created=8, section_words_created=6)
    persisted_words = db_session.scalars(
        select(Word).where(Word.course_version_id == context.course_version_id).order_by(Word.intro_order)
    ).all()
    assert [word.canonical_writing_ja for word in persisted_words] == [
        "は",
        "です",
        "こんにちは",
        "ありがとう",
        "私",
        "これ",
        "学生",
        "本",
    ]
    assert persisted_words[2].is_bootstrap_seed is True
    assert persisted_words[2].is_safe_pool is False
    assert persisted_words[3].is_safe_pool is False

    persisted_section_words = db_session.scalars(select(SectionWord.role).order_by(SectionWord.word_id)).all()
    assert sorted(persisted_section_words) == ["new", "new", "new", "new", "new", "new"]


def test_insert_bootstrap_seed_words_requires_section_config(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)

    with pytest.raises(ValueError, match="Section config must be imported before bootstrap seed words"):
        InsertBootstrapSeedWordsStep().run(db=db_session, context=context)


def test_insert_bootstrap_seed_words_step_rejects_duplicate_import(db_session: Session, tmp_path: Path) -> None:
    context = build_context(db_session, tmp_path)
    import_theme_tags(db_session, context=context)
    import_pattern_catalog(db_session, context=context)
    import_section_config(db_session, context=context)
    step = InsertBootstrapSeedWordsStep()

    first_stats = step.run(db=db_session, context=context)

    assert first_stats.words_created == 8
    with pytest.raises(ValueError, match="Bootstrap seed words already exist"):
        step.run(db=db_session, context=context)


def test_test_runner_runs_bootstrap_seed_word_insert(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    runner = CourseBuildTestRunner(
        steps=[
            ImportThemeTagsStep(),
            ImportPatternCatalogStep(),
            ImportSectionConfigStep(),
            InsertBootstrapSeedWordsStep(),
        ]
    )

    context = runner.run(db=db_session, config=config)

    persisted_words = db_session.scalars(
        select(Word.canonical_writing_ja)
        .where(Word.course_version_id == context.course_version_id)
        .order_by(Word.intro_order)
    ).all()
    assert persisted_words == ["は", "です", "こんにちは", "ありがとう", "私", "これ", "学生", "本"]
