from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from course_builder.stages.release.section_acceptance_checks import (
    run_section_acceptance_checks,
)
from domain.content.models import Item, ItemWordChoice, Section
from tests.helpers.builder import create_test_build_context, load_test_config
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.pipeline import build_publish_ready_course
from tests.helpers.scenarios import intro_and_review_unit_plan_payload, single_intro_unit_plan_payload

build_context = create_test_build_context
load_config = load_test_config


def acceptance_test_config() -> str:
    return build_test_config_yaml(
        updates={
            ("lessons", "normal_lessons_per_unit"): 1,
            ("items", "word_translation", "item_count"): 12,
            ("items", "sentence_translation", "item_count"): 12,
            ("items", "review_previous_units", "item_count"): 12,
            ("items", "exam", "item_count"): 12,
        }
    )


def test_run_section_acceptance_checks_accepts_fully_built_section(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=acceptance_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    stats = run_section_acceptance_checks(db_session, context=context)

    section = db_session.scalar(select(Section).where(Section.course_version_id == context.course_version_id).limit(1))
    assert section is not None
    assert stats.section_id == section.id
    assert stats.accepted is True
    assert stats.unit_count >= 1
    assert stats.lesson_count >= 1
    assert stats.item_count >= 1


def test_run_section_acceptance_checks_rejects_underfilled_lesson(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=acceptance_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    lesson_items = (
        db_session.scalars(select(Item).where(Item.lesson_id == first_item.lesson_id)).all()
        if (first_item := db_session.scalar(select(Item).order_by(Item.order_index).limit(1))) is not None
        else []
    )
    assert lesson_items
    for item in lesson_items:
        db_session.delete(item)
    db_session.commit()

    with pytest.raises(ValueError, match="has no items"):
        run_section_acceptance_checks(db_session, context=context)


def test_run_section_acceptance_checks_rejects_item_missing_payload(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=acceptance_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    item = db_session.scalar(select(Item).where(Item.type == "word_choice").limit(1))
    assert item is not None
    payload = db_session.get(ItemWordChoice, item.id)
    assert payload is not None
    db_session.delete(payload)
    db_session.commit()

    with pytest.raises(ValueError, match="missing payload rows"):
        run_section_acceptance_checks(db_session, context=context)


def test_run_section_acceptance_checks_rejects_new_word_without_word_choice_intro(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=acceptance_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[single_intro_unit_plan_payload()],
    )

    payload = db_session.scalar(select(ItemWordChoice).limit(1))
    assert payload is not None
    items = db_session.scalars(select(Item).join(ItemWordChoice, ItemWordChoice.item_id == Item.id).where(ItemWordChoice.word_id == payload.word_id)).all()
    assert items
    for item in items:
        db_session.delete(item)
    db_session.commit()

    with pytest.raises(ValueError, match="new words without any word_choice intro"):
        run_section_acceptance_checks(db_session, context=context)


def test_run_section_acceptance_checks_allows_review_lessons_to_contain_previous_unit_review_pool(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = build_context(db_session, tmp_path, content=acceptance_test_config())
    build_publish_ready_course(
        db_session=db_session,
        context=context,
        monkeypatch=monkeypatch,
        unit_payloads=[intro_and_review_unit_plan_payload()],
    )

    stats = run_section_acceptance_checks(db_session, context=context)

    assert stats.accepted is True
