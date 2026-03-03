from __future__ import annotations

import re

JA_FINAL_PUNCTUATION = {"。", "\uff01", "\uff1f", "!", "?"}
JA_IGNORABLE_PUNCTUATION = JA_FINAL_PUNCTUATION | {"、", ",", "・"}
EN_FINAL_PUNCTUATION = {".", "!", "?"}
EN_IGNORABLE_PUNCTUATION = EN_FINAL_PUNCTUATION | {
    ",",
    ";",
    ":",
    '"',
    "\u201c",
    "\u201d",
    "\u2018",
    "(",
    ")",
}


def _normalize_english_abbreviations(text: str) -> str:
    return re.sub(r"\b(?:[A-Za-z]\.){2,}", lambda match: match.group(0).replace(".", ""), text)


def normalize_japanese_sentence(text: str) -> str:
    normalized = "".join(character for character in text if not character.isspace())
    if normalized and normalized[-1] in JA_FINAL_PUNCTUATION:
        normalized = normalized[:-1]
    return normalized


def normalize_english_sentence(text: str) -> str:
    normalized = _normalize_english_abbreviations(text)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if normalized and normalized[-1] in EN_FINAL_PUNCTUATION:
        normalized = normalized[:-1]
    return normalized


def strip_japanese_for_matching(text: str) -> str:
    return "".join(
        character for character in normalize_japanese_sentence(text) if character not in JA_IGNORABLE_PUNCTUATION
    )


def strip_english_for_tiles(text: str) -> str:
    normalized = normalize_english_sentence(text)
    stripped = "".join(character for character in normalized if character not in EN_IGNORABLE_PUNCTUATION)
    return re.sub(r"\s+", " ", stripped).strip()
