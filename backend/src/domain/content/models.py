from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# `course_versions`
#
# **Purpose:** one generated course build.
class CourseVersion(Base):
    __tablename__ = "course_versions"
    __table_args__ = (
        UniqueConstraint("code", "version", "build_version", name="uq_course_versions_code_version_build_version"),
    )

    # * `id uuid pk` — course build identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `code text not null` — logical course code, e.g. `en-ja`.
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # * `version int not null` — build number.
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `build_version int not null` — run number for the same logical course version/config family.
    build_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `status text not null` — `draft|active|archived`.
    status: Mapped[str] = mapped_column(Text, nullable=False)
    # * `created_at timestamptz not null default now()` — build creation timestamp.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `config_version text not null` — config version string.
    config_version: Mapped[str] = mapped_column(Text, nullable=False)
    # * `config_hash text not null` — exact config hash for reproducibility.
    config_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (code, version, build_version)` — one build per code/version/build_version.


# `theme_tags`
#
# **Purpose:** reusable theme labels for words, sections, and units.
class ThemeTag(Base):
    __tablename__ = "theme_tags"
    __table_args__ = (UniqueConstraint("course_version_id", "code", name="uq_theme_tags_course_code"),)

    # * `id uuid pk` — theme identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — owning build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `code text not null` — stable code, e.g. `THEME_FOOD_DRINK`.
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # * `name text not null` — internal/display name.
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (course_version_id, code)` — one theme row per code per build.


# `patterns`
#
# **Purpose:** canonical teaching patterns for a course build.
#
# Patterns in this system are teaching patterns, not microscopic linguistic atoms.
class Pattern(Base):
    __tablename__ = "patterns"
    __table_args__ = (
        UniqueConstraint("course_version_id", "code", name="uq_patterns_course_code"),
        UniqueConstraint("course_version_id", "intro_order", name="uq_patterns_course_intro_order"),
    )

    # * `id uuid pk` — pattern identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — owning build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `code text not null` — stable pattern code.
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # * `name text not null` — readable pattern name.
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # * `short_description text not null` — short internal explanation.
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    # * `intro_order int not null` — canonical introduction order.
    intro_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `is_bootstrap bool not null default false` — whether the pattern is part of bootstrap scope.
    is_bootstrap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `unique (course_version_id, code)` — one pattern row per code per build.
    # * `unique (course_version_id, intro_order)` — stable ordering.


# `words`
#
# **Purpose:** canonical word inventory for a course build.
class Word(Base):
    __tablename__ = "words"
    __table_args__ = (
        UniqueConstraint("course_version_id", "intro_order", name="uq_words_course_intro_order"),
        UniqueConstraint(
            "course_version_id",
            "canonical_writing_ja",
            "reading_kana",
            name="uq_words_course_canonical_writing_reading",
        ),
    )

    # * `id uuid pk` — word identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — owning build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `intro_order int not null` — canonical introduction order across the course.
    intro_order: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `canonical_writing_ja text not null` — canonical Japanese writing form.
    canonical_writing_ja: Mapped[str] = mapped_column(Text, nullable=False)
    # * `reading_kana text not null` — kana reading.
    reading_kana: Mapped[str] = mapped_column(Text, nullable=False)
    # * `gloss_primary_en text not null` — primary English gloss.
    gloss_primary_en: Mapped[str] = mapped_column(Text, nullable=False)
    # * `gloss_alternatives_en text[] not null` — up to two alternate glosses.
    gloss_alternatives_en: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    # * `usage_note_en text null` — usage nuance or restriction note.
    usage_note_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    # * `pos text not null` — part of speech.
    pos: Mapped[str] = mapped_column(Text, nullable=False)
    # * `is_safe_pool bool not null default false` — whether the word is part of the configured safe/support subset.
    is_safe_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `is_bootstrap_seed bool not null default false` — whether the word came from bootstrap seed config.
    is_bootstrap_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `source_kind text not null default 'llm'` — origin marker such as `llm|manual_seed|manual_support|pattern:<code>`.
    source_kind: Mapped[str] = mapped_column(Text, nullable=False, default="llm", server_default="llm")
    # * `unique (course_version_id, intro_order)` — stable intro order.
    # * `unique (course_version_id, canonical_writing_ja, reading_kana)` — prevents duplicate lexemes.


