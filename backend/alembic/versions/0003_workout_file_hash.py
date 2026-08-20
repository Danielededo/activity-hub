"""Deduplicate on file content instead of on start time and source.

Revision ID: 0003_workout_file_hash
Revises: 0002_workout_utc_offset
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_workout_file_hash"
down_revision: str | None = "0002_workout_utc_offset"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HASH_LENGTH = 64  # sha256, hex encoded


def upgrade() -> None:
    # Added nullable and backfilled first, so the NOT NULL below holds even if
    # rows already exist. `||` concatenates on both PostgreSQL and SQLite.
    op.add_column("workouts", sa.Column("file_hash", sa.String(length=HASH_LENGTH), nullable=True))
    op.execute("UPDATE workouts SET file_hash = 'backfilled:' || id WHERE file_hash IS NULL")

    # Batch mode so this also applies on SQLite, which cannot ALTER a column
    # or drop a constraint in place.
    with op.batch_alter_table("workouts") as batch:
        batch.alter_column(
            "file_hash", existing_type=sa.String(length=HASH_LENGTH), nullable=False
        )
        batch.drop_constraint("uq_workout_user_start_source", type_="unique")
        batch.create_unique_constraint("uq_workout_user_file_hash", ["user_id", "file_hash"])

    op.create_index("ix_workouts_file_hash", "workouts", ["file_hash"])


def downgrade() -> None:
    op.drop_index("ix_workouts_file_hash", table_name="workouts")
    with op.batch_alter_table("workouts") as batch:
        batch.drop_constraint("uq_workout_user_file_hash", type_="unique")
        batch.create_unique_constraint(
            "uq_workout_user_start_source", ["user_id", "start_time", "source"]
        )
        batch.drop_column("file_hash")
