from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from course_builder.lexicon import LexemePos, is_kana_text

RATIO_SUM_TOLERANCE = 0.0001


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CourseConfig(StrictModel):
    code: str
    version: int = Field(ge=1)
    seed: int
    config_version: str


class SeedWordConfig(StrictModel):
    canonical_writing_ja: str
    reading_kana: str
    gloss_primary_en: str = Field(min_length=1)
    gloss_alternatives_en: list[str] = Field(default_factory=list, max_length=2)
    usage_note_en: str | None = None
    pos: LexemePos

    @model_validator(mode="after")
    def validate_gloss_fields(self) -> SeedWordConfig:
        if "/" in self.gloss_primary_en or ";" in self.gloss_primary_en:
            msg = "bootstrap.seed_words gloss_primary_en must not contain '/' or ';'"
            raise ValueError(msg)
        if not self.reading_kana.strip():
            msg = "bootstrap.seed_words reading_kana must not be empty"
            raise ValueError(msg)
        if any(char.isspace() for char in self.reading_kana) or not is_kana_text(self.reading_kana):
            msg = "bootstrap.seed_words reading_kana must contain kana only"
            raise ValueError(msg)
        return self


class BootstrapConfig(StrictModel):
    support_words: list[SeedWordConfig] = Field(default_factory=list)
    seed_words: list[SeedWordConfig] = Field(default_factory=list)


class ThemeTagConfig(StrictModel):
    code: str
    name: str


class ThemesConfig(StrictModel):
    tags: list[ThemeTagConfig] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_codes(self) -> ThemesConfig:
        codes = [tag.code for tag in self.tags]
        if len(codes) != len(set(codes)):
            msg = "themes.tags codes must be unique"
            raise ValueError(msg)
        return self


class AnchorWordRefConfig(StrictModel):
    canonical_writing_ja: str
    reading_kana: str
    pos: LexemePos

    @model_validator(mode="after")
    def validate_reading_kana(self) -> AnchorWordRefConfig:
        if not self.reading_kana.strip():
            msg = "patterns.anchor_word_refs reading_kana must not be empty"
            raise ValueError(msg)
        if any(char.isspace() for char in self.reading_kana) or not is_kana_text(self.reading_kana):
            msg = "patterns.anchor_word_refs reading_kana must contain kana only"
            raise ValueError(msg)
        return self


