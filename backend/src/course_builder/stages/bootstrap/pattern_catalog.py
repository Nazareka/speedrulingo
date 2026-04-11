from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.queries.bootstrap import BootstrapQueries
from domain.content.models import Pattern


@dataclass(frozen=True, slots=True)
class PatternCatalogImportStats:
    patterns_created: int


def import_pattern_catalog(db: Session, *, context: BuildContext) -> PatternCatalogImportStats:
    q = BootstrapQueries(db, context.course_version_id, context.section_code)
    existing_pattern_id_by_code = q.map_pattern_id_by_code()
    next_intro_order = len(existing_pattern_id_by_code) + 1
    patterns_created = 0
    current_pattern_codes = set(context.config.current_section.patterns_scope)
    patterns = [
        Pattern(
            course_version_id=context.course_version_id,
            code=pattern.code,
            name=pattern.name,
            short_description=pattern.short_description,
            intro_order=next_intro_order + index,
            is_bootstrap=pattern.code == "WA_DESU_STATEMENT",
        )
        for index, pattern in enumerate(
            [pattern for pattern in context.config.patterns if pattern.code in current_pattern_codes]
        )
        if pattern.code not in existing_pattern_id_by_code
    ]
    patterns_created = len(patterns)
    db.add_all(patterns)
    db.commit()
    return PatternCatalogImportStats(patterns_created=patterns_created)


class ImportPatternCatalogStep(BuildStep):
    name = "import_pattern_catalog"

    @override
    def run(self, *, db: Session, context: BuildContext) -> PatternCatalogImportStats:
        q = BootstrapQueries(db, context.course_version_id, context.section_code)
        existing_pattern_codes = set(q.map_pattern_id_by_code())
        current_pattern_codes = set(context.config.current_section.patterns_scope)
        if current_pattern_codes.issubset(existing_pattern_codes):
            msg = (
                f"Pattern catalog already exists for course_version_id={context.course_version_id} "
                f"section_code={context.section_code}"
            )
            raise ValueError(msg)
        return import_pattern_catalog(db, context=context)
