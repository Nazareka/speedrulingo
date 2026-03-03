from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.llm.core.models import ExistingWordPromptInfo
from course_builder.llm.pattern_vocab_generation.json_schema import (
    WordBatchItemPayload,
    WordExampleSentencePayload,
)


class PatternVocabGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    words_created: int = Field(default=0, ge=0)
    section_words_created: int = Field(default=0, ge=0)
    word_theme_links_created: int = Field(default=0, ge=0)
    iterations: int = Field(default=0, ge=0)
    inventory_complete: bool
    example_sentences: list[WordExampleSentencePayload] = Field(default_factory=list)
    generated_words: list[WordBatchItemPayload] = Field(default_factory=list)


class PreparedPatternVocabGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_version_id: str
    min_words: int = Field(ge=0)
    max_words: int = Field(ge=0)
    existing_words: list[ExistingWordPromptInfo] = Field(default_factory=list)
    allowed_pattern_codes: list[str] = Field(default_factory=list)
