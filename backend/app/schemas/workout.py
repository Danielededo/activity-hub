"""Workout, upload and analysis response models."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class WorkoutBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source: str
    name: str
    sport_type: str
    start_time: datetime
    utc_offset_minutes: int | None
    total_distance: float
    total_elevation_gain: float
    total_elevation_loss: float
    total_time: float
    avg_heart_rate: int | None
    max_heart_rate: int | None
    avg_cadence: int | None
    file_format: str
    created_at: datetime
    updated_at: datetime


class WorkoutSummary(WorkoutBase):
    """List representation: everything except the raw file metadata."""


class WorkoutRead(WorkoutBase):
    """Detail representation."""

    raw_data: dict[str, Any]
    track_point_count: int = 0


class WorkoutList(BaseModel):
    items: list[WorkoutSummary]
    total: int
    limit: int
    offset: int


class TrackPointRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    timestamp: datetime | None
    latitude: float | None
    longitude: float | None
    elevation: float | None
    heart_rate: int | None
    cadence: int | None


class TrackPointSeries(BaseModel):
    """A workout's samples, downsampled to something a chart can draw."""

    workout_id: int
    #: Samples stored for this workout.
    total: int
    returned: int
    #: 1 means every sample; n means every nth, plus the final one.
    stride: int
    items: list[TrackPointRead]


class SportBreakdown(BaseModel):
    sport_type: str
    workout_count: int
    total_distance: float
    total_time: float


class AnalysisSummary(BaseModel):
    user_id: int
    workout_count: int
    total_distance: float
    total_time: float
    total_elevation_gain: float
    avg_distance: float
    avg_duration: float
    avg_heart_rate: float | None
    max_heart_rate: int | None
    longest_workout_id: int | None
    first_workout_at: datetime | None
    last_workout_at: datetime | None
    by_sport: list[SportBreakdown]


class WeeklyBucket(BaseModel):
    week_start: date
    iso_year: int
    iso_week: int
    workout_count: int
    total_distance: float
    total_time: float
    total_elevation_gain: float


class WeeklyAnalysis(BaseModel):
    user_id: int
    weeks: int
    buckets: list[WeeklyBucket]
