"""Per-sample track point. A one hour activity is roughly 3,600 rows."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# SQLite has no autoincrementing BIGINT primary key, so fall back to INTEGER there.
PrimaryKeyType = BigInteger().with_variant(Integer(), "sqlite")


class TrackPoint(Base):
    __tablename__ = "track_points"
    __table_args__ = (Index("ix_track_points_workout_sequence", "workout_id", "sequence"),)

    id: Mapped[int] = mapped_column(PrimaryKeyType, primary_key=True, autoincrement=True)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), nullable=False
    )
    # Preserves file order even for GPX tracks that carry no timestamps.
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    workout: Mapped["Workout"] = relationship(back_populates="track_points")  # noqa: F821

    def __repr__(self) -> str:
        return f"<TrackPoint workout_id={self.workout_id} seq={self.sequence}>"
