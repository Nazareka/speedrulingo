from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HintSpan(BaseModel):
    token_start: int
    token_end: int
    hint_text: str
    hint_kind: str


class SentenceTokenPreview(BaseModel):
    token_index: int
    surface: str
    lemma: str | None
    reading: str | None
    pos: str | None
    hints: list[str] = []


class LessonItemResponse(BaseModel):
    item_id: str
    lesson_id: str
    lesson_kind: str
    item_type: Literal["word_choice", "sentence_tiles", "kanji_kana_match"]
    order_index: int
    cursor: int
    total_items: int
    is_last_item: bool
    prompt_lang: str
    answer_lang: str
    prompt_text: str
    sentence_id: str | None
    sentence_ja_tokens: list[SentenceTokenPreview]
    sentence_ja_hints: list[HintSpan]
    sentence_en_tokens: list[SentenceTokenPreview]
    answer_tiles: list[str]


class SubmittedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    user_answer: str = Field(min_length=1)


class SubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[SubmittedAnswer] = Field(min_length=1)


class ItemResult(BaseModel):
    item_id: str
    expected_answer: str
    user_answer: str
    is_correct: bool


class SubmitResponse(BaseModel):
    lesson_id: str
    lesson_kind: str
    score: float
    correct_items: int
    total_items: int
    passed: bool
    progress_state: str
    item_results: list[ItemResult]
