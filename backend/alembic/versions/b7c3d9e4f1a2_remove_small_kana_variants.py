"""remove small kana variants

Revision ID: b7c3d9e4f1a2
Revises: a91b3e4c2d1f
Create Date: 2026-04-12 14:58:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c3d9e4f1a2"
down_revision = "a91b3e4c2d1f"
branch_labels = None
depends_on = None


SMALL_KANA_CHARS = (
    "ぁ",
    "ぃ",
    "ぅ",
    "ぇ",
    "ぉ",
    "ゃ",
    "ゅ",
    "ょ",
    "っ",
    "ゎ",
    "ゕ",
    "ゖ",
    "ァ",
    "ィ",
    "ゥ",
    "ェ",
    "ォ",
    "ャ",
    "ュ",
    "ョ",
    "ッ",
    "ヮ",
    "ヵ",
    "ヶ",
)


def upgrade() -> None:
    bind = op.get_bind()

    small_ids = [
        row[0]
        for row in bind.execute(
            sa.text("SELECT id FROM kana_characters WHERE char = ANY(:chars)"),
            {"chars": list(SMALL_KANA_CHARS)},
        )
    ]

    if small_ids:
        bind.execute(
            sa.text(
                """
                DELETE FROM kana_lessons
                WHERE id IN (
                    SELECT DISTINCT lesson_id
                    FROM kana_lesson_items
                    WHERE prompt_character_id = ANY(:small_ids)
                       OR option_character_ids && CAST(:small_ids AS uuid[])
                )
                """
            ),
            {"small_ids": small_ids},
        )
        bind.execute(
            sa.text("DELETE FROM user_kana_progress WHERE character_id = ANY(:small_ids)"),
            {"small_ids": small_ids},
        )
        bind.execute(
            sa.text("DELETE FROM kana_audio_assets WHERE character_id = ANY(:small_ids)"),
            {"small_ids": small_ids},
        )
        bind.execute(
            sa.text("DELETE FROM kana_characters WHERE id = ANY(:small_ids)"),
            {"small_ids": small_ids},
        )

    op.drop_column("kana_characters", "is_small_variant")


def downgrade() -> None:
    op.add_column(
        "kana_characters",
        sa.Column("is_small_variant", sa.Boolean(), nullable=False, server_default="false"),
    )
