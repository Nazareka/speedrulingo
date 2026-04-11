from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfig, CourseBuildConfigLoader
from course_builder.engine.models import (
    BuildContext,
    BuildStep,
    compute_config_hash,
)
from course_builder.engine.persistence import create_draft_build_row
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.test_config_source import TEST_CONFIG_YAML, write_config


def load_test_config(
    tmp_path: Path,
    *,
    content: str = TEST_CONFIG_YAML,
    section_code: str = "PRE_A1",
) -> CourseBuildConfig:
    return CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, content), section_code=section_code)


def create_test_build_context(
    db_session: Session,
    tmp_path: Path,
    *,
    content: str = TEST_CONFIG_YAML,
    build_version: int = 1,
    section_code: str = "PRE_A1",
) -> BuildContext:
    config = load_test_config(tmp_path, content=content, section_code=section_code)
    config_hash = compute_config_hash(config)
    course_version = create_draft_build_row(
        db_session,
        config=config,
        build_version=build_version,
        config_hash=config_hash,
    )
    return BuildContext(
        config=config,
        config_hash=config_hash,
        course_version=course_version,
        course_version_id=course_version.id,
        section_code=section_code,
    )


def load_built_test_config(
    tmp_path: Path,
    *,
    updates: dict[tuple[str | int, ...], object] | None = None,
    appends: dict[tuple[str | int, ...], list[object]] | None = None,
) -> CourseBuildConfig:
    return load_test_config(tmp_path, content=build_test_config_yaml(updates=updates, appends=appends))


class _CommitDeferredSession:
    def __init__(self, session: Session) -> None:
        self._session = session

    def commit(self) -> None:
        self._session.flush()

    def rollback(self) -> None:
        self._session.rollback()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)


class CourseBuildTestRunner:
    def __init__(self, *, steps: Sequence[BuildStep]) -> None:
        self._steps = tuple(steps)

    def run(
        self,
        *,
        db: Session,
        config: CourseBuildConfig,
        build_version: int = 1,
    ) -> BuildContext:
        config_hash = compute_config_hash(config)
        course_version = create_draft_build_row(
            db,
            config=config,
            build_version=build_version,
            config_hash=config_hash,
        )
        context = BuildContext(
            config=config,
            config_hash=config_hash,
            course_version=course_version,
            course_version_id=course_version.id,
            section_code=config.current_section_code,
        )

        for step in self._steps:
            savepoint = db.begin_nested()
            test_db = _CommitDeferredSession(db)
            try:
                step.run(db=cast(Session, test_db), context=context)
                savepoint.commit()
                db.commit()
            except Exception:
                with suppress(ResourceClosedError):
                    savepoint.rollback()
                db.rollback()
                raise

        return context
