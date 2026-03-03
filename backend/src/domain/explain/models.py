from __future__ import annotations

from uuid import uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# `sentence_unit_hints`
#
# **Purpose:** source-backed quick hints for tappable sentence units.
class SentenceUnitHint(Base):
    __tablename__ = "sentence_unit_hints"

    # * `id uuid pk` — sentence-unit hint identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `sentence_id uuid fk sentences` — sentence.
    sentence_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    # * `lang text not null` — `ja|en`.
    lang: Mapped[str] = mapped_column(Text, nullable=False)
    # * `unit_index int not null` — target sentence-unit index.
    unit_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # * `hint_text text not null` — deterministic gloss hint text.
    hint_text: Mapped[str] = mapped_column(Text, nullable=False)
    # * `hint_kind text not null` — currently `gloss`.
    hint_kind: Mapped[str] = mapped_column(Text, nullable=False)
    # * `is_new bool not null default false` — whether unit corresponds to newly introduced material.
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
