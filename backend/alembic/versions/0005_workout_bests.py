"""Store each activity's fastest window over the standard distances.

Revision ID: 0005_workout_bests
Revises: 0004_profile_is_a_name
Create Date: 2026-08-21

Creating the table is all this does. The figures themselves come from the
track points, which means running the haversine and window code in
app.services.records — application logic that a migration has no business
importing, and that would rewrite the whole table on every deploy. Activities
already stored are filled in by scripts/backfill_bests.py, which is safe to
run repeatedly; activities stored from here on are computed as they arrive.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_workout_bests"
down_revision: str | None = "0004_profile_is_a_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workout_bests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("workout_id", sa.Integer(), nullable=False),
        sa.Column("distance_m", sa.Integer(), nullable=False),
        sa.Column("duration_s", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["workout_id"], ["workouts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workout_id", "distance_m", name="uq_workout_best_distance"),
    )
    op.create_index("ix_workout_bests_workout_id", "workout_bests", ["workout_id"], unique=False)
    op.create_index(
        "ix_workout_bests_distance_duration",
        "workout_bests",
        ["distance_m", "duration_s"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_workout_bests_distance_duration", table_name="workout_bests")
    op.drop_index("ix_workout_bests_workout_id", table_name="workout_bests")
    op.drop_table("workout_bests")
