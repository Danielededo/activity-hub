"""Record the UTC offset an activity's file stated.

Revision ID: 0002_workout_utc_offset
Revises: 0001_initial_schema
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_workout_utc_offset"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: TCX and GPX normally write 'Z', which fixes the instant but
    # says nothing about the local hour the activity happened at.
    op.add_column("workouts", sa.Column("utc_offset_minutes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("workouts", "utc_offset_minutes")
