from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.unit_metadata_generation.json_schema import UnitMetadataPayload


class PreparedUnitLessonInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_index: int = Field(ge=1)
    lesson_kind: str = Field(min_length=1)
    target_item_count: int = Field(ge=0)
    target_word_lemmas: list[str] = Field(default_factory=list)
    target_pattern_code: str | None = None
    available_word_lemmas: list[str] = Field(default_factory=list)
    available_pattern_codes: list[str] = Field(default_factory=list)


class PreparedUnitInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_index: int = Field(ge=1)
    lessons: list[PreparedUnitLessonInput] = Field(default_factory=list)


class PreparedUnitMetadataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    section_title: str = Field(min_length=1)
    section_generation_description: str = Field(min_length=1)
    section_theme_codes: list[str] = Field(default_factory=list)
    word_prompt_info_by_lemma: dict[str, ExistingWordPromptInfo] = Field(default_factory=dict)
    pattern_templates_by_code: dict[str, list[str]] = Field(default_factory=dict)
    units: list[PreparedUnitInput] = Field(default_factory=list)


class UnitMetadataGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    metadata_items: list[UnitMetadataPayload]
    iterations: int = Field(ge=0)
