from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext
from course_builder.queries.release import ReleaseQueries
from domain.content.models import CourseVersion


@dataclass(frozen=True, slots=True)
class PublishStats:
    course_version_id: str
    archived_course_versions: int
    published: bool
    final_status: str


def publish_course_version(
    db: Session,
    *,
    context: BuildContext,
) -> PublishStats:
    q = ReleaseQueries(db, context.course_version_id, context.section_code)
    course_version = db.get(CourseVersion, context.course_version_id)
    if course_version is None:
        msg = f"Missing course_version_id={context.course_version_id} before publish"
        raise ValueError(msg)
    if course_version.status == "active":
        return PublishStats(
            course_version_id=course_version.id,
            archived_course_versions=0,
            published=False,
            final_status=course_version.status,
        )
    if course_version.status != "draft":
        msg = f"Only draft or already-active course versions can be published, got status={course_version.status!r}"
        raise ValueError(msg)

    archived_count = 0
    try:
        active_course_versions = q.list_active_course_versions_for_code(
            code=course_version.code,
            exclude_course_version_id=course_version.id,
        )
        for active_course_version in active_course_versions:
            active_course_version.status = "archived"
            archived_count += 1

        course_version.status = "active"
        db.commit()
        db.refresh(course_version)
    except Exception:
        db.rollback()
        raise

    return PublishStats(
        course_version_id=course_version.id,
        archived_course_versions=archived_count,
        published=True,
        final_status=course_version.status,
    )
