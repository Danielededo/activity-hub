"""Personal bests: the fastest a standard distance was ever covered.

Two halves. `fastest_windows` looks inside one activity and answers "what is
the quickest this file ever covered five kilometres" — computed once, when the
file is stored, because the samples are already in memory there and reading
them back later would mean scanning every track point of every activity on
every request. `user_records` then reduces those per-activity answers, plus the
workout summaries, into what the dashboard shows.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Workout, WorkoutBest
from app.services.analyzer import MAX_PLAUSIBLE_STEP_M, haversine_distance, local_start_date

#: Distances a personal best is worth keeping, as (label, metres).
#:
#: The half marathon is 21,097.5 m and is stored as 21,098 — half a metre,
#: which is a tenth of a second of running and lets the distance be an integer
#: key. Anything longer than the marathon is somebody's ultra and does not have
#: a standard distance to compare against.
STANDARD_DISTANCES: tuple[tuple[str, int], ...] = (
    ("1 km", 1_000),
    ("5 km", 5_000),
    ("10 km", 10_000),
    ("Half marathon", 21_098),
    ("Marathon", 42_195),
)

DISTANCE_LABELS = {metres: label for label, metres in STANDARD_DISTANCES}


class Sample(Protocol):
    """What both a parsed and a stored track point offer."""

    timestamp: datetime | None
    latitude: float | None
    longitude: float | None


def _progression(points) -> list[tuple[float, float]]:
    """(elapsed seconds, cumulative metres) for the usable part of a track.

    A point without a position or without a time cannot contribute to either
    axis and is dropped. A hop longer than a plausible step is a lost signal,
    so its time counts and its distance does not — the same treatment
    `track_distance` gives it, and the reason a paused watch does not turn into
    a record. Timestamps that go backwards are dropped too: a handful of
    exporters write them out of order, and a negative step would break the
    scan below.
    """
    progression: list[tuple[float, float]] = []
    start: datetime | None = None
    previous: Sample | None = None
    cumulative = 0.0

    for point in points:
        if point.timestamp is None or point.latitude is None or point.longitude is None:
            continue
        if start is None:
            start = point.timestamp
        elapsed = (point.timestamp - start).total_seconds()
        if progression and elapsed < progression[-1][0]:
            continue
        if previous is not None:
            step = haversine_distance(
                previous.latitude, previous.longitude, point.latitude, point.longitude
            )
            if step <= MAX_PLAUSIBLE_STEP_M:
                cumulative += step
        progression.append((elapsed, cumulative))
        previous = point

    return progression


def _time_to_cover(progression: list[tuple[float, float]], target: int) -> float | None:
    """The shortest time any stretch of this track took to cover `target` metres.

    A two-pointer scan: for each end sample, `start` is advanced as far as it
    can go while the window still spans the target, which makes the window the
    tightest one ending there. Because the samples are seconds apart and the
    target is not, the exact start falls between two samples, and the time is
    interpolated across that hop — otherwise a 5 km best would depend on how
    often the watch happened to write a point.
    """
    if len(progression) < 2:
        return None

    best: float | None = None
    start = 0
    for end in range(1, len(progression)):
        end_time, end_distance = progression[end]
        while start + 1 <= end and end_distance - progression[start + 1][1] >= target:
            start += 1
        if end_distance - progression[start][1] < target:
            continue

        start_time, start_distance = progression[start]
        if start + 1 <= end:
            next_time, next_distance = progression[start + 1]
            span = next_distance - start_distance
            if span > 0:
                # Where in this hop the stretch would have to begin to be
                # exactly `target` long.
                fraction = min(1.0, max(0.0, (end_distance - target - start_distance) / span))
                start_time += (next_time - start_time) * fraction

        candidate = end_time - start_time
        if candidate > 0 and (best is None or candidate < best):
            best = candidate

    return best


def fastest_windows(points) -> dict[int, float]:
    """Fastest time this activity covered each standard distance, in seconds.

    Only distances the activity actually reached appear. An activity with no
    timestamps, or with no positions, produces nothing: the time is unknowable
    and a zero would read as a world record.
    """
    progression = _progression(points)
    if not progression or progression[-1][1] <= 0:
        return {}

    covered = progression[-1][1]
    windows: dict[int, float] = {}
    for _, metres in STANDARD_DISTANCES:
        if metres > covered:
            # The ladder is ascending, so nothing longer can fit either.
            break
        duration = _time_to_cover(progression, metres)
        if duration is not None:
            windows[metres] = duration
    return windows


# -- aggregate reporting -------------------------------------------------


@dataclass(slots=True)
class _Holder:
    """The activity that holds a record, and the figure it holds it with."""

    workout_id: int
    workout_name: str
    start_time: datetime
    utc_offset_minutes: int | None
    value: float

    def as_dict(self) -> dict:
        return {
            "workout_id": self.workout_id,
            "workout_name": self.workout_name,
            "start_time": self.start_time,
            "utc_offset_minutes": self.utc_offset_minutes,
            "value": self.value,
        }


def _best_holder(current: _Holder | None, candidate: _Holder) -> _Holder:
    """Keep the larger figure; the earlier activity wins a tie.

    A tie means the record was first set then, and re-riding the same loop to
    the metre should not move the date.
    """
    if current is None or candidate.value > current.value:
        return candidate
    return current


def user_records(db: Session, user_id: int, zone: ZoneInfo | None = None) -> dict:
    """Per-sport records and distance bests, plus totals by calendar year.

    The workout rows are read in one query and reduced in Python. There is one
    row per activity — hundreds, not the hundreds of thousands of track points
    behind them — and the alternative is a separate correlated query for every
    record of every sport.
    """
    zone = zone or settings.timezone

    rows = db.execute(
        select(
            Workout.id,
            Workout.name,
            Workout.sport_type,
            Workout.start_time,
            Workout.utc_offset_minutes,
            Workout.total_distance,
            Workout.total_time,
            Workout.total_elevation_gain,
        ).where(Workout.user_id == user_id)
    ).all()

    counts: dict[str, int] = defaultdict(int)
    longest_distance: dict[str, _Holder] = {}
    longest_duration: dict[str, _Holder] = {}
    biggest_climb: dict[str, _Holder] = {}
    yearly: dict[int, dict] = defaultdict(
        lambda: {
            "workout_count": 0,
            "total_distance": 0.0,
            "total_time": 0.0,
            "total_elevation_gain": 0.0,
        }
    )

    for row in rows:
        counts[row.sport_type] += 1

        def holder(value: float, row=row) -> _Holder:
            return _Holder(
                workout_id=row.id,
                workout_name=row.name,
                start_time=row.start_time,
                utc_offset_minutes=row.utc_offset_minutes,
                value=float(value or 0.0),
            )

        if row.total_distance:
            longest_distance[row.sport_type] = _best_holder(
                longest_distance.get(row.sport_type), holder(row.total_distance)
            )
        if row.total_time:
            longest_duration[row.sport_type] = _best_holder(
                longest_duration.get(row.sport_type), holder(row.total_time)
            )
        if row.total_elevation_gain:
            biggest_climb[row.sport_type] = _best_holder(
                biggest_climb.get(row.sport_type), holder(row.total_elevation_gain)
            )

        year = local_start_date(row.start_time, row.utc_offset_minutes, zone).year
        bucket = yearly[year]
        bucket["workout_count"] += 1
        bucket["total_distance"] += float(row.total_distance or 0.0)
        bucket["total_time"] += float(row.total_time or 0.0)
        bucket["total_elevation_gain"] += float(row.total_elevation_gain or 0.0)

    bests = _distance_bests(db, user_id)

    by_sport = [
        {
            "sport_type": sport,
            "workout_count": counts[sport],
            "longest_distance": _as_dict(longest_distance.get(sport)),
            "longest_duration": _as_dict(longest_duration.get(sport)),
            "biggest_climb": _as_dict(biggest_climb.get(sport)),
            "distance_bests": bests.get(sport, []),
        }
        # Most-recorded sport first, matching the breakdown beside it.
        for sport in sorted(counts, key=lambda name: (-counts[name], name))
    ]

    return {
        "user_id": user_id,
        "by_sport": by_sport,
        "yearly": [{"year": year, **yearly[year]} for year in sorted(yearly, reverse=True)],
    }


def _as_dict(holder: _Holder | None) -> dict | None:
    return holder.as_dict() if holder is not None else None


def _distance_bests(db: Session, user_id: int) -> dict[str, list[dict]]:
    """The quickest stored window per sport and standard distance.

    A window function picks the winner per group in the database, so the query
    returns one row per record rather than every window ever recorded.
    """
    ranked = (
        select(
            Workout.sport_type,
            Workout.id.label("workout_id"),
            Workout.name.label("workout_name"),
            Workout.start_time,
            Workout.utc_offset_minutes,
            WorkoutBest.distance_m,
            WorkoutBest.duration_s,
            func.row_number()
            .over(
                partition_by=(Workout.sport_type, WorkoutBest.distance_m),
                # The earliest activity wins a tie, for the same reason a tied
                # longest ride does not move the date.
                order_by=(WorkoutBest.duration_s.asc(), Workout.start_time.asc()),
            )
            .label("rank"),
        )
        .join(Workout, Workout.id == WorkoutBest.workout_id)
        .where(Workout.user_id == user_id)
        .subquery()
    )

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in db.execute(
        select(ranked).where(ranked.c.rank == 1).order_by(ranked.c.distance_m)
    ).all():
        grouped[row.sport_type].append(
            {
                "label": DISTANCE_LABELS.get(row.distance_m, f"{row.distance_m} m"),
                "distance_m": row.distance_m,
                "duration_s": float(row.duration_s),
                "workout_id": row.workout_id,
                "workout_name": row.workout_name,
                "start_time": row.start_time,
                "utc_offset_minutes": row.utc_offset_minutes,
            }
        )
    return grouped
