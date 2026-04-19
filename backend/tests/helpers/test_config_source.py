from __future__ import annotations

from pathlib import Path

import yaml

TEST_CONFIG_YAML = """
course:
  code: "en-ja"
  version: 1
  seed: 1337
  config_version: "test_config_v1"

bootstrap:
  marker_words:
    - { canonical_writing_ja: "は", reading_kana: "は", gloss_primary_en: "topic marker", gloss_alternatives_en: [], usage_note_en: "particle", pos: "marker" }
  function_words:
    - { canonical_writing_ja: "です", reading_kana: "です", gloss_primary_en: "polite copula", gloss_alternatives_en: [], usage_note_en: null, pos: "function_word" }
  seed_words:
    - { canonical_writing_ja: "こんにちは", reading_kana: "こんにちは", gloss_primary_en: "hello", gloss_alternatives_en: [], usage_note_en: "fixed greeting expression", pos: "expression" }
    - { canonical_writing_ja: "ありがとう", reading_kana: "ありがとう", gloss_primary_en: "thank you", gloss_alternatives_en: [], usage_note_en: "fixed expression", pos: "expression" }
    - { canonical_writing_ja: "私", reading_kana: "わたし", gloss_primary_en: "I", gloss_alternatives_en: [], usage_note_en: null, pos: "pronoun" }
    - { canonical_writing_ja: "これ", reading_kana: "これ", gloss_primary_en: "this", gloss_alternatives_en: [], usage_note_en: null, pos: "pronoun" }
    - { canonical_writing_ja: "学生", reading_kana: "がくせい", gloss_primary_en: "student", gloss_alternatives_en: [], usage_note_en: null, pos: "noun" }
    - { canonical_writing_ja: "本", reading_kana: "ほん", gloss_primary_en: "book", gloss_alternatives_en: [], usage_note_en: null, pos: "noun" }

themes:
  tags:
    - code: "THEME_SELF_INTRO"
      name: "Self introduction"
    - code: "THEME_HOME_PLACE"
      name: "Home and place"

patterns:
  - code: "WA_DESU_STATEMENT"
    name: "X は Y です"
    kind: "structural"
    templates:
      - "X は Y です"
    required_support_forms: ["は", "です"]
    anchor_mode: null
    anchor_word_refs: []
    required_lexical_mode: null
    required_lexical_refs: []
    short_description: "Basic polite statement."
    examples:
      - ja: "私は学生です。"
        en: "I am a student."
        lexicon_used:
          - { canonical_writing_ja: "私", reading_kana: "わたし", pos: "pronoun" }
          - { canonical_writing_ja: "は", reading_kana: "は", pos: "particle" }
          - { canonical_writing_ja: "学生", reading_kana: "がくせい", pos: "noun" }
          - { canonical_writing_ja: "です", reading_kana: "です", pos: "copula" }
      - ja: "これは本です。"
        en: "This is a book."
        lexicon_used:
          - { canonical_writing_ja: "これ", reading_kana: "これ", pos: "pronoun" }
          - { canonical_writing_ja: "は", reading_kana: "は", pos: "particle" }
          - { canonical_writing_ja: "本", reading_kana: "ほん", pos: "noun" }
          - { canonical_writing_ja: "です", reading_kana: "です", pos: "copula" }

sections:
  first_section:
    title: "Section 1"
    description: "Tiny test section."
    generation_description: "Tiny test section for generation."
    primary_themes:
      - "THEME_SELF_INTRO"
    secondary_themes:
      - "THEME_HOME_PLACE"
    patterns_scope:
      - "WA_DESU_STATEMENT"
    section_planning:
      min_sentence_introductions_per_normal_lesson: 1
      max_sentence_introductions_per_normal_lesson: 3

lessons:
  normal_lessons_per_unit: 5
  review_previous_units_lessons_per_unit: 1
  exam_lessons_per_unit: 1

items:
  word_translation:
    item_count: 12
    direction_ratio:
      ja_to_en: 0.50
      en_to_ja: 0.50
  sentence_translation:
    item_count: 12
    direction_ratio:
      ja_to_en: 0.50
      en_to_ja: 0.50
  review_previous_units:
    item_count: 12
    direction_ratio:
      ja_to_en: 0.50
      en_to_ja: 0.50
  exam:
    item_count: 12
    direction_ratio:
      ja_to_en: 0.50
      en_to_ja: 0.50

generation:
  words:
    batch_size: 20
    max_total_per_build: 50
  lessons:
    seed_word_translation_items_per_word: 2
    generated_word_sentence_count_per_word: 3
    pattern_sentence_count_per_pattern: 6
    reinforcement_sentence_count_per_lesson: 6
    max_sentences_per_normal_lesson: 6
    max_new_words_per_normal_lesson: 2
    max_new_patterns_per_normal_lesson: 1

runtime_distractors:
  word_choice:
    option_count: 4
  sentence_tiles:
    distractor_count: 2

llm:
  mechanical_word_generation:
    model: "gpt-5.2"
    reasoning_effort: "medium"
  anchored_word_generation:
    model: "gpt-5.2"
    reasoning_effort: "medium"
  pattern_vocab_generation:
    model: "gpt-5.2"
    reasoning_effort: "medium"
  unit_metadata_generation:
    model: "gpt-5.2"
    reasoning_effort: "medium"
"""


