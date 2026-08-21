"""Create the profile this deployment serves, if it does not exist yet.

Not part of the container entrypoint: the dashboard asks who you are on first
run, which is friendlier than inventing a placeholder name you would then want
to change. This script is for the headless cases — an API-only deployment, a
smoke test, loading the demo data before any browser is involved.

    python -m scripts.ensure_user
"""

from __future__ import annotations

import sys

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User


def ensure_user(db: Session) -> tuple[User | None, str]:
    """Return the single user and what had to happen to get it."""
    existing = db.execute(select(User).order_by(User.id).limit(1)).scalar_one_or_none()
    if existing is not None:
        total = db.execute(select(func.count(User.id))).scalar() or 0
        note = "" if total == 1 else f" ({total} users present, using the lowest id)"
        return existing, f"already present{note}"

    user = User(first_name=settings.default_first_name, last_name=settings.default_last_name)
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Another process got there first; that is a success, not a clash.
        db.rollback()
        winner = db.execute(select(User).order_by(User.id).limit(1)).scalar_one_or_none()
        return winner, "created concurrently"
    db.refresh(user)
    return user, "created"


def main() -> int:
    try:
        with SessionLocal() as db:
            user, outcome = ensure_user(db)
    except SQLAlchemyError as exc:
        print(f"Could not reach the database: {exc}", file=sys.stderr)
        return 1
    if user is None:
        print("No user could be established", file=sys.stderr)
        return 1
    print(f"user {user.id} ({user.full_name}): {outcome}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
