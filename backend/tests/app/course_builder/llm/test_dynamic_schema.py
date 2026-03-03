from __future__ import annotations

import json

from course_builder.llm.anchored_word_generation.json_schema import (
    build_anchored_word_generation_response_format,
)
from course_builder.llm.mechanical_word_generation.json_schema import (
    build_mechanical_word_generation_response_format,
)
from course_builder.llm.pattern_vocab_generation.json_schema import (
    build_pattern_vocab_response_format,
)
from course_builder.llm.unit_metadata_generation.json_schema import build_unit_metadata_response_format


def _schema_bytes(schema: dict[str, object]) -> bytes:
    return json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def test_pattern_vocab_schema_is_byte_stable() -> None:
    first_schema = build_pattern_vocab_response_format(
        min_item_count=3,
        max_item_count=3,
    )
    second_schema = build_pattern_vocab_response_format(
        min_item_count=3,
        max_item_count=3,
    )

    assert _schema_bytes(first_schema) == _schema_bytes(second_schema)


def test_anchored_word_schema_is_byte_stable() -> None:
    first_schema = build_anchored_word_generation_response_format(item_count=2)
    second_schema = build_anchored_word_generation_response_format(item_count=2)

    assert _schema_bytes(first_schema) == _schema_bytes(second_schema)


def test_mechanical_word_schema_is_byte_stable() -> None:
    first_schema = build_mechanical_word_generation_response_format(item_count=2)
    second_schema = build_mechanical_word_generation_response_format(item_count=2)

    assert _schema_bytes(first_schema) == _schema_bytes(second_schema)


def test_unit_schema_is_byte_stable() -> None:
    first_schema = build_unit_metadata_response_format(
        unit_count=2,
        section_theme_codes=["THEME_SELF_INTRO", "THEME_HOME_PLACE"],
    )
    second_schema = build_unit_metadata_response_format(
        unit_count=2,
        section_theme_codes=["THEME_SELF_INTRO", "THEME_HOME_PLACE"],
    )

    assert _schema_bytes(first_schema) == _schema_bytes(second_schema)


def test_response_format_marks_all_object_properties_as_required() -> None:
    response_format = build_pattern_vocab_response_format(
        min_item_count=2,
        max_item_count=2,
    )
    schema = response_format["schema"]
    assert isinstance(schema, dict)
    properties = schema["properties"]
    required = schema["required"]
    assert isinstance(properties, dict)
    assert isinstance(required, list)
    assert required == list(properties.keys())


def test_response_format_strips_ref_sibling_keywords() -> None:
    response_format = build_pattern_vocab_response_format(
        min_item_count=2,
        max_item_count=2,
    )
    schema = response_format["schema"]
    assert isinstance(schema, dict)
    properties = schema["properties"]
    assert isinstance(properties, dict)
    first_item = properties["i"]
    assert isinstance(first_item, dict)
    assert "$ref" not in first_item
