"""add sentence audio assets

Revision ID: f2b0c7e1d4a9
Revises: e8b2f4a1c6d7
Create Date: 2026-04-09 13:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b0c7e1d4a9"
down_revision: str | None = "e8b2f4a1c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sentence_audio_assets",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("sentence_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("voice_id", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("language_code", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("generation_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["sentence_id"], ["sentences.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sentence_id",
            "provider",
            "voice_id",
            "model_id",
            "text_hash",
            name="uq_sentence_audio_assets_identity",
        ),
    )


def downgrade() -> None:
    op.drop_table("sentence_audio_assets")
