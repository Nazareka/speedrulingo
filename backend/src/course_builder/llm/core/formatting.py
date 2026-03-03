from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import TypedDict

from course_builder.llm.core.models import ExistingWordPromptInfo

WORD_LIST_HEADER = "canonical_writing_ja | reading_kana | gloss_primary_en | pos | gloss_alternatives_en"
TARGET_LEXEME_LIST_HEADER = "canonical_writing_ja | reading_kana | pos"


def normalize_prompt_list(values: Iterable[str]) -> str:
    items = [value for value in values if value]
    return "\n".join(items) if items else "(none)"


def format_prompt_word_line(
    *,
    canonical_writing_ja: str,
    reading_kana: str,
    gloss_primary_en: str,
    gloss_alternatives_en: list[str],
    pos: str | None = None,
) -> str:
    return " | ".join(
        [
            canonical_writing_ja,
            reading_kana,
            gloss_primary_en,
            pos.replace("_", " ") if pos is not None else "",
            ", ".join(gloss_alternatives_en),
        ]
    )


def format_pattern_scope_lines(
    *,
    pattern_templates_by_code: Mapping[str, Sequence[str]],
    allowed_pattern_codes: list[str],
) -> str:
    return normalize_prompt_list(
        f"{code} | templates={'; '.join(pattern_templates_by_code[code])}"
        for code in allowed_pattern_codes
        if code in pattern_templates_by_code
    )


def format_target_lexeme_lines(lexemes: Iterable[tuple[str, str, str]]) -> str:
    lines = [
        TARGET_LEXEME_LIST_HEADER,
        *[
            f"{canonical_writing_ja} | {reading_kana} | {pos}"
            for canonical_writing_ja, reading_kana, pos in lexemes
        ],
    ]
    return normalize_prompt_list(lines)


def format_existing_word_lines(words: Iterable[ExistingWordPromptInfo]) -> str:
    lines = [
        WORD_LIST_HEADER,
        *[
            format_prompt_word_line(
                canonical_writing_ja=word.canonical_writing_ja,
                reading_kana=word.reading_kana,
                gloss_primary_en=word.gloss_primary_en,
                gloss_alternatives_en=word.gloss_alternatives_en,
                pos=word.pos,
            )
            for word in words
        ],
    ]
    return normalize_prompt_list(lines)


class UnitMetadataPromptLesson(TypedDict):
    lesson_index: int
    lesson_kind: str
    target_item_count: int
    target_word_lemmas: list[str]
    target_pattern_code: str | None
    available_word_lemmas: list[str]
    available_pattern_codes: list[str]


class UnitMetadataPromptUnit(TypedDict):
    order_index: int
    lesson_count: int
    lessons: list[UnitMetadataPromptLesson]


def format_unit_metadata_spec_lines(units: Sequence[UnitMetadataPromptUnit]) -> str:
    return normalize_prompt_list(
        f"Unit {unit['order_index']} | normal_lessons={unit['lesson_count']}" for unit in units
    )


def format_unit_metadata_allocated_content(
    *,
    units: Sequence[UnitMetadataPromptUnit],
    word_prompt_info_by_lemma: Mapping[str, ExistingWordPromptInfo],
    pattern_templates_by_code: Mapping[str, Sequence[str]],
) -> str:
    unit_blocks: list[str] = []
    for unit in units:
        lesson_lines = [
            " | ".join(
                [
                    f"lesson={lesson['lesson_index']}",
                    f"lesson_kind={lesson['lesson_kind']}",
                    f"target_items={lesson['target_item_count']}",
                    "target_words="
                    + (
                        "; ".join(
                            format_prompt_word_line(
                                canonical_writing_ja=word.canonical_writing_ja,
                                reading_kana=word.reading_kana,
                                gloss_primary_en=word.gloss_primary_en,
                                gloss_alternatives_en=word.gloss_alternatives_en,
                                pos=word.pos,
                            )
                            for lemma in lesson["target_word_lemmas"]
                            if (word := word_prompt_info_by_lemma.get(lemma)) is not None
                        )
                        or "(none)"
                    ),
                    "target_pattern="
                    + (
                        "; ".join(
                            f"{code} | templates={'; '.join(pattern_templates_by_code[code])}"
                            for code in [lesson["target_pattern_code"]]
                            if code is not None and code in pattern_templates_by_code
                        )
                        or "(none)"
                    ),
                    "available_words="
                    + (
                        "; ".join(
                            format_prompt_word_line(
                                canonical_writing_ja=word.canonical_writing_ja,
                                reading_kana=word.reading_kana,
                                gloss_primary_en=word.gloss_primary_en,
                                gloss_alternatives_en=word.gloss_alternatives_en,
                                pos=word.pos,
                            )
                            for lemma in lesson["available_word_lemmas"]
                            if (word := word_prompt_info_by_lemma.get(lemma)) is not None
                        )
                        or "(none)"
                    ),
                    "available_patterns="
                    + (
                        "; ".join(
                            f"{code} | templates={'; '.join(pattern_templates_by_code[code])}"
                            for code in lesson["available_pattern_codes"]
                            if code in pattern_templates_by_code
                        )
                        or "(none)"
                    ),
                ]
            )
            for lesson in unit["lessons"]
        ]
        unit_blocks.append(f"Unit {unit['order_index']}\n" + ("\n".join(lesson_lines) if lesson_lines else "(none)"))
    return normalize_prompt_list(unit_blocks)
