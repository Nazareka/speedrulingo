from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.stages.release.publish_logic import publish_course_version
from course_builder.stages.release.section_acceptance_checks import run_section_acceptance_checks


@dataclass(frozen=True, slots=True)
class ReleaseStageStats:
    course_version_id: str
    accepted: bool
    unit_count: int
    lesson_count: int
    item_count: int
    archived_course_versions: int
    published: bool
    final_status: str


def run_release_stage(db: Session, *, context: BuildContext) -> ReleaseStageStats:
    acceptance_stats = run_section_acceptance_checks(db, context=context)
    publish_stats = publish_course_version(db, context=context)
    return ReleaseStageStats(
        course_version_id=publish_stats.course_version_id,
        accepted=acceptance_stats.accepted,
        unit_count=acceptance_stats.unit_count,
        lesson_count=acceptance_stats.lesson_count,
        item_count=acceptance_stats.item_count,
        archived_course_versions=publish_stats.archived_course_versions,
        published=publish_stats.published,
        final_status=publish_stats.final_status,
    )


class ReleaseStage(BuildStep):
    name = "release"

    @override
    def run(self, *, db: Session, context: BuildContext) -> ReleaseStageStats:
        return run_release_stage(db, context=context)
