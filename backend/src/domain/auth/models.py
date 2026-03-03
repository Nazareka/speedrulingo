from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


# `users`
#
# **Purpose:** application users.
class User(Base):
    __tablename__ = "users"

    # * `id uuid pk` — internal user identifier.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `email text unique not null` — login identity.
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # * `password_hash text not null` — hashed password.
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    # * `has_pro_sub bool not null default false` — reserved for future premium features.
    has_pro_sub: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `is_admin bool not null default false` — access to build/admin controls.
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    # * `created_at timestamptz not null default now()` — account creation timestamp.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


# `user_course_enrollments`
#
# **Purpose:** binds a user to a specific course build.
class UserCourseEnrollment(Base):
    __tablename__ = "user_course_enrollments"
    __table_args__ = (UniqueConstraint("user_id", "course_version_id", name="uq_user_course_enrollment"),)

    # * `id uuid pk` — enrollment id.
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    # * `user_id uuid fk users` — enrolled user.
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # * `course_version_id uuid fk course_versions` — selected course build.
    course_version_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("course_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    # * `enrolled_at timestamptz not null default now()` — start timestamp.
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # * `unique (user_id, course_version_id)` — no duplicate enrollment for same build.
