from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.config import AnchorWordRefConfig
from course_builder.llm.anchored_word_generation.json_schema import AnchoredWordPayload
from course_builder.llm.core.models import ExistingWordPromptInfo


class PreparedAnchoredWordGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    targets: list[AnchorWordRefConfig] = Field(min_length=1)
    existing_words: list[ExistingWordPromptInfo] = Field(default_factory=list)
    allowed_pattern_codes: list[str] = Field(default_factory=list)


class AnchoredWordGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    words: list[AnchoredWordPayload] = Field(default_factory=list)
    iterations: int = Field(default=0, ge=0)


__all__ = [
    "AnchoredWordGenerationResult",
    "PreparedAnchoredWordGenerationInput",
]
