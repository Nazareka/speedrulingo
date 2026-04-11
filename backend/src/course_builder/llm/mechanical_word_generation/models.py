from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from core.lexicon import LexemePos
from course_builder.llm.mechanical_word_generation.json_schema import MechanicalWordPayload


class MechanicalLexemePromptInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_writing_ja: str
    reading_kana: str
    pos: LexemePos


class PreparedMechanicalWordGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lexemes: list[MechanicalLexemePromptInfo] = Field(min_length=1)


class MechanicalWordGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    words: list[MechanicalWordPayload] = Field(default_factory=list)
    iterations: int = Field(default=0, ge=0)
