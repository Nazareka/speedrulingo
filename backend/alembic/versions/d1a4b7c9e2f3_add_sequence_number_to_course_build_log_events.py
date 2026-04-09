"""add sequence number to course build log events"""

import sqlalchemy as sa

from alembic import op

revision = "d1a4b7c9e2f3"
down_revision = "c4a5f8d2e1b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("CREATE SEQUENCE course_build_log_events_sequence_number_seq"))
    op.add_column(
        "course_build_log_events",
        sa.Column("sequence_number", sa.BigInteger(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            WITH ordered AS (
                SELECT id, ROW_NUMBER() OVER (ORDER BY created_at, id) AS sequence_number
                FROM course_build_log_events
            )
            UPDATE course_build_log_events AS log_events
            SET sequence_number = ordered.sequence_number
            FROM ordered
            WHERE log_events.id = ordered.id
            """
        )
    )
    op.execute(
        sa.text(
            """
            SELECT setval(
                'course_build_log_events_sequence_number_seq',
                COALESCE((SELECT MAX(sequence_number) FROM course_build_log_events), 1),
                (SELECT COUNT(*) > 0 FROM course_build_log_events)
            )
            """
        )
    )
    op.alter_column(
        "course_build_log_events",
        "sequence_number",
        server_default=sa.text("nextval('course_build_log_events_sequence_number_seq')"),
    )
    op.alter_column("course_build_log_events", "sequence_number", nullable=False)
    op.create_unique_constraint(
        "uq_course_build_log_events_sequence_number",
        "course_build_log_events",
        ["sequence_number"],
    )


def downgrade() -> None:
    raise NotImplementedError("Downgrading course_build_log_events sequence_number is not supported.")
