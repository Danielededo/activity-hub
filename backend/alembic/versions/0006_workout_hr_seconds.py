"""Store how long each activity spent at each heart rate.

Revision ID: 0006_workout_hr_seconds
Revises: 0005_workout_bests
Create Date: 2026-08-21

Nullable on purpose, and nullable is load-bearing: null means the histogram has
never been computed for that activity, while an empty object means it was
computed and the file carried no usable heart rate. Without that distinction the
backfill cannot tell what it has already looked at, and rescans every
heart-rate-less activity on every run.

Filling it in is scripts/backfill_hr_zones.py, for the same reason as the
personal bests: the figures come from the track points via application code that
a migration has no business importing.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006_workout_hr_seconds"
down_revision: str | None = "0005_workout_bests"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workouts",
        sa.Column(
            "hr_seconds",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("workouts", "hr_seconds")
