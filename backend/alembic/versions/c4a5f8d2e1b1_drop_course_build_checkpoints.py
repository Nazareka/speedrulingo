"""drop course build checkpoints"""

from alembic import op

revision = "c4a5f8d2e1b1"
down_revision = "7a1e0b4d6f2c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_course_build_checkpoints_course_version_id", table_name="course_build_checkpoints")
    op.drop_table("course_build_checkpoints")


def downgrade() -> None:
    raise NotImplementedError("Downgrading dropped course_build_checkpoints is not supported.")
