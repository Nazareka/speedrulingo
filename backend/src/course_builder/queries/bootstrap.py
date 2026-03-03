from __future__ import annotations

from sqlalchemy import select

from course_builder.queries.shared import CourseVersionQueries
from domain.content.models import Pattern, Section, SectionWord, ThemeTag


class BootstrapQueries(CourseVersionQueries):
    def exists_theme_tags(self) -> bool:
        return (
            self.db.scalar(select(ThemeTag.id).where(ThemeTag.course_version_id == self.course_version_id).limit(1))
            is not None
        )

    def exists_patterns(self) -> bool:
        return (
            self.db.scalar(select(Pattern.id).where(Pattern.course_version_id == self.course_version_id).limit(1))
            is not None
        )

    def exists_current_section(self) -> bool:
        return (
            self.db.scalar(
                select(Section.id)
                .where(
                    Section.course_version_id == self.course_version_id,
                    Section.code == self.section_code,
                )
                .limit(1)
            )
            is not None
        )

    def exists_words_for_current_section(self) -> bool:
        section_id = self.get_section_id()
        if section_id is None:
            return False
        return (
            self.db.scalar(select(SectionWord.word_id).where(SectionWord.section_id == section_id).limit(1)) is not None
        )
