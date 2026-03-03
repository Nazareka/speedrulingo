from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.content.models import Pattern, Section, ThemeTag, Unit


class CourseVersionQueries:
    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        overridden_names = sorted(
            name
            for name, value in CourseVersionQueries.__dict__.items()
            if _is_reserved_query_method(name=name, value=value) and name in cls.__dict__
        )
        if overridden_names:
            names = ", ".join(overridden_names)
            msg = f"{cls.__name__} cannot override shared query methods from CourseVersionQueries: {names}"
            raise TypeError(msg)

    def __init__(self, db: Session, course_version_id: str, section_code: str) -> None:
        self.db = db
        self.course_version_id = course_version_id
        self.section_code = section_code

    def get_section(self) -> Section | None:
        return self.db.scalar(
            select(Section)
            .where(
                Section.course_version_id == self.course_version_id,
                Section.code == self.section_code,
            )
            .limit(1)
        )

    def get_section_id(self) -> str | None:
        return self.db.scalar(
            select(Section.id)
            .where(
                Section.course_version_id == self.course_version_id,
                Section.code == self.section_code,
            )
            .limit(1)
        )

    def list_units_for_section(self, *, section_id: str) -> list[Unit]:
        return list(self.db.scalars(select(Unit).where(Unit.section_id == section_id).order_by(Unit.order_index)).all())

    def map_theme_tag_id_by_code(self) -> dict[str, str]:
        return {
            row.code: row.id
            for row in self.db.execute(
                select(ThemeTag.code, ThemeTag.id).where(ThemeTag.course_version_id == self.course_version_id)
            )
        }

    def list_existing_theme_tags_by_code(self, *, codes: list[str]) -> dict[str, ThemeTag]:
        if not codes:
            return {}
        return {
            theme_tag.code: theme_tag
            for theme_tag in self.db.scalars(
                select(ThemeTag).where(
                    ThemeTag.course_version_id == self.course_version_id,
                    ThemeTag.code.in_(codes),
                )
            )
        }

    def map_pattern_id_by_code(self) -> dict[str, str]:
        return {
            row.code: row.id
            for row in self.db.execute(
                select(Pattern.code, Pattern.id).where(Pattern.course_version_id == self.course_version_id)
            ).all()
        }


def _is_reserved_query_method(*, name: str, value: object) -> bool:
    if name.startswith("_"):
        return False
    return callable(value)
