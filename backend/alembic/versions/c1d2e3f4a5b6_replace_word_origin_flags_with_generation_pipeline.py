"""replace word origin flags with generation pipeline

Revision ID: c1d2e3f4a5b6
Revises: b7c3d9e4f1a2
Create Date: 2026-04-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b7c3d9e4f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("words", sa.Column("generation_pipeline", sa.Text(), nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE words
            SET generation_pipeline = 'pattern_vocab_generation'
            WHERE source_kind LIKE 'pattern:%'
               OR source_kind IN ('llm', 'llm_generated')
            """
        )
    )
    op.drop_column("words", "is_safe_pool")
    op.drop_column("words", "is_bootstrap_seed")


def downgrade() -> None:
    op.add_column(
        "words",
        sa.Column("is_bootstrap_seed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "words",
        sa.Column("is_safe_pool", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute(
        sa.text(
            """
            UPDATE words
            SET is_bootstrap_seed = TRUE
            WHERE source_kind = 'manual_seed'
            """
        )
    )
    op.drop_column("words", "generation_pipeline")
