from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# `user_lesson_progress`
#
# **Purpose:** minimal per-lesson progress state.
class UserLessonProgress(Base):
    __tablename__ = "user_lesson_progress"

    # * `enrollment_id uuid fk user_course_enrollments` — enrollment.
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `lesson_id uuid fk lessons` — lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True
    )
    # * `state text not null` — `not_started|in_progress|completed`.
    state: Mapped[str] = mapped_column(Text, nullable=False)
    # * `updated_at timestamptz not null default now()` — last update timestamp.
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `primary key (enrollment_id, lesson_id)` — uniqueness.


# `exam_attempts`
#
# **Purpose:** stores exam tries.
#
# The attempt limit policy is enforced in code, not schema.
class ExamAttempt(Base):
    __tablename__ = "exam_attempts"

    # * `id uuid pk` — attempt id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `enrollment_id uuid fk user_course_enrollments` — enrollment.
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `lesson_id uuid fk lessons` — exam lesson.
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False
    )
    # * `attempt_no int not null` — attempt sequence.
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `started_at timestamptz not null default now()` — start time.
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `submitted_at timestamptz null` — finish time.
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # * `score real null` — score.
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # * `passed bool null` — result.
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


# `user_words_learned`
#
# **Purpose:** materialized learned words.
class UserWordLearned(Base):
    __tablename__ = "user_words_learned"

    # * `enrollment_id uuid fk user_course_enrollments` — enrollment.
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `word_id uuid fk words` — learned word.
    word_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("words.id", ondelete="CASCADE"), primary_key=True
    )
    # * `learned_at timestamptz not null default now()` — learning timestamp.
    learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `primary key (enrollment_id, word_id)` — uniqueness.


# `user_pattern_learned`
#
# **Purpose:** materialized learned patterns.
class UserPatternLearned(Base):
    __tablename__ = "user_pattern_learned"

    # * `enrollment_id uuid fk user_course_enrollments` — enrollment.
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `pattern_id uuid fk patterns` — learned pattern.
    pattern_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("patterns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `learned_at timestamptz not null default now()` — learning timestamp.
    learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `primary key (enrollment_id, pattern_id)` — uniqueness.


# `user_kanji_learned`
#
# **Purpose:** materialized learned kanji.
class UserKanjiLearned(Base):
    __tablename__ = "user_kanji_learned"

    # * `enrollment_id uuid fk user_course_enrollments` — enrollment.
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # * `kanji_char text fk kanji(char)` — learned kanji.
    kanji_char: Mapped[str] = mapped_column(Text, ForeignKey("kanji.char", ondelete="CASCADE"), primary_key=True)
    # * `learned_at timestamptz not null default now()` — learning timestamp.
    learned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `primary key (enrollment_id, kanji_char)` — uniqueness.