# `word_theme_links`
#
# **Purpose:** maps words to themes.
class WordThemeLink(Base):
    __tablename__ = "word_theme_links"

    # * `word_id uuid fk words` — linked word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `theme_tag_id uuid fk theme_tags` — linked theme.
    theme_tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("theme_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `primary key (word_id, theme_tag_id)` — uniqueness.


# `sections`
#
# **Purpose:** config-defined pedagogical chunks of the course.
class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (
        UniqueConstraint("course_version_id", "order_index", name="uq_sections_course_order_index"),
        UniqueConstraint("course_version_id", "code", name="uq_sections_course_code"),
    )

    # * `id uuid pk` — section identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — owning build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `code text not null` — stable config section code.
    code: Mapped[str] = mapped_column(Text, nullable=False)
    # * `order_index int not null` — section order.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `title text not null` — section title.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # * `description text not null` — user-facing section summary.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # * `generation_description text not null` — LLM-facing generation scope summary.
    generation_description: Mapped[str] = mapped_column(Text, nullable=False)
    # * `target_unit_count int not null` — intended number of units.
    target_unit_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `target_new_word_count int not null` — intended number of new words in the section.
    target_new_word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `unique (course_version_id, order_index)` — stable ordering.


# `section_theme_links`
#
# **Purpose:** themes active in a section.
class SectionThemeLink(Base):
    __tablename__ = "section_theme_links"

    # * `section_id uuid fk sections` — section.
    section_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `theme_tag_id uuid fk theme_tags` — theme.
    theme_tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("theme_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `primary key (section_id, theme_tag_id)` — uniqueness.


# `section_pattern_links`
#
# **Purpose:** patterns included in a section.
class SectionPatternLink(Base):
    __tablename__ = "section_pattern_links"

    # * `section_id uuid fk sections` — section.
    section_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `pattern_id uuid fk patterns` — pattern.
    pattern_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `role text not null` — `introduce|review|mastery`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (section_id, pattern_id)` — uniqueness.


# `section_words`
#
# **Purpose:** words assigned to a section's vocabulary scope.
class SectionWord(Base):
    __tablename__ = "section_words"

    # * `section_id uuid fk sections` — section.
    section_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sections.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `word_id uuid fk words` — word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `role text not null` — `new|review|safe_allowed`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (section_id, word_id)` — uniqueness.


# `units`
#
# **Purpose:** LLM-planned units inside a section.
class Unit(Base):
    __tablename__ = "units"
    __table_args__ = (UniqueConstraint("section_id", "order_index", name="uq_units_section_order_index"),)

    # * `id uuid pk` — unit identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `section_id uuid fk sections` — parent section.
    section_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sections.id", ondelete="CASCADE"), nullable=False
    )
    # * `order_index int not null` — order inside section.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `title text not null` — internal/user-facing unit title.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    # * `description text not null` — internal/user-facing unit summary.
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (section_id, order_index)` — stable ordering.


# `unit_theme_links`
#
# **Purpose:** themes active in a unit.
class UnitThemeLink(Base):
    __tablename__ = "unit_theme_links"

    # * `unit_id uuid fk units` — unit.
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True
    )
    # * `theme_tag_id uuid fk theme_tags` — theme.
    theme_tag_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("theme_tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `primary key (unit_id, theme_tag_id)` — uniqueness.


# `unit_pattern_links`
#
# **Purpose:** patterns introduced or reviewed in a unit.
class UnitPatternLink(Base):
    __tablename__ = "unit_pattern_links"

    # * `unit_id uuid fk units` — unit.
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True
    )
    # * `pattern_id uuid fk patterns` — pattern.
    pattern_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `role text not null` — `introduce|review|mastery`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (unit_id, pattern_id)` — uniqueness.


# `unit_words`
#
# **Purpose:** words allocated to a unit.
class UnitWord(Base):
    __tablename__ = "unit_words"

    # * `unit_id uuid fk units` — unit.
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("units.id", ondelete="CASCADE"), primary_key=True
    )
    # * `word_id uuid fk words` — word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `role text not null` — `new|review|safe_allowed`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (unit_id, word_id)` — uniqueness.


