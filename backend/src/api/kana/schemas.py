from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class KanaCharacterProgress(BaseModel):
    character_id: str
    char: str
    script: Literal["hiragana", "katakana"]
    group_key: str
    audio_url: str | None = None
    times_seen: int
    target_exposures: int
    state: Literal["locked", "new", "learning", "mastered"]
    # True when a planned lesson exists and this character is a prompt target with no prior exposures.
    is_next_lesson_new: bool = False


class KanaScriptGroup(BaseModel):
    script: Literal["hiragana", "katakana"]
    characters: list[KanaCharacterProgress]


class KanaOverviewResponse(BaseModel):
    scripts: list[KanaScriptGroup]
    current_lesson_id: str | None
    total_characters: int
    mastered_characters: int


class KanaContinueResponse(BaseModel):
    lesson_id: str
    total_items: int


class KanaAnswerOption(BaseModel):
    option_id: str
    char: str
    audio_url: str | None = None


class KanaLessonItemResponse(BaseModel):
    item_id: str
    lesson_id: str
    item_type: Literal["audio_to_kana_choice", "kana_to_audio_choice"]
    order_index: int
    cursor: int
    total_items: int
    is_last_item: bool
    prompt_char: str | None = None
    prompt_audio_url: str | None = None
    answer_options: list[KanaAnswerOption]


class SubmittedKanaAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    option_id: str = Field(min_length=1)


class KanaSubmitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answers: list[SubmittedKanaAnswer] = Field(min_length=1)


class KanaItemResult(BaseModel):
    item_id: str
    expected_option_id: str
    user_option_id: str
    is_correct: bool


class KanaSubmitResponse(BaseModel):
    lesson_id: str
    score: float
    correct_items: int
    total_items: int
    passed: bool
    progress_state: Literal["planned", "abandoned", "completed"]
    item_results: list[KanaItemResult]
