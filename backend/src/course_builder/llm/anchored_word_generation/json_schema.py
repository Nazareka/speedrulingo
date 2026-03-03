from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.lexicon import LexemePos
from course_builder.llm.core.structured_output import build_response_format


class AnchoredWordExamplePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ja_text: str = Field(alias="j", min_length=1)
    en_text: str = Field(alias="e", min_length=1)


class AnchoredWordPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    canonical_writing_ja: str = Field(alias="l", min_length=1)
    reading_kana: str = Field(alias="r", min_length=1)
    gloss_primary_en: str = Field(alias="g", min_length=1)
    gloss_alternatives_en: list[str] = Field(alias="ga", default_factory=list, max_length=2)
    usage_note_en: str | None = Field(alias="u", default=None)
    pos: LexemePos = Field(alias="o")
    example_sentences: list[AnchoredWordExamplePayload] = Field(alias="x", min_length=2, max_length=2)


class AnchoredWordBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[AnchoredWordPayload] = Field(alias="i")


def build_anchored_word_generation_response_format(*, item_count: int) -> dict[str, object]:
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
                        "g": {"type": "string", "minLength": 1, "description": "Short clean primary English gloss."},
                        "ga": {
                            "type": "array",
                            "maxItems": 2,
                            "items": {"type": "string"},
                            "description": "Up to two useful alternate glosses.",
                        },
                        "u": {"type": ["string", "null"], "description": "Optional usage note."},
                        "o": {"type": "string", "minLength": 1, "description": "Requested part of speech."},
                        "x": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 2,
                            "description": "Exactly two example sentences.",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "j": {"type": "string", "minLength": 1, "description": "Japanese sentence."},
                                    "e": {"type": "string", "minLength": 1, "description": "English translation."},
                                },
                            },
                        },
                    },
                },
            }
        },
    }
    return build_response_format(name="anchored_word_out", schema=schema)
