"""Replace username and email with a first and last name.

Revision ID: 0004_profile_is_a_name
Revises: 0003_workout_file_hash
Create Date: 2026-08-21

With one user and no authentication there is nothing to log in as and nothing
to send mail to, so the profile is just a name. The dashboard asks for it on
first run.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_profile_is_a_name"
down_revision: str | None = "0003_workout_file_hash"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_LENGTH = 120


def upgrade() -> None:
    # Added nullable and backfilled from the old username, so the NOT NULL
    # below holds even where rows already exist.
    op.add_column("users", sa.Column("first_name", sa.String(length=NAME_LENGTH), nullable=True))
    op.add_column("users", sa.Column("last_name", sa.String(length=NAME_LENGTH), nullable=True))
    op.execute("UPDATE users SET first_name = username WHERE first_name IS NULL")

    # Batch mode so this also applies on SQLite, which cannot ALTER a column or
    # drop an indexed one in place.
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "first_name", existing_type=sa.String(length=NAME_LENGTH), nullable=False
        )
        batch.drop_index("ix_users_username")
        batch.drop_index("ix_users_email")
        batch.drop_column("username")
        batch.drop_column("email")


def downgrade() -> None:
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    # The old columns were unique, so the backfill has to be too.
    op.execute("UPDATE users SET username = 'user' || id, email = 'user' || id || '@localhost'")

    with op.batch_alter_table("users") as batch:
        batch.alter_column("username", existing_type=sa.String(length=64), nullable=False)
        batch.alter_column("email", existing_type=sa.String(length=255), nullable=False)
        batch.create_index("ix_users_username", ["username"], unique=True)
        batch.create_index("ix_users_email", ["email"], unique=True)
        batch.drop_column("last_name")
        batch.drop_column("first_name")
