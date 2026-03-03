from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from course_builder.runtime.models import BuildContext, BuildStep, compute_config_hash
from course_builder.runtime.persistence import create_draft_build_row
from domain.content.models import CourseVersion, ThemeTag
from tests.helpers.builder import CourseBuildTestRunner, load_test_config


def test_create_draft_build_row_persists_expected_metadata(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    config_hash = compute_config_hash(config)

    draft = create_draft_build_row(
        db_session,
        config=config,
        config_hash=config_hash,
    )

    persisted = db_session.scalar(select(CourseVersion).where(CourseVersion.id == draft.id))
    assert persisted is not None
    assert persisted.code == "en-ja"
    assert persisted.version == 1
    assert persisted.build_version == 1
    assert persisted.status == "draft"
    assert persisted.config_version == "test_config_v1"
    assert persisted.config_hash == config_hash


@dataclass
class RecordingStep(BuildStep):
    name: str
    calls: list[str]

    def run(self, *, db: Session, context: BuildContext) -> None:
        _ = db
        self.calls.append(f"{self.name}:{context.course_version_id}")


@dataclass
class FailingStep(BuildStep):
    name: str

    def run(self, *, db: Session, context: BuildContext) -> None:
        _ = db
        _ = context
        msg = "boom"
        raise RuntimeError(msg)


@dataclass
class InsertThemeTagStep(BuildStep):
    name: str
    code: str

    def run(self, *, db: Session, context: BuildContext) -> None:
        db.add(
            ThemeTag(
                course_version_id=context.course_version_id,
                code=self.code,
                name=self.code,
            )
        )
        db.commit()


@dataclass
class InsertThenFailStep(BuildStep):
    name: str
    code: str

    def run(self, *, db: Session, context: BuildContext) -> None:
        db.add(
            ThemeTag(
                course_version_id=context.course_version_id,
                code=self.code,
                name=self.code,
            )
        )
        db.commit()
        msg = "boom"
        raise RuntimeError(msg)


def test_test_runner_runs_steps_in_order(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    calls: list[str] = []
    runner = CourseBuildTestRunner(
        steps=[
            RecordingStep(name="step_one", calls=calls),
            RecordingStep(name="step_two", calls=calls),
        ]
    )

    context = runner.run(db=db_session, config=config)

    assert len(calls) == 2
    assert calls == [f"step_one:{context.course_version_id}", f"step_two:{context.course_version_id}"]


def test_test_runner_stops_after_step_failure(db_session: Session, tmp_path: Path) -> None:
    config = load_test_config(tmp_path)
    runner = CourseBuildTestRunner(
        steps=[
            InsertThemeTagStep(name="step_one", code="THEME_OK"),
            InsertThenFailStep(name="step_two", code="THEME_FAIL"),
            InsertThemeTagStep(name="step_three", code="THEME_LATE"),
        ]
    )

    with pytest.raises(RuntimeError, match="boom"):
        runner.run(db=db_session, config=config)

    assert db_session.scalar(select(func.count()).select_from(CourseVersion)) == 1
    persisted_theme_codes = list(
        db_session.scalars(
            select(ThemeTag.code).where(ThemeTag.course_version_id == db_session.scalar(select(CourseVersion.id)))
        )
    )
    assert persisted_theme_codes == ["THEME_OK"]
