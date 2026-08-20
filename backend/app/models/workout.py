"""Workout model: one row per uploaded TCX/GPX file."""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin

# JSONB on PostgreSQL, plain JSON elsewhere so the test suite can run on SQLite.
JsonColumn = JSON().with_variant(JSONB(), "postgresql")


class Workout(Base, TimestampMixin):
    __tablename__ = "workouts"
    __table_args__ = (
        # The hard guarantee: the same bytes cannot be stored twice for a user,
        # whatever the file was named. Near-duplicates — one session exported
        # from two services, so different bytes — are caught in the service
        # layer by a start-time window, which no constraint can express.
        UniqueConstraint("user_id", "file_hash", name="uq_workout_user_file_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    source: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    # The UTC offset the file stated, in minutes. Null when it only wrote 'Z',
    # which is the common case: the instant is known, the local hour is not.
    utc_offset_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Metric units throughout: metres for distance/elevation, seconds for time.
    total_distance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_elevation_gain: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_elevation_loss: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_time: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    avg_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    file_format: Mapped[str] = mapped_column(String(8), nullable=False)
    #: SHA-256 of the uploaded file, hex encoded.
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # File-level metadata only (creator, laps, counts). The samples live in track_points.
    raw_data: Mapped[dict[str, Any]] = mapped_column(JsonColumn, nullable=False, default=dict)

    user: Mapped["User"] = relationship(back_populates="workouts")  # noqa: F821
    track_points: Mapped[list["TrackPoint"]] = relationship(  # noqa: F821
        back_populates="workout",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TrackPoint.sequence",
    )

    def __repr__(self) -> str:
        return f"<Workout id={self.id} sport={self.sport_type!r} start={self.start_time}>"