# `planned_units`
#
# **Purpose:** persisted deterministic curriculum plan before unit materialization.
class PlannedUnit(Base):
    __tablename__ = "planned_units"
    __table_args__ = (UniqueConstraint("section_id", "order_index", name="uq_planned_units_section_order"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    section_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_theme_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    pattern_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)


# `planned_lessons`
#
# **Purpose:** persisted deterministic lesson plan before lesson materialization.
class PlannedLesson(Base):
    __tablename__ = "planned_lessons"
    __table_args__ = (UniqueConstraint("planned_unit_id", "order_index", name="uq_planned_lessons_unit_order"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    planned_unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("planned_units.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    force_kana_display: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    target_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    introduced_word_lemmas: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    kanji_focus_word_lemmas: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    target_word_lemmas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_pattern_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    target_pattern_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_pattern_examples: Mapped[list[dict[str, object]]] = mapped_column(JSONB, nullable=False)
    available_word_lemmas: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    available_pattern_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    target_pattern_sentence_count: Mapped[int] = mapped_column(Integer, nullable=False)


# `lessons`
#
# **Purpose:** sequential lessons inside a unit.
#
# Rules in code:
#
# * lesson titles are not needed
# * lessons unlock sequentially
# * last lesson must be `exam`
class Lesson(Base):
    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("unit_id", "order_index", name="uq_lessons_unit_order_index"),)

    # * `id uuid pk` — lesson identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `unit_id uuid fk units` — parent unit.
    unit_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("units.id", ondelete="CASCADE"), nullable=False
    )
    # * `order_index int not null` — order inside unit.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `kind text not null` — `normal|review_previous_units|exam`.
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    # * `force_kana_display bool not null default false` — whether Japanese surfaces should render in kana for this lesson.
    force_kana_display: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `target_item_count int not null` — expected number of items.
    target_item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `unique (unit_id, order_index)` — stable ordering.


# `lesson_words`
#
# **Purpose:** vocabulary pool allowed for a lesson.
class LessonWord(Base):
    __tablename__ = "lesson_words"

    # * `lesson_id uuid fk lessons` — lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `word_id uuid fk words` — word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `role text not null` — `new|review|safe_allowed`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (lesson_id, word_id)` — uniqueness.


# `lesson_pattern_links`
#
# **Purpose:** pattern pool allowed for a lesson.
class LessonPatternLink(Base):
    __tablename__ = "lesson_pattern_links"

    # * `lesson_id uuid fk lessons` — lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `pattern_id uuid fk patterns` — pattern.
    pattern_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `role text not null` — `new|review|mastery`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (lesson_id, pattern_id)` — uniqueness.


# `sentences`
#
# **Purpose:** generated bilingual sentence pairs.
class Sentence(Base):
    __tablename__ = "sentences"
    __table_args__ = (
        UniqueConstraint(
            "course_version_id",
            "ja_text",
            "en_text",
            "target_word_id",
            "target_pattern_id",
            name="uq_sentences_course_text_target",
        ),
    )

    # * `id uuid pk` — sentence identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — owning build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `ja_text text not null` — Japanese sentence.
    ja_text: Mapped[str] = mapped_column(Text, nullable=False)
    # * `en_text text not null` — English translation.
    en_text: Mapped[str] = mapped_column(Text, nullable=False)
    # * `target_word_id uuid null fk words` — main target word if any.
    target_word_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="SET NULL"), nullable=True
    )
    # * `target_pattern_id uuid null fk patterns` — main target pattern if any.
    target_pattern_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="SET NULL"),
        nullable=True,
    )
    # * `unique (course_version_id, ja_text, en_text, target_word_id, target_pattern_id)` — one row per target context.


# `lesson_sentences`
#
# **Purpose:** assigns sentences to lessons.
#
# This table is used for:
#
# * normal lessons
# * review lessons
# * exam lessons
class LessonSentence(Base):
    __tablename__ = "lesson_sentences"

    # * `lesson_id uuid fk lessons` — lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sentences.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `order_index int not null` — stable order inside lesson.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `role text not null default 'core'` — `core|review`.
    role: Mapped[str] = mapped_column(Text, nullable=False, default="core", server_default="core")
    # * `primary key (lesson_id, sentence_id)` — uniqueness.


# `sentence_word_links`
#
# **Purpose:** which words are used in a sentence.
class SentenceWordLink(Base):
    __tablename__ = "sentence_word_links"

    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sentences.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `word_id uuid fk words` — used word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `role text not null` — `target|support`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (sentence_id, word_id)` — uniqueness.


# `sentence_pattern_links`
#
# **Purpose:** which patterns are used in a sentence.
class SentencePatternLink(Base):
    __tablename__ = "sentence_pattern_links"

    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sentences.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `pattern_id uuid fk patterns` — pattern.
    pattern_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `role text not null` — `target|support`.
    role: Mapped[str] = mapped_column(Text, nullable=False)
    # * `primary key (sentence_id, pattern_id)` — uniqueness.


# `sentence_units`
#
# **Purpose:** deterministic sentence units used for hints and sentence tiles.
class SentenceUnit(Base):
    __tablename__ = "sentence_units"
    __table_args__ = (UniqueConstraint("sentence_id", "lang", "unit_index", name="uq_sentence_units_index"),)

    # * `id uuid pk` — sentence-unit row id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    # * `lang text not null` — `ja|en`.
    lang: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unit_index int not null` — sentence-unit position.
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `surface text not null` — displayed sentence unit surface.
    surface: Mapped[str] = mapped_column(Text, nullable=False)
    # * `lemma text null` — canonical underlying lemma/chunk text.
    lemma: Mapped[str | None] = mapped_column(Text, nullable=True)
    # * `reading text null` — kana reading for Japanese units.
    reading: Mapped[str | None] = mapped_column(Text, nullable=True)
    # * `pos text null` — primary part of speech for the unit.
    pos: Mapped[str | None] = mapped_column(Text, nullable=True)
    # * `unique (sentence_id, lang, unit_index)` — stable ordering.


# `sentence_tile_sets`
#
# **Purpose:** one deterministic answer-tile segmentation per sentence per answer language.
class SentenceTileSet(Base):
    __tablename__ = "sentence_tile_sets"
    __table_args__ = (UniqueConstraint("sentence_id", "answer_lang", name="uq_sentence_tile_sets_variant"),)

    # * `id uuid pk` — tile set id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    # * `answer_lang text not null` — `ja|en`.
    answer_lang: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (sentence_id, answer_lang)` — deterministic generation.


# `sentence_tiles`
#
# **Purpose:** correct ordered answer units for a tile set.
#
# Wrong tiles are not stored.
class SentenceTile(Base):
    __tablename__ = "sentence_tiles"
    __table_args__ = (UniqueConstraint("tile_set_id", "tile_index", name="uq_sentence_tiles_order"),)

    # * `id uuid pk` — tile id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `tile_set_id uuid fk sentence_tile_sets` — parent tile set.
    tile_set_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sentence_tile_sets.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `tile_index int not null` — correct order index.
    tile_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `text text not null` — tile text.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unit_start int null` — first covered sentence-unit index.
    unit_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # * `unit_end int null` — last covered sentence-unit index.
    unit_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # * `unique (tile_set_id, tile_index)` — stable ordering.


# `items`
#
# **Purpose:** base lesson item table.
#
# Supported item types:
#
# * `word_choice`
#
# * `sentence_tiles`
#
# * `kanji_kana_match`
class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("lesson_id", "order_index", name="uq_items_lesson_order_index"),)

    # * `id uuid pk` — item identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `lesson_id uuid fk lessons` — lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    # * `order_index int not null` — order inside lesson.
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `type text not null` — `word_choice|sentence_tiles|kanji_kana_match`.
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # * `prompt_lang text not null` — `ja|en`.
    prompt_lang: Mapped[str] = mapped_column(Text, nullable=False)
    # * `answer_lang text not null` — `ja|en`.
    answer_lang: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (lesson_id, order_index)` — stable ordering.


# `item_word_choice`
#
# **Purpose:** one-word choice exercise.
#
# Runtime logic:
#
# * derive correct answer from word + prompt/answer direction
# * generate wrong options algorithmically
class ItemWordChoice(Base):
    __tablename__ = "item_word_choice"

    # * `item_id uuid pk fk items` — base item.
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    # * `word_id uuid fk words` — target word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), nullable=False
    )


# `item_sentence_tiles`
#
# **Purpose:** sentence reorder exercise.
#
# Runtime logic:
#
# * fetch correct tiles
# * generate wrong tiles algorithmically
# * shuffle
class ItemSentenceTiles(Base):
    __tablename__ = "item_sentence_tiles"

    # * `item_id uuid pk fk items` — base item.
    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    # * `sentence_id uuid fk sentences` — target sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    # * `tile_set_id uuid fk sentence_tile_sets` — correct tile set.
    tile_set_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("sentence_tile_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )


# `item_kanji_kana_match`
#
# **Purpose:** one kanji-to-kana reading match item.
class ItemKanjiKanaMatch(Base):
    __tablename__ = "item_kanji_kana_match"

    item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("items.id", ondelete="CASCADE"), primary_key=True
    )
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), nullable=False
    )
    prompt_script: Mapped[str] = mapped_column(Text, nullable=False)
    answer_script: Mapped[str] = mapped_column(Text, nullable=False)


