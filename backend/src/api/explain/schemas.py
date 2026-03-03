from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sentence_id: str
    token_surface: str = Field(min_length=1)


class SentenceTokenDTO(BaseModel):
    token_index: int
    surface: str
    lemma: str | None
    reading: str | None
    pos: str | None
    hints: list[str]


class ExplainResponse(BaseModel):
    sentence_id: str
    sentence_ja: str
    sentence_en: str
    tokens: list[SentenceTokenDTO]
    matching_tokens: list[SentenceTokenDTO]


class SentenceTokensResponse(BaseModel):
    sentence_id: str
    sentence_ja: str
    sentence_en: str
    tokens: list[SentenceTokenDTO]


class KanjiLessonSummary(BaseModel):
    lesson_id: str
    unit_id: str
    unit_order_index: int
    lesson_order_index: int
    state: str
    kanji_chars: list[str]


class KanjiLessonsResponse(BaseModel):
    lessons: list[KanjiLessonSummary]


class KanjiUsageRow(BaseModel):
    lesson_id: str
    unit_id: str
    unit_order_index: int
    lesson_order_index: int
    example_word_ja: str
    example_reading: str | None
    meaning_en: str
    is_learned: bool


class KanjiDetailResponse(BaseModel):
    kanji_char: str
    primary_meaning: str | None
    usages: list[KanjiUsageRow]
