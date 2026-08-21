"""A single activity's fastest window over one standard distance.

Computed when the file is stored, because that is the one moment its samples
are already in memory. Recomputing on request would mean scanning every track
point of every activity — hundreds of thousands of rows to answer a question
whose answer never changes.
"""

from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class WorkoutBest(Base):
    __tablename__ = "workout_bests"
    __table_args__ = (
        # One answer per activity per distance: recomputing must overwrite
        # rather than accumulate a second opinion.
        UniqueConstraint("workout_id", "distance_m", name="uq_workout_best_distance"),
        # The records query filters by distance and orders by duration.
        Index("ix_workout_bests_distance_duration", "distance_m", "duration_s"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(
        ForeignKey("workouts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    #: The nominal distance, in whole metres. See STANDARD_DISTANCES.
    distance_m: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Seconds taken to cover it, at the fastest point of the activity.
    duration_s: Mapped[float] = mapped_column(Float, nullable=False)

    workout: Mapped["Workout"] = relationship(back_populates="bests")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<WorkoutBest workout_id={self.workout_id} {self.distance_m}m in {self.duration_s}s>"
        )
