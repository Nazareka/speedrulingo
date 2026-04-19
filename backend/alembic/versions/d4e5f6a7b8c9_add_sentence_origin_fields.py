"""add sentence origin fields

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-04-14 00:00:01.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sentences",
        sa.Column("source_kind", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
    )
    op.add_column("sentences", sa.Column("generation_pipeline", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE sentences
            SET source_kind = CASE
                WHEN target_pattern_id IS NOT NULL THEN 'config_example'
                WHEN target_word_id IS NOT NULL THEN COALESCE(words.source_kind, 'manual')
                ELSE 'manual'
            END,
                generation_pipeline = CASE
                WHEN target_word_id IS NOT NULL THEN words.generation_pipeline
                ELSE NULL
            END
            FROM words
            WHERE sentences.target_word_id = words.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE sentences
            SET source_kind = 'config_example',
                generation_pipeline = NULL
            WHERE target_pattern_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("sentences", "generation_pipeline")
    op.drop_column("sentences", "source_kind")
