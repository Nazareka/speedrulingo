from __future__ import annotations

from enum import StrEnum

KANJI_RANGES = (
    (0x4E00, 0x9FFF),
    (0x3400, 0x4DBF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2EBEF),
)
HIRAGANA_RANGE = (0x3040, 0x309F)
KATAKANA_RANGE = (0x30A0, 0x30FF)
HIRAGANA_TO_KATAKANA_SOURCE_RANGE = (0x3041, 0x3096)
HIRAGANA_TO_KATAKANA_OFFSET = 0x60


class LexemePos(StrEnum):
    NOUN = "noun"
    PROPER_NOUN = "proper_noun"
    PRONOUN = "pronoun"
    DETERMINER = "determiner"
    VERB = "verb"
    ADJECTIVE_I = "adjective_i"
    ADJECTIVE_NA = "adjective_na"
    ADVERB = "adverb"
    PARTICLE = "particle"
    AUXILIARY = "auxiliary"
    COPULA = "copula"
    SUFFIX = "suffix"
    CONJUNCTION = "conjunction"
    INTERJECTION = "interjection"
    EXPRESSION = "expression"

    @classmethod
    def mechanical_values(cls) -> set[str]:
        return {
            cls.PARTICLE.value,
            cls.AUXILIARY.value,
            cls.COPULA.value,
            cls.SUFFIX.value,
            cls.CONJUNCTION.value,
        }

    @classmethod
    def teachable_values(cls) -> list[str]:
        return [pos.value for pos in cls if pos.value not in cls.mechanical_values()]

    @classmethod
    def word_choice_intro_values(cls) -> set[str]:
        return {
            cls.EXPRESSION.value,
            cls.PROPER_NOUN.value,
            cls.NOUN.value,
            cls.PRONOUN.value,
        }

    @classmethod
    def is_mechanical(cls, pos: str | LexemePos) -> bool:
        return str(pos) in cls.mechanical_values()

    @classmethod
    def is_support(cls, pos: str | LexemePos) -> bool:
        return cls.is_mechanical(pos)


def is_kanji(character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in KANJI_RANGES)


def is_hiragana(character: str) -> bool:
    codepoint = ord(character)
    return HIRAGANA_RANGE[0] <= codepoint <= HIRAGANA_RANGE[1]


def is_kana_text(value: str) -> bool:
    allowed_characters = {"ー", "・", "々", "ゝ", "ゞ", "ヽ", "ヾ"}
    for character in value:
        if character in allowed_characters:
            continue
        codepoint = ord(character)
        if HIRAGANA_RANGE[0] <= codepoint <= HIRAGANA_RANGE[1]:
            continue
        if KATAKANA_RANGE[0] <= codepoint <= KATAKANA_RANGE[1]:
            continue
        return False
    return True


def extract_kanji_chars(text: str | None) -> list[str]:
    if not text:
        return []
    return [char for char in text if is_kanji(char)]
