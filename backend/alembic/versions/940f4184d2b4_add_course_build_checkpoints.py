"""add course build checkpoints"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '940f4184d2b4'
down_revision = '8afbb8a8d088'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'course_build_checkpoints',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('build_version', sa.Integer(), nullable=False),
        sa.Column('section_code', sa.Text(), nullable=False),
        sa.Column('course_version_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('next_stage_index', sa.Integer(), nullable=False),
        sa.Column('last_attempted_stage_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['course_version_id'], ['course_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('build_version', 'section_code', name='uq_course_build_checkpoints_scope'),
    )
    op.create_index(
        'ix_course_build_checkpoints_course_version_id',
        'course_build_checkpoints',
        ['course_version_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_course_build_checkpoints_course_version_id', table_name='course_build_checkpoints')
    op.drop_table('course_build_checkpoints')