# `kanji`
#
# **Purpose:** canonical kanji inventory used in the course.
class Kanji(Base):
    __tablename__ = "kanji"

    # * `char text pk` — kanji character.
    char: Mapped[str] = mapped_column(Text, primary_key=True)
    # * `primary_meaning text null` — short display meaning.
    primary_meaning: Mapped[str | None] = mapped_column(Text, nullable=True)


# `word_kanji_links`
#
# **Purpose:** which kanji appear in which words.
class WordKanjiLink(Base):
    __tablename__ = "word_kanji_links"

    # * `word_id uuid fk words` — word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `kanji_char text fk kanji(char)` — kanji.
    kanji_char: Mapped[str] = mapped_column(Text, ForeignKey("kanji.char", ondelete="CASCADE"), primary_key=True)
    # * `order_index int not null` — order inside the word.
    order_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    # * `primary key (word_id, kanji_char, order_index)` — uniqueness.


# `kanji_introductions`
#
# **Purpose:** when a kanji usage is introduced in a lesson.
class KanjiIntroduction(Base):
    __tablename__ = "kanji_introductions"
    __table_args__ = (
        UniqueConstraint(
            "course_version_id",
            "lesson_id",
            "kanji_char",
            "example_word_ja",
            name="uq_kanji_introductions_unique_usage",
        ),
    )

    # * `id uuid pk` — introduction id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `course_version_id uuid fk course_versions` — build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `lesson_id uuid fk lessons` — lesson where usage is first introduced.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    # * `kanji_char text fk kanji(char)` — introduced kanji.
    kanji_char: Mapped[str] = mapped_column(Text, ForeignKey("kanji.char", ondelete="CASCADE"), nullable=False)
    # * `word_id uuid fk words` — word used for introduction.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), nullable=False
    )
    # * `example_word_ja text not null` — displayed example word.
    example_word_ja: Mapped[str] = mapped_column(Text, nullable=False)
    # * `example_reading text null` — displayed reading.
    example_reading: Mapped[str | None] = mapped_column(Text, nullable=True)
    # * `meaning_en text not null` — displayed meaning.
    meaning_en: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unique (course_version_id, lesson_id, kanji_char, example_word_ja)` — prevents duplicates.
