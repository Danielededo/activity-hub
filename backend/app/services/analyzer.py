"""Derives workout summaries from track points, and user stats from workouts."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Workout
from app.services.parsers.base_parser import ParsedTrackPoint, ParsedWorkout

EARTH_RADIUS_M = 6_371_008.8

#: Elevation changes below this are GPS noise, not climbing (metres).
ELEVATION_NOISE_THRESHOLD_M = 1.0

#: Two consecutive points further apart than this are a signal gap, not movement.
MAX_PLAUSIBLE_STEP_M = 1_000.0


def haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float, radius: float = EARTH_RADIUS_M
) -> float:
    """Great-circle distance between two coordinates, in metres."""
    phi1, phi2 = radians(lat1), radians(lat2)
    delta_phi = phi2 - phi1
    delta_lambda = radians(lon2 - lon1)
    inner = sin(delta_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(delta_lambda / 2) ** 2
    return 2 * radius * asin(sqrt(min(1.0, inner)))


@dataclass(slots=True)
class WorkoutMetrics:
    """The summary columns stored on a Workout row."""

    total_distance: float
    total_elevation_gain: float
    total_elevation_loss: float
    total_time: float
    avg_heart_rate: int | None
    max_heart_rate: int | None
    avg_cadence: int | None


def track_distance(points: list[ParsedTrackPoint]) -> float:
    """Sum of great-circle hops between consecutive positioned points."""
    total = 0.0
    previous: ParsedTrackPoint | None = None
    for point in points:
        if point.latitude is None or point.longitude is None:
            continue
        if previous is not None:
            step = haversine_distance(
                previous.latitude, previous.longitude, point.latitude, point.longitude
            )
            # Skip teleports: a dropped signal should not inflate the total.
            if step <= MAX_PLAUSIBLE_STEP_M:
                total += step
        previous = point
    return total


def elevation_change(points: list[ParsedTrackPoint]) -> tuple[float, float]:
    """Cumulative (gain, loss) in metres, ignoring sub-threshold jitter."""
    gain = loss = 0.0
    reference: float | None = None
    for point in points:
        if point.elevation is None:
            continue
        if reference is None:
            reference = point.elevation
            continue
        delta = point.elevation - reference
        if abs(delta) < ELEVATION_NOISE_THRESHOLD_M:
            continue
        if delta > 0:
            gain += delta
        else:
            loss += -delta
        reference = point.elevation
    return gain, loss


def elapsed_seconds(points: list[ParsedTrackPoint]) -> float:
    """Wall-clock span of the track, in seconds."""
    stamps = [point.timestamp for point in points if point.timestamp is not None]
    if len(stamps) < 2:
        return 0.0
    return max((max(stamps) - min(stamps)).total_seconds(), 0.0)


def _average(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


def compute_metrics(parsed: ParsedWorkout) -> WorkoutMetrics:
    """Fill in whatever the file did not state, from the track points."""
    points = parsed.track_points
    heart_rates = [p.heart_rate for p in points if p.heart_rate]
    cadences = [p.cadence for p in points if p.cadence]
    gain, loss = elevation_change(points)

    return WorkoutMetrics(
        # Trust the file's own totals when present: Garmin measures distance
        # with a wheel or footpod, which beats integrating GPS positions.
        total_distance=parsed.total_distance or track_distance(points),
        total_elevation_gain=gain,
        total_elevation_loss=loss,
        total_time=parsed.total_time or elapsed_seconds(points),
        avg_heart_rate=parsed.avg_heart_rate or _average(heart_rates),
        max_heart_rate=parsed.max_heart_rate or (max(heart_rates) if heart_rates else None),
        avg_cadence=parsed.avg_cadence or _average(cadences),
    )


# -- aggregate reporting ------------------------------------------------


def user_summary(db: Session, user_id: int) -> dict:
    """Lifetime totals, averages and a per-sport breakdown for one user."""
    totals = db.execute(
        select(
            func.count(Workout.id),
            func.coalesce(func.sum(Workout.total_distance), 0.0),
            func.coalesce(func.sum(Workout.total_time), 0.0),
            func.coalesce(func.sum(Workout.total_elevation_gain), 0.0),
            func.avg(Workout.avg_heart_rate),
            func.max(Workout.max_heart_rate),
            func.min(Workout.start_time),
            func.max(Workout.start_time),
        ).where(Workout.user_id == user_id)
    ).one()

    (count, distance, time, elevation, avg_hr, max_hr, first_at, last_at) = totals
    longest = db.execute(
        select(Workout.id)
        .where(Workout.user_id == user_id)
        .order_by(Workout.total_distance.desc(), Workout.id)
        .limit(1)
    ).scalar_one_or_none()

    by_sport = [
        {
            "sport_type": row.sport_type,
            "workout_count": row.workout_count,
            "total_distance": float(row.total_distance or 0.0),
            "total_time": float(row.total_time or 0.0),
        }
        for row in db.execute(
            select(
                Workout.sport_type,
                func.count(Workout.id).label("workout_count"),
                func.coalesce(func.sum(Workout.total_distance), 0.0).label("total_distance"),
                func.coalesce(func.sum(Workout.total_time), 0.0).label("total_time"),
            )
            .where(Workout.user_id == user_id)
            .group_by(Workout.sport_type)
            .order_by(func.count(Workout.id).desc(), Workout.sport_type)
        ).all()
    ]

    return {
        "user_id": user_id,
        "workout_count": count,
        "total_distance": float(distance),
        "total_time": float(time),
        "total_elevation_gain": float(elevation),
        "avg_distance": float(distance) / count if count else 0.0,
        "avg_duration": float(time) / count if count else 0.0,
        "avg_heart_rate": float(avg_hr) if avg_hr is not None else None,
        "max_heart_rate": int(max_hr) if max_hr is not None else None,
        "longest_workout_id": longest,
        "first_workout_at": first_at,
        "last_workout_at": last_at,
        "by_sport": by_sport,
    }


def weekly_summary(db: Session, user_id: int, weeks: int = 12) -> dict:
    """Per-ISO-week totals for the last `weeks` weeks, most recent last.

    Weeks with no activity are returned as zeroed buckets so the chart keeps
    an even x axis.
    """
    today = datetime.now(UTC).date()
    current_week_start = today - timedelta(days=today.weekday())
    first_week_start = current_week_start - timedelta(weeks=weeks - 1)

    rows = db.execute(
        select(
            Workout.start_time,
            Workout.total_distance,
            Workout.total_time,
            Workout.total_elevation_gain,
        ).where(Workout.user_id == user_id)
    ).all()

    grouped: dict[date, dict] = defaultdict(
        lambda: {
            "workout_count": 0,
            "total_distance": 0.0,
            "total_time": 0.0,
            "total_elevation_gain": 0.0,
        }
    )
    for start_time, distance, time, elevation in rows:
        started = start_time.date()
        week_start = started - timedelta(days=started.weekday())
        if week_start < first_week_start or week_start > current_week_start:
            continue
        bucket = grouped[week_start]
        bucket["workout_count"] += 1
        bucket["total_distance"] += float(distance or 0.0)
        bucket["total_time"] += float(time or 0.0)
        bucket["total_elevation_gain"] += float(elevation or 0.0)

    buckets = []
    for offset in range(weeks):
        week_start = first_week_start + timedelta(weeks=offset)
        iso_year, iso_week, _ = week_start.isocalendar()
        buckets.append(
            {
                "week_start": week_start,
                "iso_year": iso_year,
                "iso_week": iso_week,
                **grouped[week_start],
            }
        )

    return {"user_id": user_id, "weeks": weeks, "buckets": buckets}
