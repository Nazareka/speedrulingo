from __future__ import annotations

from dataclasses import dataclass
from typing import override

from sqlalchemy.orm import Session

from course_builder.runtime.models import BuildContext, BuildStep
from course_builder.stages.bootstrap.bootstrap_seed_words import insert_bootstrap_seed_words
from course_builder.stages.bootstrap.pattern_catalog import import_pattern_catalog
from course_builder.stages.bootstrap.sections import import_section_config
from course_builder.stages.bootstrap.theme_tags import import_theme_tags


@dataclass(frozen=True, slots=True)
class BootstrapCatalogStageStats:
    theme_tags_created: int
    patterns_created: int
    sections_created: int
    section_theme_links_created: int
    section_pattern_links_created: int
    words_created: int
    section_words_created: int


def run_bootstrap_catalog_stage(db: Session, *, context: BuildContext) -> BootstrapCatalogStageStats:
    theme_stats = import_theme_tags(db, context=context)
    pattern_stats = import_pattern_catalog(db, context=context)
    section_stats = import_section_config(db, context=context)
    bootstrap_stats = insert_bootstrap_seed_words(db, context=context)
    return BootstrapCatalogStageStats(
        theme_tags_created=theme_stats.theme_tags_created,
        patterns_created=pattern_stats.patterns_created,
        sections_created=section_stats.sections_created,
        section_theme_links_created=section_stats.section_theme_links_created,
        section_pattern_links_created=section_stats.section_pattern_links_created,
        words_created=bootstrap_stats.words_created,
        section_words_created=bootstrap_stats.section_words_created,
    )


class BootstrapCatalogStage(BuildStep):
    name = "bootstrap_catalog"

    @override
    def run(self, *, db: Session, context: BuildContext) -> BootstrapCatalogStageStats:
        return run_bootstrap_catalog_stage(db, context=context)
