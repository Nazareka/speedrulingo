from __future__ import annotations

from course_builder.engine.models import BuildStep
from course_builder.stages.assembly.stage import ContentAssemblyStage
from course_builder.stages.bootstrap.stage import BootstrapCatalogStage
from course_builder.stages.planning.normal_lesson_planning import NormalLessonPlanningStage
from course_builder.stages.planning.pattern_vocab_generation import PatternVocabGenerationStage
from course_builder.stages.planning.section_curriculum_planning import SectionCurriculumPlanningStage
from course_builder.stages.planning.unit_metadata_generation import UnitMetadataGenerationStage
from course_builder.stages.release.stage import ReleaseStage

BUILD_STAGES: tuple[BuildStep, ...] = (
    BootstrapCatalogStage(),
    PatternVocabGenerationStage(),
    SectionCurriculumPlanningStage(),
    UnitMetadataGenerationStage(),
    NormalLessonPlanningStage(),
    ContentAssemblyStage(),
    ReleaseStage(),
)


def get_registered_build_stages() -> tuple[BuildStep, ...]:
    return BUILD_STAGES
