"""Turning an uploaded file into a stored workout.

Kept out of the router so the whole path — parse, summarise, deduplicate,
persist — can be tested and reused without going through HTTP.
"""

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models import TrackPoint, User, Workout
from app.services.analyzer import compute_metrics
from app.services.parsers import parse_file


class WorkoutServiceError(Exception):
    """Base class for failures the API turns into 4xx responses."""


class UserNotFoundError(WorkoutServiceError):
    def __init__(self, user_id: int) -> None:
        super().__init__(f"User {user_id} not found")
        self.user_id = user_id


class DuplicateWorkoutError(WorkoutServiceError):
    def __init__(self, existing_id: int) -> None:
        super().__init__(f"This workout is already stored as workout {existing_id}")
        self.existing_id = existing_id


def store_workout(db: Session, user_id: int, filename: str | None, content: bytes) -> Workout:
    """Parse `content`, summarise it and persist it for `user_id`.

    Raises UserNotFoundError, DuplicateWorkoutError, or ParserError when the
    file cannot be read.
    """
    if db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none() is None:
        raise UserNotFoundError(user_id)

    parsed = parse_file(filename, content)

    duplicate = db.execute(
        select(Workout.id).where(
            Workout.user_id == user_id,
            Workout.start_time == parsed.start_time,
            Workout.source == parsed.source,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise DuplicateWorkoutError(duplicate)

    metrics = compute_metrics(parsed)
    workout = Workout(
        user_id=user_id,
        source=parsed.source,
        name=parsed.name,
        sport_type=parsed.sport_type,
        start_time=parsed.start_time,
        utc_offset_minutes=parsed.utc_offset_minutes,
        file_format=parsed.file_format,
        raw_data=parsed.raw_data,
        total_distance=metrics.total_distance,
        total_elevation_gain=metrics.total_elevation_gain,
        total_elevation_loss=metrics.total_elevation_loss,
        total_time=metrics.total_time,
        avg_heart_rate=metrics.avg_heart_rate,
        max_heart_rate=metrics.max_heart_rate,
        avg_cadence=metrics.avg_cadence,
    )
    db.add(workout)
    db.flush()

    if parsed.track_points:
        # One multi-row INSERT rather than thousands of ORM objects.
        db.execute(
            insert(TrackPoint),
            [
                {
                    "workout_id": workout.id,
                    "sequence": point.sequence,
                    "timestamp": point.timestamp,
                    "latitude": point.latitude,
                    "longitude": point.longitude,
                    "elevation": point.elevation,
                    "heart_rate": point.heart_rate,
                    "cadence": point.cadence,
                }
                for point in parsed.track_points
            ],
        )

    db.commit()
    db.refresh(workout)
    return workout


def track_point_count(db: Session, workout_id: int) -> int:
    """How many samples are stored for a workout."""
    return (
        db.execute(
            select(func.count(TrackPoint.id)).where(TrackPoint.workout_id == workout_id)
        ).scalar()
        or 0
    )
