from __future__ import annotations

import asyncio
from pathlib import Path

from course_builder.llm.unit_metadata_generation import (
    PreparedUnitInput,
    PreparedUnitLessonInput,
    PreparedUnitMetadataInput,
    run_unit_metadata_generation,
)
from tests.helpers.builder import load_test_config

load_config = load_test_config


def test_unit_metadata_generation_returns_metadata_items(
    tmp_path: Path,
) -> None:
    config = load_config(tmp_path)

    result = asyncio.run(
        run_unit_metadata_generation(
            config=config,
            prepared_input=PreparedUnitMetadataInput(
                section_title="Section 1",
                section_generation_description="Starter Japanese.",
                section_theme_codes=["THEME_SELF_INTRO", "THEME_HOME_PLACE"],
                word_prompt_info_by_lemma={
                    "私": {
                        "canonical_writing_ja": "私",
                        "reading_kana": "わたし",
                        "gloss_primary_en": "I",
                        "gloss_alternatives_en": [],
                        "usage_note_en": None,
                        "pos": "pronoun",
                    }
                },
                pattern_templates_by_code={
                    "WA_DESU_STATEMENT": ["X は Y です"],
                },
                units=[
                    PreparedUnitInput(
                        order_index=1,
                        lessons=[
                            PreparedUnitLessonInput(
                                lesson_index=1,
                                lesson_kind="pattern_example_sentence",
                                target_item_count=4,
                                target_word_lemmas=["私"],
                                target_pattern_code="WA_DESU_STATEMENT",
                                available_word_lemmas=["私"],
                                available_pattern_codes=["WA_DESU_STATEMENT"],
                            )
                        ],
                    )
                ],
            ),
        )
    )

    assert [item.title for item in result.metadata_items] == ["Section 1 Unit 1"]
    assert [item.theme_codes for item in result.metadata_items] == [["THEME_SELF_INTRO"]]
    assert [item.description for item in result.metadata_items] == ["Placeholder unit description."]
    assert result.iterations == 0


def test_unit_metadata_generation_returns_empty_result_for_empty_units(
    tmp_path: Path,
) -> None:
    config = load_config(tmp_path)
    result = asyncio.run(
        run_unit_metadata_generation(
            config=config,
            prepared_input=PreparedUnitMetadataInput(
                section_title="Section 1",
                section_generation_description="Starter Japanese.",
                section_theme_codes=["THEME_SELF_INTRO"],
                units=[],
            ),
        )
    )
    assert result.metadata_items == []
    assert result.iterations == 0
