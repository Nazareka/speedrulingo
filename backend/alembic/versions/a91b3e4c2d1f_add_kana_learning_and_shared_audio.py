"""add kana learning and shared audio

Revision ID: a91b3e4c2d1f
Revises: 5a1c3f9b2e8d
Create Date: 2026-04-11 16:10:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a91b3e4c2d1f"
down_revision: str | None = "5a1c3f9b2e8d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audio_assets",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "voice_id", "model_id", "text_hash", name="uq_audio_assets_identity"),
    )

    op.add_column("sentence_audio_assets", sa.Column("audio_asset_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("word_audio_assets", sa.Column("audio_asset_id", postgresql.UUID(as_uuid=False), nullable=True))

    bind = op.get_bind()
    metadata = sa.MetaData()
    audio_assets = sa.Table("audio_assets", metadata, autoload_with=bind)
    sentence_audio_assets = sa.Table("sentence_audio_assets", metadata, autoload_with=bind)
    word_audio_assets = sa.Table("word_audio_assets", metadata, autoload_with=bind)

    asset_id_by_identity: dict[tuple[str, str, str, str], str] = {}
    rows = list(
        bind.execute(
            sa.select(
                sentence_audio_assets.c.id,
                sentence_audio_assets.c.provider,
                sentence_audio_assets.c.voice_id,
                sentence_audio_assets.c.model_id,
                sentence_audio_assets.c.language_code,
                sentence_audio_assets.c.text_hash,
                sentence_audio_assets.c.source_text,
                sentence_audio_assets.c.storage_path,
                sentence_audio_assets.c.mime_type,
                sentence_audio_assets.c.byte_size,
                sentence_audio_assets.c.status,
                sentence_audio_assets.c.created_at,
                sentence_audio_assets.c.updated_at,
                sentence_audio_assets.c.generation_error,
            )
        )
    )
    rows.extend(
        bind.execute(
            sa.select(
                word_audio_assets.c.id,
                word_audio_assets.c.provider,
                word_audio_assets.c.voice_id,
                word_audio_assets.c.model_id,
                word_audio_assets.c.language_code,
                word_audio_assets.c.text_hash,
                word_audio_assets.c.source_text,
                word_audio_assets.c.storage_path,
                word_audio_assets.c.mime_type,
                word_audio_assets.c.byte_size,
                word_audio_assets.c.status,
                word_audio_assets.c.created_at,
                word_audio_assets.c.updated_at,
                word_audio_assets.c.generation_error,
            )
        )
    )
    for row in rows:
        identity = (row.provider, row.voice_id, row.model_id, row.text_hash)
        if identity in asset_id_by_identity:
            continue
        audio_asset_id = str(uuid4())
        asset_id_by_identity[identity] = audio_asset_id
        bind.execute(
            audio_assets.insert().values(
                id=audio_asset_id,
                provider=row.provider,
                voice_id=row.voice_id,
                model_id=row.model_id,
                language_code=row.language_code,
                text_hash=row.text_hash,
                source_text=row.source_text,
                storage_path=row.storage_path,
                mime_type=row.mime_type,
                byte_size=row.byte_size,
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
                generation_error=row.generation_error,
            )
        )

    for table in (sentence_audio_assets, word_audio_assets):
        for row in bind.execute(sa.select(table.c.id, table.c.provider, table.c.voice_id, table.c.model_id, table.c.text_hash)):
            bind.execute(
                table.update()
                .where(table.c.id == row.id)
                .values(audio_asset_id=asset_id_by_identity[row.provider, row.voice_id, row.model_id, row.text_hash])
            )

    op.alter_column("sentence_audio_assets", "audio_asset_id", nullable=False)
    op.alter_column("word_audio_assets", "audio_asset_id", nullable=False)
    op.create_foreign_key(
        "fk_sentence_audio_assets_audio_asset_id",
        "sentence_audio_assets",
        "audio_assets",
        ["audio_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_word_audio_assets_audio_asset_id",
        "word_audio_assets",
        "audio_assets",
        ["audio_asset_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.create_table(
        "kana_characters",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("char", sa.Text(), nullable=False),
        sa.Column("script", sa.Text(), nullable=False),
        sa.Column("sound_text", sa.Text(), nullable=False),
        sa.Column("group_key", sa.Text(), nullable=False),
        sa.Column("group_order", sa.Integer(), nullable=False),
        sa.Column("difficulty_rank", sa.Integer(), nullable=False),
        sa.Column("target_exposures", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("base_char", sa.Text(), nullable=True),
        sa.Column("is_voiced", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_small_variant", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["base_char"], ["kana_characters.char"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("char"),
        sa.UniqueConstraint("difficulty_rank"),
    )
    op.create_table(
        "kana_audio_assets",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("audio_asset_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=False), nullable=False),
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
        sa.ForeignKeyConstraint(["audio_asset_id"], ["audio_assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["character_id"], ["kana_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "character_id",
            "provider",
            "voice_id",
            "model_id",
            "text_hash",
            name="uq_kana_audio_assets_identity",
        ),
    )
    op.create_table(
        "user_kana_progress",
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("character_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("times_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("times_prompted_as_character", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("times_prompted_as_audio", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("state", sa.Text(), nullable=False, server_default="new"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["character_id"], ["kana_characters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["user_course_enrollments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("enrollment_id", "character_id"),
    )
    op.create_table(
        "kana_lessons",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("enrollment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="planned"),
        sa.Column("total_items", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["enrollment_id"], ["user_course_enrollments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "kana_lesson_items",
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.Text(), nullable=False),
        sa.Column("prompt_character_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("option_character_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=False)), nullable=False),
        sa.Column("correct_option_index", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["kana_lessons.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_character_id"], ["kana_characters.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("kana_lesson_items")
    op.drop_table("kana_lessons")
    op.drop_table("user_kana_progress")
    op.drop_table("kana_audio_assets")
    op.drop_table("kana_characters")
    op.drop_constraint("fk_word_audio_assets_audio_asset_id", "word_audio_assets", type_="foreignkey")
    op.drop_constraint("fk_sentence_audio_assets_audio_asset_id", "sentence_audio_assets", type_="foreignkey")
    op.drop_column("word_audio_assets", "audio_asset_id")
    op.drop_column("sentence_audio_assets", "audio_asset_id")
    op.drop_table("audio_assets")
