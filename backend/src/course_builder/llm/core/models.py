from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExistingWordPromptInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_writing_ja: str
    reading_kana: str
    gloss_primary_en: str
    gloss_alternatives_en: list[str] = Field(default_factory=list)
    usage_note_en: str | None = None
    pos: str
