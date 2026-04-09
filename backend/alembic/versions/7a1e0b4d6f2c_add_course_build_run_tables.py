"""add course build run tables"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '7a1e0b4d6f2c'
down_revision = '940f4184d2b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'course_build_runs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('workflow_id', sa.Text(), nullable=True),
        sa.Column('build_version', sa.Integer(), nullable=False),
        sa.Column('config_path', sa.Text(), nullable=False),
        sa.Column('scope_kind', sa.Text(), nullable=False),
        sa.Column('section_code', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('requested_by', sa.Text(), nullable=True),
        sa.Column('course_version_id', postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column('all_stages', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('completed_stage_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_stage_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_stage_name', sa.Text(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['course_version_id'], ['course_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_course_build_runs_build_version', 'course_build_runs', ['build_version'], unique=False)
    op.create_index('ix_course_build_runs_course_version_id', 'course_build_runs', ['course_version_id'], unique=False)
    op.create_index('ix_course_build_runs_status', 'course_build_runs', ['status'], unique=False)
    op.create_table(
        'course_build_stage_runs',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('build_run_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('section_code', sa.Text(), nullable=False),
        sa.Column('stage_name', sa.Text(), nullable=False),
        sa.Column('stage_index', sa.Integer(), nullable=False),
        sa.Column('status', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['build_run_id'], ['course_build_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('build_run_id', 'section_code', 'stage_index', name='uq_course_build_stage_runs_scope'),
    )
    op.create_index('ix_course_build_stage_runs_build_run_id', 'course_build_stage_runs', ['build_run_id'], unique=False)
    op.create_index('ix_course_build_stage_runs_status', 'course_build_stage_runs', ['status'], unique=False)
    op.create_table(
        'course_build_log_events',
        sa.Column('id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('build_run_id', postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column('section_code', sa.Text(), nullable=True),
        sa.Column('stage_name', sa.Text(), nullable=True),
        sa.Column('level', sa.Text(), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['build_run_id'], ['course_build_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_course_build_log_events_build_run_id', 'course_build_log_events', ['build_run_id'], unique=False)
    op.create_index('ix_course_build_log_events_created_at', 'course_build_log_events', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_course_build_log_events_created_at', table_name='course_build_log_events')
    op.drop_index('ix_course_build_log_events_build_run_id', table_name='course_build_log_events')
    op.drop_table('course_build_log_events')
    op.drop_index('ix_course_build_stage_runs_status', table_name='course_build_stage_runs')
    op.drop_index('ix_course_build_stage_runs_build_run_id', table_name='course_build_stage_runs')
    op.drop_table('course_build_stage_runs')
    op.drop_index('ix_course_build_runs_status', table_name='course_build_runs')
    op.drop_index('ix_course_build_runs_course_version_id', table_name='course_build_runs')
    op.drop_index('ix_course_build_runs_build_version', table_name='course_build_runs')
    op.drop_table('course_build_runs')