def write_config(tmp_path: Path, content: str) -> Path:
    loaded = yaml.safe_load(content)
    if not isinstance(loaded, dict):
        msg = "Expected test config content to be a mapping"
        raise TypeError(msg)

    root = tmp_path / "course_build_config"
    root.mkdir(parents=True, exist_ok=True)
    section_dir = root / "PRE_A1"
    section_dir.mkdir(parents=True, exist_ok=True)

    bootstrap = loaded["bootstrap"]
    first_section = loaded["sections"]["first_section"]
    theme_tags = loaded["themes"]["tags"]
    pattern_entries = loaded["patterns"]

    support_words = [
        *_normalize_test_support_words(bootstrap.get("marker_words", []), default_pos="particle"),
        *_normalize_test_support_words(bootstrap.get("function_words", []), default_pos="copula"),
    ]
    seed_words = [_normalize_test_word(word) for word in bootstrap["seed_words"]]
    primary_theme_codes = list(first_section["primary_themes"])
    secondary_theme_codes = list(first_section.get("secondary_themes", []))
    theme_by_code = {theme["code"]: theme for theme in theme_tags}

    (root / "course.yaml").write_text(
        yaml.safe_dump(
            {
                "course": loaded["course"],
                "sections": ["PRE_A1"],
                "lessons": loaded["lessons"],
                "items": loaded["items"],
                "generation": loaded["generation"],
                "runtime_distractors": loaded["runtime_distractors"],
                "llm": loaded["llm"],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (section_dir / "themes.yaml").write_text(
        yaml.safe_dump(
            {
                "themes": {
                    "primary": [theme_by_code[code] for code in primary_theme_codes],
                    "secondary": [theme_by_code[code] for code in secondary_theme_codes],
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (section_dir / "section.yaml").write_text(
        yaml.safe_dump(
            {
                "section": {
                    "title": first_section["title"],
                    "description": first_section["description"],
                    "generation_description": first_section["generation_description"],
                    "section_planning": first_section.get("section_planning", {}),
                }
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    normalized_pattern_entries = [_build_test_pattern_entry(pattern) for pattern in pattern_entries]
    (section_dir / "patterns.yaml").write_text(
        yaml.safe_dump(
            {"patterns": normalized_pattern_entries},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (section_dir / "pattern_examples.yaml").write_text(
        yaml.safe_dump(
            {
                "pattern_examples": [
                    {
                        "code": pattern["code"],
                        "examples": _build_test_pattern_examples(pattern),
                    }
                    for pattern in pattern_entries
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (section_dir / "bootstrap_words.yaml").write_text(
        yaml.safe_dump(
            {"bootstrap_words": [*support_words, *seed_words]},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return root


def _normalize_test_support_words(words: list[dict[str, object]], *, default_pos: str) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for word in words:
        normalized.append(_normalize_test_word(word, default_pos=default_pos))
    return normalized


def _normalize_test_word(word: dict[str, object], *, default_pos: str | None = None) -> dict[str, object]:
    normalized = dict(word)
    if normalized.get("pos") == "marker":
        normalized["pos"] = default_pos or "particle"
    elif normalized.get("pos") == "function_word":
        normalized["pos"] = default_pos or "copula"
    return normalized


def _build_test_pattern_entry(pattern: dict[str, object]) -> dict[str, object]:
    templates = pattern.get("templates")
    template_values = templates if isinstance(templates, list) else [pattern["template"]]
    required_support_forms_value = pattern.get("required_support_forms", [])
    required_support_forms = (
        list(required_support_forms_value) if isinstance(required_support_forms_value, list) else []
    )
    required_support_lexeme_refs = [
        {
            "canonical_writing_ja": form,
            "reading_kana": form,
            "pos": "particle",
        }
        for form in required_support_forms
    ]
    anchor_word_refs_value = pattern.get("anchor_word_refs", [])
    if not isinstance(anchor_word_refs_value, list):
        anchor_word_refs_value = []
    required_lexical_refs_value = pattern.get("required_lexical_refs", [])
    if not isinstance(required_lexical_refs_value, list):
        required_lexical_refs_value = []
    return {
        "code": pattern["code"],
        "name": pattern["name"],
        "templates": template_values,
        "required_support_lexeme_refs": required_support_lexeme_refs,
        "anchor_mode": pattern.get("anchor_mode"),
        "anchor_word_refs": [_normalize_test_word(ref) for ref in anchor_word_refs_value if isinstance(ref, dict)],
        "required_lexical_mode": pattern.get("required_lexical_mode"),
        "required_lexical_refs": [
            _normalize_test_word(ref) for ref in required_lexical_refs_value if isinstance(ref, dict)
        ],
        "short_description": pattern["short_description"],
        "min_extra_words": pattern.get("min_extra_words"),
        "max_extra_words": pattern.get("max_extra_words"),
    }


def _build_test_pattern_examples(pattern: dict[str, object]) -> list[dict[str, object]]:
    examples: list[dict[str, object]] = []
    examples_value = pattern.get("examples", [])
    if not isinstance(examples_value, list):
        return examples
    for example in examples_value:
        if not isinstance(example, dict):
            continue
        examples.append(
            {
                "ja": example["ja"],
                "en": example["en"],
                "lexicon_used": [
                    _normalize_test_word(lexeme)
                    for lexeme in example.get("lexicon_used", [])
                    if isinstance(lexeme, dict)
                ],
            }
        )
    return examples
