from __future__ import annotations

from pathlib import Path

import pytest

from course_builder.config import CourseBuildConfigLoader
from tests.helpers.config_builder import build_test_config_yaml
from tests.helpers.test_config_source import TEST_CONFIG_YAML, write_config


def test_load_and_validate_valid_config(tmp_path: Path) -> None:
    config = CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, TEST_CONFIG_YAML), section_code="PRE_A1")

    assert config.course.code == "en-ja"
    assert config.current_section.patterns_scope[0] == "WA_DESU_STATEMENT"
    assert config.items.word_translation.item_count == 12


def test_rejects_duplicate_theme_code(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        updates={
            ("themes", "tags", 0, "code"): "THEME_DUP",
            ("themes", "tags", 1, "code"): "THEME_DUP",
            ("sections", "first_section", "primary_themes", 0): "THEME_DUP",
            ("sections", "first_section", "secondary_themes", 0): "THEME_DUP",
        }
    )

    with pytest.raises(ValueError, match=r"themes\.tags codes must be unique"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")


def test_rejects_unknown_section_code(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown section code"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, TEST_CONFIG_YAML), section_code="A1_1")


def test_rejects_anchor_words_without_anchor_mode(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        updates={
            ("patterns", 0, "anchor_mode"): "all_of",
        }
    )

    with pytest.raises(ValueError, match="anchor_mode must define anchor_word_refs"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")


def test_allows_required_support_forms_not_in_bootstrap(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        updates={
            ("patterns", 0, "required_support_forms"): ["は", "ません"],
        }
    )

    config = CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")
    assert config.patterns[0].required_support_forms == ["は", "ません"]


def test_rejects_required_lexical_refs_without_mode(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        updates={
            (
                "patterns",
                0,
                "required_lexical_refs",
            ): [{"canonical_writing_ja": "これ", "reading_kana": "これ", "pos": "pronoun"}],
        }
    )

    with pytest.raises(ValueError, match="null required_lexical_mode must not define required_lexical_refs"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")


def test_allows_required_lexical_refs_outside_bootstrap_inventory(tmp_path: Path) -> None:
    yaml_with_required_lexical_ref = build_test_config_yaml(
        updates={
            ("patterns", 0, "required_lexical_mode"): "all_of",
            (
                "patterns",
                0,
                "required_lexical_refs",
            ): [{"canonical_writing_ja": "どこ", "reading_kana": "どこ", "pos": "pronoun"}],
        }
    )

    config = CourseBuildConfigLoader.load_and_validate(
        write_config(tmp_path, yaml_with_required_lexical_ref),
        section_code="PRE_A1",
    )

    assert config.patterns[0].required_lexical_mode == "all_of"
    assert config.patterns[0].required_lexical_refs[0].canonical_writing_ja == "どこ"


def test_rejects_conflicting_pos_for_same_pattern_example_lexeme(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        appends={
            ("patterns", 0, "examples"): [
                {
                    "ja": "みせです。",
                    "en": "It is a shop.",
                    "lexicon_used": [
                        {"canonical_writing_ja": "みせ", "reading_kana": "みせ", "pos": "noun"},
                    ],
                },
                {
                    "ja": "みせです。",
                    "en": "It is a shop.",
                    "lexicon_used": [
                        {"canonical_writing_ja": "みせ", "reading_kana": "みせ", "pos": "expression"},
                    ],
                },
            ]
        }
    )

    with pytest.raises(ValueError, match=r"lexicon_used contains conflicting pos for みせ/みせ: noun != expression"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")


def test_rejects_pattern_example_english_with_alternative_separator(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        appends={
            ("patterns", 0, "examples"): [
                {
                    "ja": "ともだちがいます。",
                    "en": "I have a friend / There is a friend.",
                    "lexicon_used": [
                        {"canonical_writing_ja": "ともだち", "reading_kana": "ともだち", "pos": "noun"},
                    ],
                }
            ]
        }
    )

    with pytest.raises(ValueError, match=r"pattern examples en must be one clean sentence"):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")


def test_rejects_non_generated_pattern_example_lexeme_missing_from_bootstrap(tmp_path: Path) -> None:
    invalid_yaml = build_test_config_yaml(
        appends={
            ("patterns", 0, "examples"): [
                {
                    "ja": "家族は三人です。",
                    "en": "There are three people in my family.",
                    "lexicon_used": [
                        {"canonical_writing_ja": "家族", "reading_kana": "かぞく", "pos": "noun"},
                        {"canonical_writing_ja": "は", "reading_kana": "は", "pos": "particle"},
                        {"canonical_writing_ja": "三人", "reading_kana": "さんにん", "pos": "noun"},
                        {"canonical_writing_ja": "です", "reading_kana": "です", "pos": "copula"},
                    ],
                }
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            r"patterns\[WA_DESU_STATEMENT\] has example lexemes but no min_extra_words/max_extra_words; "
            r"non-support example lexemes must be present in bootstrap_words: .*三人/さんにん/noun"
        ),
    ):
        CourseBuildConfigLoader.load_and_validate(write_config(tmp_path, invalid_yaml), section_code="PRE_A1")
