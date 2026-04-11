from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.engine.models import BuildContext, BuildStep
from course_builder.queries.bootstrap import BootstrapQueries
from domain.content.models import (
    Section,
    SectionPatternLink,
    SectionThemeLink,
)


@dataclass(frozen=True, slots=True)
class SectionImportStats:
    sections_created: int
    section_theme_links_created: int
    section_pattern_links_created: int


def import_section_config(db: Session, *, context: BuildContext) -> SectionImportStats:
    q = BootstrapQueries(db, context.course_version_id, context.section_code)
    theme_code_to_id = q.map_theme_tag_id_by_code()
    pattern_code_to_id = q.map_pattern_id_by_code()

    current_section = context.config.current_section
    section = Section(
        course_version_id=context.course_version_id,
        code=current_section.code,
        order_index=context.config.sections.index_of(context.section_code) + 1,
        title=current_section.title,
        description=current_section.description,
        generation_description=current_section.generation_description,
        target_unit_count=0,
        target_new_word_count=0,
    )
    db.add(section)
    db.flush()

    section_theme_links = [
        SectionThemeLink(
            section_id=section.id,
            theme_tag_id=theme_code_to_id[theme_code],
        )
        for theme_code in current_section.primary_themes + current_section.secondary_themes
    ]
    section_pattern_links = [
        SectionPatternLink(
            section_id=section.id,
            pattern_id=pattern_code_to_id[pattern_code],
            role="introduce",
        )
        for pattern_code in current_section.patterns_scope
    ]
    db.add_all(section_theme_links)
    db.add_all(section_pattern_links)
    db.commit()

    return SectionImportStats(
        sections_created=1,
        section_theme_links_created=len(section_theme_links),
        section_pattern_links_created=len(section_pattern_links),
    )


class ImportSectionConfigStep(BuildStep):
    name = "import_section_config"

    @override
    def run(self, *, db: Session, context: BuildContext) -> SectionImportStats:
        q = BootstrapQueries(db, context.course_version_id, context.section_code)
        if q.exists_current_section():
            msg = (
                f"Section config already exists for course_version_id={context.course_version_id} "
                f"section_code={context.section_code}"
            )
            raise ValueError(msg)
        if not q.exists_theme_tags():
            raise ValueError("Theme tags must be imported before section config")
        if not q.exists_patterns():
            msg = f"Pattern catalog must be imported before section config for course_version_id={context.course_version_id}"
            raise ValueError(msg)
        return import_section_config(db, context=context)
