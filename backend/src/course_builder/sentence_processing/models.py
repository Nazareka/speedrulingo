from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class VocabItem:
    word_id: str | None
    canonical_writing_ja: str
    reading_kana: str
    gloss_primary_en: str
    gloss_alternatives_en: tuple[str, ...]
    usage_note_en: str | None
    pos: str


@dataclass(frozen=True, slots=True)
class SurfaceEntry:
    surface: str
    reading: str | None
    vocab_items: tuple[VocabItem, ...]
    match_kind: Literal["exact", "generated"]


@dataclass(frozen=True, slots=True)
class ParsedToken:
    surface: str
    reading: str | None
    vocab_items: tuple[VocabItem, ...]
    match_kind: Literal["exact", "generated"]


@dataclass(frozen=True, slots=True)
class HintChunk:
    text: str
    token_start: int
    token_end: int
    vocab_items: tuple[VocabItem, ...]
    hints: tuple[str, ...]
    lemma: str | None
    reading: str | None
    pos: str | None


@dataclass(frozen=True, slots=True)
class ParsedSentenceResult:
    normalized_sentence: str
    tokens: tuple[ParsedToken, ...]
    chunks: tuple[HintChunk, ...]


@dataclass(frozen=True, slots=True)
class EnglishToken:
    surface: str
    lemma: str
    pos: str
