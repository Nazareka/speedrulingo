from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.llm.anchored_word_generation.models import (
    AnchoredWordGenerationResult,
    PreparedAnchoredWordGenerationInput,
)
from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.mechanical_word_generation.models import (
    MechanicalWordGenerationResult,
    PreparedMechanicalWordGenerationInput,
)
from course_builder.llm.pattern_vocab_generation.models import (
    PatternVocabGenerationResult,
    PreparedPatternVocabGenerationInput,
)


class PreparedPatternRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_code: str
    mechanical_batches: list[PreparedMechanicalWordGenerationInput] = Field(default_factory=list)
    anchored_batches: list[PreparedAnchoredWordGenerationInput] = Field(default_factory=list)
    lexical_input: PreparedPatternVocabGenerationInput | None = None


class PatternRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_code: str
    mechanical_results: list[MechanicalWordGenerationResult] = Field(default_factory=list)
    anchored_results: list[AnchoredWordGenerationResult] = Field(default_factory=list)
    lexical_result: PatternVocabGenerationResult | None = None


class MasterPatternVocabGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pattern_results: list[PatternRunResult] = Field(default_factory=list)


class PreparedMasterPatternVocabGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    existing_words: list[ExistingWordPromptInfo] = Field(default_factory=list)
    prepared_patterns: list[PreparedPatternRun] = Field(default_factory=list)
