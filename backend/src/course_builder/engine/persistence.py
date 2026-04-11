from __future__ import annotations

from sqlalchemy.orm import Session

from course_builder.config import CourseBuildConfig
from domain.content.models import CourseVersion


def create_draft_build_row(
    db: Session,
    *,
    config: CourseBuildConfig,
    build_version: int = 1,
    config_hash: str,
) -> CourseVersion:
    draft = CourseVersion(
        code=config.course.code,
        version=config.course.version,
        build_version=build_version,
        status="draft",
        config_version=config.course.config_version,
        config_hash=config_hash,
    )
    db.add(draft)
    db.flush()
    return draft
