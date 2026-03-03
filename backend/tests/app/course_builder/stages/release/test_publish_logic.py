from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.runtime.models import BuildContext
from course_builder.stages.release.publish_logic import PublishStats, publish_course_version
from course_builder.stages.release.section_acceptance_checks import run_section_acceptance_checks
from domain.content.models import CourseVersion, Item
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_publish_ready_course
from tests.helpers.scenarios import single_intro_unit_plan_payload

build_context = create_test_build_context
load_config = load_test_config


def publish_test_config() -> str:
    return build_test_config_yaml(
        updates={
            ("course", "version"): 1,
            ("items", "word_translation", "item_count"): 12,
            ("items", "sentence_translation", "item_count"): 12,
            ("items", "review_previous_units", "item_count"): 12,
            ("items", "exam", "item_count"): 12,
        }
    )


def _build_publishable_course(
    db_session: Session,
    *,
    context: BuildContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )


def test_publish_course_version_activates_build_and_archives_previous_active(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_context = build_context(db_session, tmp_path, content=publish_test_config())
    previous_context.course_version.status = "active"
    db_session.commit()

    context = build_context(
        db_session,
        tmp_path,
        content=build_test_config_yaml(
            updates={
                ("course", "version"): 2,
                ("items", "word_translation", "item_count"): 12,
                ("items", "sentence_translation", "item_count"): 12,
                ("items", "review_previous_units", "item_count"): 12,
                ("items", "exam", "item_count"): 12,
            }
        ),
    )
    _build_publishable_course(db_session, context=context, monkeypatch=monkeypatch)

    stats = publish_course_version(db_session, context=context)

    assert stats == PublishStats(
        course_version_id=context.course_version_id,
        archived_course_versions=1,
        published=True,
        final_status="active",
    )

    archived_previous = db_session.get(CourseVersion, previous_context.course_version_id)
    active_current = db_session.get(CourseVersion, context.course_version_id)
    assert archived_previous is not None and archived_previous.status == "archived"
    assert active_current is not None and active_current.status == "active"


def test_publish_course_version_does_not_re_run_acceptance_checks(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=publish_test_config())
    _build_publishable_course(db_session, context=context, monkeypatch=monkeypatch)

    lesson_items = (
        db_session.scalars(select(Item).where(Item.lesson_id == first_item.lesson_id)).all()
        if (first_item := db_session.scalar(select(Item).limit(1))) is not None
        else []
    )
    assert lesson_items
    for item in lesson_items:
        db_session.delete(item)
    db_session.commit()

    with pytest.raises(ValueError, match="has no items"):
        run_section_acceptance_checks(db_session, context=context)

    stats = publish_course_version(db_session, context=context)

    assert stats.published is True


def test_publish_course_version_is_noop_for_already_active_build(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=publish_test_config())
    _build_publishable_course(db_session, context=context, monkeypatch=monkeypatch)

    context.course_version.status = "active"
    db_session.commit()

    stats = publish_course_version(db_session, context=context)

    assert stats == PublishStats(
        course_version_id=context.course_version_id,
        archived_course_versions=0,
        published=False,
        final_status="active",
    )
