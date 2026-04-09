"""add parent build run id to course build runs

Revision ID: e8b2f4a1c6d7
Revises: d1a4b7c9e2f3
Create Date: 2026-04-06 13:05:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e8b2f4a1c6d7"
down_revision: str | Sequence[str] | None = "d1a4b7c9e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "course_build_runs",
        sa.Column("parent_build_run_id", postgresql.UUID(as_uuid=False), nullable=True),
    )
    op.create_foreign_key(
        "fk_course_build_runs_parent_build_run_id",
        "course_build_runs",
        "course_build_runs",
        ["parent_build_run_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_course_build_runs_parent_build_run_id", "course_build_runs", type_="foreignkey")
    op.drop_column("course_build_runs", "parent_build_run_id")
