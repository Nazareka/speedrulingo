from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class KanaCharacter(Base):
    __tablename__ = "kana_characters"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    char: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    script: Mapped[str] = mapped_column(Text, nullable=False)
    sound_text: Mapped[str] = mapped_column(Text, nullable=False)
    group_key: Mapped[str] = mapped_column(Text, nullable=False)
    group_order: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_rank: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    target_exposures: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    base_char: Mapped[str | None] = mapped_column(Text, ForeignKey("kana_characters.char", ondelete="SET NULL"), nullable=True)
    is_voiced: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")


class KanaAudioAsset(Base):
    __tablename__ = "kana_audio_assets"
    __table_args__ = (
        UniqueConstraint(
            "character_id",
            "provider",
            "voice_id",
            "model_id",
            "text_hash",
            name="uq_kana_audio_assets_identity",
        ),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    audio_asset_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("audio_assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    character_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kana_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    voice_id: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(Text, nullable=False)
    language_code: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    generation_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class UserKanaProgress(Base):
    __tablename__ = "user_kana_progress"

    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        primary_key=True,
    )
    character_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kana_characters.id", ondelete="CASCADE"),
        primary_key=True,
    )
    times_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    times_prompted_as_character: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    times_prompted_as_audio: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    state: Mapped[str] = mapped_column(Text, nullable=False, default="new", server_default="new")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class KanaLesson(Base):
    __tablename__ = "kana_lessons"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    enrollment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("user_course_enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="planned", server_default="planned")
    total_items: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class KanaLessonItem(Base):
    __tablename__ = "kana_lesson_items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    lesson_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kana_lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    item_type: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_character_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("kana_characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    option_character_ids: Mapped[list[str]] = mapped_column(ARRAY(UUID(as_uuid=False)), nullable=False)
    correct_option_index: Mapped[int] = mapped_column(Integer, nullable=False)
