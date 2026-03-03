from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from course_builder.lexicon import LexemePos
from course_builder.llm.core.structured_output import build_response_format


class WordExampleSentencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ja_text: str = Field(alias="j", min_length=1)
    en_text: str = Field(alias="e", min_length=1)


class WordBatchItemPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    canonical_writing_ja: str = Field(alias="l", min_length=1)
    reading_kana: str = Field(alias="r", min_length=1)
    gloss_primary_en: str = Field(alias="g", min_length=1)
    gloss_alternatives_en: list[str] = Field(alias="ga", default_factory=list, max_length=2)
    usage_note_en: str | None = Field(alias="u", default=None)
    pos: LexemePos = Field(alias="o")
    example_sentences: list[WordExampleSentencePayload] = Field(alias="x", min_length=2, max_length=2)


class WordBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    items: list[WordBatchItemPayload] = Field(alias="i")


def _enum_schema(*, values: list[str]) -> dict[str, object]:
    return {"type": "string", "enum": list(dict.fromkeys(values))}


def build_pattern_vocab_response_format(
    *,
    min_item_count: int,
    max_item_count: int,
) -> dict[str, object]:
    if min_item_count > max_item_count:
        raise ValueError("min_item_count must be <= max_item_count")
    item_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "l": {
                "type": "string",
                "minLength": 1,
                "description": "Canonical Japanese lemma for the new word to add to the current section inventory.",
            },
            "r": {
                "type": "string",
                "minLength": 1,
                "description": "Kana reading for the lemma. Use kana only, without spaces.",
            },
            "g": {
                "type": "string",
                "minLength": 1,
                "description": "Short clean primary English gloss. Do not use slashes or semicolons.",
            },
            "ga": {
                "type": "array",
                "maxItems": 2,
                "items": {"type": "string"},
                "description": "Up to two genuinely useful alternate English glosses.",
            },
            "u": {
                "type": ["string", "null"],
                "description": "Optional nuance or restricted-usage note in English.",
            },
            "o": {
                **_enum_schema(values=LexemePos.teachable_values()),
                "description": "Normalized primary part of speech label for the word.",
            },
            "x": {
                "type": "array",
                "minItems": 2,
                "maxItems": 2,
                "description": "Exactly two example sentences for the generated word. USE ONLY EXISTING WORDS AND PATTERNS",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "j": {
                            "type": "string",
                            "minLength": 1,
                            "description": "One natural Japanese example sentence that uses the generated word.",
                        },
                        "e": {
                            "type": "string",
                            "minLength": 1,
                            "description": "English translation for the example sentence.",
                        },
                    },
                },
            },
        },
    }
    schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "i": {
                "type": "array",
                "minItems": min_item_count,
                "maxItems": max_item_count,
                "items": item_schema,
            }
        },
    }
    return build_response_format(name="word_out", schema=schema)
