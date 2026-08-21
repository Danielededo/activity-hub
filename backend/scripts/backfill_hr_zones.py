"""Fill in the heart-rate histogram for activities stored before it existed.

New uploads compute their own, so this is a one-off after upgrading past
migration 0006 — and for recomputing if the histogram's own rules change.

    python -m scripts.backfill_hr_zones              # only activities with none
    python -m scripts.backfill_hr_zones --recompute  # every activity, replacing

Unlike the personal-bests backfill, this one can tell "never looked at" from
"looked at, nothing to record": null means the first, an empty object the
second. So an activity without a heart-rate strap is visited once and skipped
on every run after that, instead of being rescanned forever.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TrackPoint, Workout
from app.services.zones import heart_rate_seconds


@dataclass(slots=True)
class Outcome:
    considered: int = 0
    #: Activities that produced at least one second at a known heart rate.
    filled: int = 0
    #: Activities with no usable heart rate: recorded as empty, not left null.
    without_heart_rate: int = 0


def backfill(db: Session, *, recompute: bool = False, batch: int = 200) -> Outcome:
    """Compute and store histograms. Safe to interrupt and safe to re-run."""
    query = select(Workout.id).order_by(Workout.id)
    if not recompute:
        query = query.where(Workout.hr_seconds.is_(None))

    outcome = Outcome()
    for index, workout_id in enumerate(list(db.execute(query).scalars()), start=1):
        points = list(
            db.execute(
                select(TrackPoint.timestamp, TrackPoint.heart_rate)
                .where(TrackPoint.workout_id == workout_id)
                .order_by(TrackPoint.sequence)
            ).all()
        )
        histogram = heart_rate_seconds(points)
        db.execute(
            update(Workout)
            .where(Workout.id == workout_id)
            .values(hr_seconds={str(bpm): seconds for bpm, seconds in histogram.items()})
        )

        outcome.considered += 1
        if histogram:
            outcome.filled += 1
        else:
            outcome.without_heart_rate += 1

        # Committing in batches keeps a long run's progress if it is stopped.
        if index % batch == 0:
            db.commit()

    db.commit()
    return outcome


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Redo every activity, replacing any histogram already stored",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            outcome = backfill(db, recompute=args.recompute)
        except SQLAlchemyError as exc:
            print(f"Could not reach the database: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    print(
        f"{outcome.considered} activities considered, "
        f"{outcome.filled} with heart rate, "
        f"{outcome.without_heart_rate} without"
    )


if __name__ == "__main__":
    main()
