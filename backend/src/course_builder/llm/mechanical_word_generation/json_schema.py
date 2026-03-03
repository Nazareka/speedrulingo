from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.lexicon import LexemePos
from course_builder.llm.core.structured_output import build_response_format


class MechanicalWordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    canonical_writing_ja: str = Field(alias="l", min_length=1)
    reading_kana: str = Field(alias="r", min_length=1)
    pos: LexemePos = Field(alias="o")
    gloss_primary_en: str = Field(alias="g", min_length=1)
    gloss_alternatives_en: list[str] = Field(alias="ga", default_factory=list, max_length=2)
    usage_note_en: str | None = Field(alias="u", default=None)


class MechanicalWordBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[MechanicalWordPayload] = Field(alias="i")


def build_mechanical_word_generation_response_format(*, item_count: int) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "i": {
                "type": "array",
                "minItems": item_count,
                "maxItems": item_count,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "l": {"type": "string", "minLength": 1, "description": "Requested Japanese lemma."},
                        "r": {"type": "string", "minLength": 1, "description": "Requested kana reading."},
                        "o": {"type": "string", "minLength": 1, "description": "Requested part of speech."},
                        "g": {"type": "string", "minLength": 1, "description": "Short clean primary gloss."},
                        "ga": {"type": "array", "maxItems": 2, "items": {"type": "string"}},
                        "u": {"type": ["string", "null"]},
                    },
                },
            }
        },
    }
    return build_response_format(name="mechanical_word_out", schema=schema)
