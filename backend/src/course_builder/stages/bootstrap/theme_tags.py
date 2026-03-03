from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.queries.bootstrap import BootstrapQueries
from course_builder.runtime.models import BuildContext, BuildStep
from domain.content.models import ThemeTag


@dataclass(frozen=True, slots=True)
class ThemeTagImportStats:
    theme_tags_created: int


def import_theme_tags(db: Session, *, context: BuildContext) -> ThemeTagImportStats:
    q = BootstrapQueries(db, context.course_version_id, context.section_code)
    configured_themes = list(context.config.themes.tags)
    configured_codes = [theme.code for theme in configured_themes]
    existing_theme_tags = q.list_existing_theme_tags_by_code(codes=configured_codes)
    theme_tags: list[ThemeTag] = []

    for theme in configured_themes:
        existing_theme_tag = existing_theme_tags.get(theme.code)
        if existing_theme_tag is None:
            theme_tags.append(
                ThemeTag(
                    course_version_id=context.course_version_id,
                    code=theme.code,
                    name=theme.name,
                )
            )
            continue
        if existing_theme_tag.name != theme.name:
            msg = f"Theme tag definition conflict for {theme.code!r}: existing catalog entry does not match config"
            raise ValueError(msg)

    if not theme_tags:
        return ThemeTagImportStats(theme_tags_created=0)

    db.add_all(theme_tags)
    db.commit()
    return ThemeTagImportStats(theme_tags_created=len(theme_tags))


class ImportThemeTagsStep(BuildStep):
    name = "import_theme_tags"

    @override
    def run(self, *, db: Session, context: BuildContext) -> ThemeTagImportStats:
        return import_theme_tags(db, context=context)