class PatternExampleConfig(StrictModel):
    ja: str
    en: str
    lexicon_used: list[AnchorWordRefConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_english_sentence(self) -> PatternExampleConfig:
        if "/" in self.en or ";" in self.en:
            msg = "pattern examples en must be one clean sentence and must not contain '/' or ';'"
            raise ValueError(msg)
        return self


class PatternConfig(StrictModel):
    code: str
    name: str
    kind: Literal["structural", "lexicalized"] = "structural"
    templates: list[str] = Field(min_length=1)
    required_support_forms: list[str] = Field(default_factory=list)
    anchor_mode: Literal["all_of", "any_of"] | None = None
    anchor_word_refs: list[AnchorWordRefConfig] = Field(default_factory=list)
    required_lexical_mode: Literal["all_of", "any_of"] | None = None
    required_lexical_refs: list[AnchorWordRefConfig] = Field(default_factory=list)
    short_description: str
    examples: list[PatternExampleConfig] = Field(default_factory=list)
    min_extra_words: int | None = Field(default=None, ge=0)
    max_extra_words: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_anchor_fields(self) -> PatternConfig:
        if self.anchor_mode is None and self.anchor_word_refs:
            msg = "patterns entries with null anchor_mode must not define anchor_word_refs"
            raise ValueError(msg)
        if self.anchor_mode is not None and not self.anchor_word_refs:
            msg = "patterns entries with anchor_mode must define anchor_word_refs"
            raise ValueError(msg)
        if self.required_lexical_mode is None and self.required_lexical_refs:
            msg = "patterns entries with null required_lexical_mode must not define required_lexical_refs"
            raise ValueError(msg)
        if self.required_lexical_mode is not None and not self.required_lexical_refs:
            msg = "patterns entries with required_lexical_mode must define required_lexical_refs"
            raise ValueError(msg)
        if (
            self.min_extra_words is not None
            and self.max_extra_words is not None
            and self.min_extra_words > self.max_extra_words
        ):
            msg = f"patterns[{self.code}] min_extra_words must be <= max_extra_words"
            raise ValueError(msg)
        return self


class SectionPlanningConfig(StrictModel):
    min_sentence_introductions_per_normal_lesson: int = Field(default=2, ge=1)
    max_sentence_introductions_per_normal_lesson: int = Field(default=3, ge=1)
    bootstrap_mode: Literal["support_only", "normal"] = "normal"

    @model_validator(mode="after")
    def validate_bounds(self) -> SectionPlanningConfig:
        if (
            self.min_sentence_introductions_per_normal_lesson
            > self.max_sentence_introductions_per_normal_lesson
        ):
            msg = (
                "section_planning.min_sentence_introductions_per_normal_lesson must be <= "
                "max_sentence_introductions_per_normal_lesson"
            )
            raise ValueError(msg)
        return self


class SectionConfig(StrictModel):
    code: str
    title: str
    description: str
    generation_description: str
    primary_themes: list[str] = Field(min_length=1)
    secondary_themes: list[str] = Field(default_factory=list)
    patterns_scope: list[str] = Field(min_length=1)
    section_planning: SectionPlanningConfig = Field(default_factory=SectionPlanningConfig)


class SectionsConfig(StrictModel):
    ordered_codes: list[str] = Field(min_length=1)
    current: SectionConfig

    def index_of(self, section_code: str) -> int:
        try:
            return self.ordered_codes.index(section_code)
        except ValueError as exc:
            msg = f"Unknown section code in course sections order: {section_code}"
            raise ValueError(msg) from exc

    def previous_codes(self, section_code: str) -> list[str]:
        return self.ordered_codes[: self.index_of(section_code)]

    def is_first(self, section_code: str) -> bool:
        return self.index_of(section_code) == 0


class DirectionRatioConfig(StrictModel):
    ja_to_en: float = Field(ge=0.0, le=1.0)
    en_to_ja: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_ratio_sum(self) -> DirectionRatioConfig:
        if abs((self.ja_to_en + self.en_to_ja) - 1.0) > RATIO_SUM_TOLERANCE:
            msg = "direction ratios must sum to 1.0"
            raise ValueError(msg)
        return self


class LessonsConfig(StrictModel):
    normal_lessons_per_unit: int = Field(ge=1)
    review_previous_units_lessons_per_unit: int = Field(ge=0)
    exam_lessons_per_unit: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> LessonsConfig:
        if self.exam_lessons_per_unit != 1:
            msg = "lessons.exam_lessons_per_unit must be exactly 1"
            raise ValueError(msg)
        return self


class ItemProfileConfig(StrictModel):
    item_count: int = Field(ge=1)
    direction_ratio: DirectionRatioConfig


class ItemsConfig(StrictModel):
    word_translation: ItemProfileConfig
    sentence_translation: ItemProfileConfig
    review_previous_units: ItemProfileConfig
    exam: ItemProfileConfig


class GenerationWordsConfig(StrictModel):
    batch_size: int = Field(ge=1)
    max_total_per_build: int = Field(ge=1)


class GenerationLessonsConfig(StrictModel):
    seed_word_translation_items_per_word: int = Field(ge=1)
    generated_word_sentence_count_per_word: int = Field(ge=1)
    pattern_sentence_count_per_pattern: int = Field(ge=1)
    reinforcement_sentence_count_per_lesson: int = Field(ge=1)
    max_sentences_per_normal_lesson: int = Field(ge=1)
    max_new_words_per_normal_lesson: int = Field(ge=1)
    max_new_patterns_per_normal_lesson: int = Field(ge=1)


class GenerationConfig(StrictModel):
    words: GenerationWordsConfig
    lessons: GenerationLessonsConfig


class RuntimeDistractorsWordChoiceConfig(StrictModel):
    option_count: int = Field(ge=2)


class RuntimeDistractorsSentenceTilesConfig(StrictModel):
    distractor_count: int = Field(ge=0)


class RuntimeDistractorsConfig(StrictModel):
    word_choice: RuntimeDistractorsWordChoiceConfig
    sentence_tiles: RuntimeDistractorsSentenceTilesConfig


class LlmConfig(StrictModel):
    pattern_vocab_generation_model: str
    unit_metadata_generation_model: str


class CourseBuildConfig(StrictModel):
    config_root: Path
    course: CourseConfig
    bootstrap: BootstrapConfig
    themes: ThemesConfig
    patterns: list[PatternConfig] = Field(min_length=1)
    sections: SectionsConfig
    lessons: LessonsConfig
    items: ItemsConfig
    generation: GenerationConfig
    runtime_distractors: RuntimeDistractorsConfig
    llm: LlmConfig

    @property
    def current_section(self) -> SectionConfig:
        return self.sections.current

    @property
    def current_section_code(self) -> str:
        return self.sections.current.code

    @property
    def previous_section_codes(self) -> list[str]:
        return self.sections.previous_codes(self.current_section_code)

    @model_validator(mode="after")
    def validate_cross_references(self) -> CourseBuildConfig:
        theme_codes = {tag.code for tag in self.themes.tags}
        pattern_codes = {pattern.code for pattern in self.patterns}
        bootstrap_word_keys = {
            (word.canonical_writing_ja, word.reading_kana, word.pos)
            for word in [*self.bootstrap.seed_words, *self.bootstrap.support_words]
        }
        example_lexeme_pos_by_key: dict[tuple[str, str], LexemePos] = {}
        current_section = self.current_section
        missing_primary_themes = sorted(set(current_section.primary_themes) - theme_codes)
        if missing_primary_themes:
            msg = f"sections.current.primary_themes contains unknown theme codes: {missing_primary_themes}"
            raise ValueError(msg)

        missing_secondary_themes = sorted(set(current_section.secondary_themes) - theme_codes)
        if missing_secondary_themes:
            msg = f"sections.current.secondary_themes contains unknown theme codes: {missing_secondary_themes}"
            raise ValueError(msg)

        missing_pattern_scope = sorted(set(current_section.patterns_scope) - pattern_codes)
        if missing_pattern_scope:
            msg = f"sections.current.patterns_scope contains unknown pattern codes: {missing_pattern_scope}"
            raise ValueError(msg)
        scoped_pattern_codes = set(current_section.patterns_scope)

        for pattern in self.patterns:
            for example in pattern.examples:
                for lexeme in example.lexicon_used:
                    lexeme_key = (lexeme.canonical_writing_ja, lexeme.reading_kana)
                    existing_pos = example_lexeme_pos_by_key.get(lexeme_key)
                    if existing_pos is not None and existing_pos != lexeme.pos:
                        msg = (
                            f"patterns[{pattern.code}] lexicon_used contains conflicting pos for "
                            f"{lexeme.canonical_writing_ja}/{lexeme.reading_kana}: "
                            f"{existing_pos.value} != {lexeme.pos.value}"
                        )
                        raise ValueError(msg)
                    example_lexeme_pos_by_key[lexeme_key] = lexeme.pos
            if pattern.code in scoped_pattern_codes:
                missing_anchor_refs = sorted(
                    (f"{anchor_ref.canonical_writing_ja}/{anchor_ref.reading_kana}/{anchor_ref.pos}")
                    for anchor_ref in pattern.anchor_word_refs
                    if (
                        anchor_ref.canonical_writing_ja,
                        anchor_ref.reading_kana,
                        anchor_ref.pos,
                    )
                    not in bootstrap_word_keys
                )
                if missing_anchor_refs:
                    msg = f"patterns[{pattern.code}] anchor_word_refs contains unknown lexical refs: {missing_anchor_refs}"
                    raise ValueError(msg)

        return self


class CourseBuildConfigLoader:
    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            msg = f"Config file must contain a mapping at root level: {path}"
            raise ValueError(msg)
        return data

    @classmethod
    def from_directory(cls, path: str | Path, *, section_code: str) -> CourseBuildConfig:
        root = Path(path)
        if not root.is_dir():
            msg = f"Course build config entrypoint must be a directory, got: {root}"
            raise ValueError(msg)

        course_payload = cls._read_yaml(root / "course.yaml")
        course = CourseConfig.model_validate(course_payload["course"])
        lessons = LessonsConfig.model_validate(course_payload["lessons"])
        items = ItemsConfig.model_validate(course_payload["items"])
        generation = GenerationConfig.model_validate(course_payload["generation"])
        runtime_distractors = RuntimeDistractorsConfig.model_validate(course_payload["runtime_distractors"])
        llm = LlmConfig.model_validate(course_payload["llm"])

        declared_section_codes = course_payload.get("sections")
        if not isinstance(declared_section_codes, list) or not declared_section_codes:
            msg = "course.yaml must declare a non-empty sections list"
            raise ValueError(msg)
        if section_code not in declared_section_codes:
            msg = f"Unknown section code {section_code!r}; expected one of {declared_section_codes!r}"
            raise ValueError(msg)
        active_section_index = declared_section_codes.index(section_code)

        section_dir = root / section_code
        if not section_dir.is_dir():
            msg = f"Missing section directory for active section {section_code}: {section_dir}"
            raise ValueError(msg)

        themes_payload = cls._read_yaml(section_dir / "themes.yaml")
        section_payload = cls._read_yaml(section_dir / "section.yaml")
        bootstrap_words_path = section_dir / "bootstrap_words.yaml"
        bootstrap_words_payload = (
            cls._read_yaml(bootstrap_words_path) if bootstrap_words_path.exists() else {"bootstrap_words": []}
        )

        primary_themes = [ThemeTagConfig.model_validate(item) for item in themes_payload["themes"]["primary"]]
        secondary_themes = [
            ThemeTagConfig.model_validate(item) for item in themes_payload["themes"].get("secondary", [])
        ]
        themes = ThemesConfig(tags=[*primary_themes, *secondary_themes])

        patterns: list[PatternConfig] = []
        for loaded_section_code in declared_section_codes[: active_section_index + 1]:
            loaded_section_dir = root / loaded_section_code
            loaded_patterns_payload = cls._read_yaml(loaded_section_dir / "patterns.yaml")
            loaded_pattern_examples_payload = cls._read_yaml(loaded_section_dir / "pattern_examples.yaml")
            examples_by_code: dict[str, list[dict[str, Any]]] = {}
            for example_entry in loaded_pattern_examples_payload.get("pattern_examples", []):
                pattern_code = example_entry["code"]
                examples_by_code.setdefault(pattern_code, []).extend(example_entry.get("examples", []))

            for raw_pattern in loaded_patterns_payload.get("patterns", []):
                support_refs = raw_pattern.get("required_support_lexeme_refs", [])
                pattern_payload = {
                    "code": raw_pattern["code"],
                    "name": raw_pattern["name"],
                    "kind": raw_pattern.get("kind", "structural"),
                    "templates": raw_pattern["templates"],
                    "required_support_forms": [ref["canonical_writing_ja"] for ref in support_refs],
                    "anchor_mode": raw_pattern.get("anchor_mode"),
                    "anchor_word_refs": raw_pattern.get("anchor_word_refs", []),
                    "required_lexical_mode": raw_pattern.get("required_lexical_mode"),
                    "required_lexical_refs": raw_pattern.get("required_lexical_refs", []),
                    "short_description": raw_pattern["short_description"],
                    "examples": examples_by_code.get(raw_pattern["code"], []),
                    "min_extra_words": raw_pattern.get("min_extra_words"),
                    "max_extra_words": raw_pattern.get("max_extra_words"),
                }
                patterns.append(PatternConfig.model_validate(pattern_payload))

        bootstrap_words = [SeedWordConfig.model_validate(item) for item in bootstrap_words_payload["bootstrap_words"]]
        support_words = [word for word in bootstrap_words if LexemePos.is_support(word.pos)]
        seed_words = [word for word in bootstrap_words if not LexemePos.is_support(word.pos)]
        bootstrap = BootstrapConfig(
            support_words=support_words,
            seed_words=seed_words,
        )

        current_section = SectionConfig(
            code=section_code,
            title=section_payload["section"]["title"],
            description=section_payload["section"]["description"],
            generation_description=section_payload["section"]["generation_description"],
            primary_themes=[theme.code for theme in primary_themes],
            secondary_themes=[theme.code for theme in secondary_themes],
            patterns_scope=[
                raw_pattern["code"] for raw_pattern in cls._read_yaml(section_dir / "patterns.yaml").get("patterns", [])
            ],
            section_planning=SectionPlanningConfig.model_validate(
                {
                    **section_payload["section"].get("section_planning", {}),
                    "bootstrap_mode": section_payload["section"]
                    .get("section_planning", {})
                    .get("bootstrap_mode", "support_only" if active_section_index == 0 else "normal"),
                }
            ),
        )

        return CourseBuildConfig(
            config_root=root,
            course=course,
            bootstrap=bootstrap,
            themes=themes,
            patterns=patterns,
            sections=SectionsConfig(ordered_codes=list(declared_section_codes), current=current_section),
            lessons=lessons,
            items=items,
            generation=generation,
            runtime_distractors=runtime_distractors,
            llm=llm,
        )

    @classmethod
    def load_and_validate(cls, path: str | Path, *, section_code: str) -> CourseBuildConfig:
        return cls.from_directory(path, section_code=section_code)


def default_config_directory(*, course_code: str, course_version: int) -> Path:
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "config" / f"{course_code}-v{course_version}"


@cache
def load_course_config(*, course_code: str, course_version: int, section_code: str) -> CourseBuildConfig:
    return CourseBuildConfigLoader.load_and_validate(
        default_config_directory(course_code=course_code, course_version=course_version),
        section_code=section_code,
    )
