"""Initial schema: users, workouts, track_points.

Self-contained on purpose: a revision is a snapshot of the schema at a point in
time, so it declares its own column types rather than importing them from the
models. Importing would keep the two textually in sync, but it would also let a
later model change silently alter what this revision means. `alembic check` in
CI is what actually guards against drift.

The variants keep this applicable to SQLite as well as PostgreSQL, so the
test suite needs no database.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-20

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

#: JSONB on PostgreSQL, portable JSON elsewhere.
JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
#: SQLite has no autoincrementing BIGINT primary key.
BIG_PK_TYPE = sa.BigInteger().with_variant(sa.Integer(), "sqlite")

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "workouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sport_type", sa.String(length=64), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_distance", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_elevation_gain", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_elevation_loss", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_time", sa.Float(), nullable=False, server_default="0"),
        sa.Column("avg_heart_rate", sa.Integer(), nullable=True),
        sa.Column("max_heart_rate", sa.Integer(), nullable=True),
        sa.Column("avg_cadence", sa.Integer(), nullable=True),
        sa.Column("file_format", sa.String(length=8), nullable=False),
        sa.Column("raw_data", JSON_TYPE, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "start_time", "source", name="uq_workout_user_start_source"),
    )
    op.create_index("ix_workouts_user_id", "workouts", ["user_id"])
    op.create_index("ix_workouts_sport_type", "workouts", ["sport_type"])
    op.create_index("ix_workouts_start_time", "workouts", ["start_time"])

    op.create_table(
        "track_points",
        sa.Column("id", BIG_PK_TYPE, primary_key=True, autoincrement=True),
        sa.Column("workout_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("elevation", sa.Float(), nullable=True),
        sa.Column("heart_rate", sa.Integer(), nullable=True),
        sa.Column("cadence", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["workout_id"], ["workouts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_track_points_workout_sequence", "track_points", ["workout_id", "sequence"])


def downgrade() -> None:
    op.drop_table("track_points")
    op.drop_table("workouts")
    op.drop_table("users")
