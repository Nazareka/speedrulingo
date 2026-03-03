from __future__ import annotations

import re

from course_builder.sentence_processing.chunking import merge_hint_chunks
from course_builder.sentence_processing.models import EnglishToken, ParsedSentenceResult, VocabItem
from course_builder.sentence_processing.normalization import (
    normalize_english_sentence,
    normalize_japanese_sentence,
    strip_japanese_for_matching,
)
from course_builder.sentence_processing.parser import build_surface_index, parse_sentence


def normalize_sentence_texts(*, ja_text: str, en_text: str) -> tuple[str, str]:
    return (normalize_japanese_sentence(ja_text), normalize_english_sentence(en_text))


def build_japanese_sentence_analysis(*, sentence_ja: str, vocab: list[VocabItem]) -> ParsedSentenceResult:
    normalized_sentence = normalize_japanese_sentence(sentence_ja)
    parser_text = strip_japanese_for_matching(sentence_ja)
    parsed_tokens = parse_sentence(
        original_sentence=sentence_ja,
        normalized_sentence=parser_text,
        surface_index=build_surface_index(vocab),
    )
    chunks = merge_hint_chunks(parsed_tokens)
    return ParsedSentenceResult(
        normalized_sentence=normalized_sentence,
        tokens=parsed_tokens,
        chunks=chunks,
    )


def tokenize_english_sentence(text: str) -> tuple[EnglishToken, ...]:
    normalized = normalize_english_sentence(text)
    parts = re.findall(r"[^\W\d_]+(?:['\u2019][^\W\d_]+)?|\d+", normalized)
    return tuple(
        EnglishToken(
            surface=part,
            lemma=part.lower(),
            pos="number" if part.isdigit() else "word",
        )
        for part in parts
    )
