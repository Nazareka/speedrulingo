"""Pydantic and TypedDict shapes for course build runs (inputs and summaries).

Shared by ``engine`` orchestration, ``build_runs`` persistence, and ``workflows`` DBOS entrypoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BuildRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    config: Path
    build_version: int = Field(ge=1)
    section_code: str | None = None
    all_stages: bool = True
    all_sections: bool = False

    @model_validator(mode="after")
    def validate_scope(self) -> BuildRequest:
        if self.all_sections and self.section_code is not None:
            msg = "--section-code must not be provided when --all-sections is used"
            raise ValueError(msg)
        if not self.all_sections and self.section_code is None:
            msg = "--section-code is required unless --all-sections is used"
            raise ValueError(msg)
        return self


def build_request(
    *,
    config: str | Path,
    build_version: int,
    section_code: str | None = None,
    all_stages: bool = True,
    all_sections: bool = False,
) -> BuildRequest:
    return BuildRequest(
        config=Path(config),
        build_version=build_version,
        section_code=section_code,
        all_stages=all_stages,
        all_sections=all_sections,
    )


class SectionBuildSummary(TypedDict):
    build_run_id: str
    build_version: int
    section_code: str
    course_version_id: str | None
    completed_stage: str | None
    completed_stage_index: int | None
    remaining_stage_count: int
    ran_stage_count: int
    ran_stages: list[str]
    was_noop: bool


class AllSectionsBuildSummary(TypedDict):
    build_run_id: str
    build_version: int
    ran_section_count: int
    ran_sections: list[SectionBuildSummary]
    last_section: SectionBuildSummary | None
    was_noop: bool


class SectionSentenceAudioSummary(TypedDict):
    build_run_id: str
    source_section_build_run_id: str
    build_version: int
    section_code: str
    total_sentence_count: int
    generated_sentence_count: int
    reused_sentence_count: int
    failed_sentence_count: int


class SectionWordAudioSummary(TypedDict):
    build_run_id: str
    source_section_build_run_id: str
    build_version: int
    section_code: str
    total_word_count: int
    generated_word_count: int
    reused_word_count: int
    failed_word_count: int
