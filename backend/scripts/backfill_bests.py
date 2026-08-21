"""Fill in personal bests for activities stored before they were computed.

New uploads compute their own windows, so this is only needed once, after
upgrading past migration 0005 — and for the odd case of wanting to recompute
after a change to how the windows are found.

    python -m scripts.backfill_bests            # only activities with none
    python -m scripts.backfill_bests --recompute  # every activity, replacing

Track points are read one activity at a time. A library of a few thousand
activities is a few million samples, and loading them all to hold them in
memory at once is the one thing this must not do.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from sqlalchemy import delete, insert, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import TrackPoint, Workout, WorkoutBest
from app.services.records import fastest_windows


@dataclass(slots=True)
class Outcome:
    considered: int = 0
    #: Activities that gained at least one record.
    filled: int = 0
    #: Activities with no timestamps, no positions, or too short for 1 km.
    without_bests: int = 0
    windows: int = 0


def backfill(db: Session, *, recompute: bool = False, batch: int = 200) -> Outcome:
    """Compute and store windows for stored activities. Safe to re-run."""
    query = select(Workout.id).order_by(Workout.id)
    if not recompute:
        # Skip anything already answered, so an interrupted run resumes.
        #
        # "No rows" cannot distinguish "not computed yet" from "computed, and
        # too short to have any", so activities under a kilometre are rescanned
        # on every run. They are cheap and this is a manual one-off; the
        # alternative is a second table recording what has been looked at.
        query = query.where(
            ~select(WorkoutBest.id).where(WorkoutBest.workout_id == Workout.id).exists()
        )

    outcome = Outcome()
    workout_ids = list(db.execute(query).scalars())

    for index, workout_id in enumerate(workout_ids, start=1):
        points = list(
            db.execute(
                select(TrackPoint.timestamp, TrackPoint.latitude, TrackPoint.longitude)
                .where(TrackPoint.workout_id == workout_id)
                .order_by(TrackPoint.sequence)
            ).all()
        )
        outcome.considered += 1

        windows = fastest_windows(points)
        if recompute:
            db.execute(delete(WorkoutBest).where(WorkoutBest.workout_id == workout_id))
        if windows:
            db.execute(
                insert(WorkoutBest),
                [
                    {"workout_id": workout_id, "distance_m": metres, "duration_s": duration}
                    for metres, duration in windows.items()
                ],
            )
            outcome.filled += 1
            outcome.windows += len(windows)
        else:
            outcome.without_bests += 1

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
        help="Redo every activity, replacing any windows already stored",
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
        f"{outcome.filled} with records ({outcome.windows} windows), "
        f"{outcome.without_bests} with none"
    )


if __name__ == "__main__":
    main()
