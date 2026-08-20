"""Listing, detail and deletion of stored workouts."""

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Workout
from app.schemas import WorkoutList, WorkoutRead
from app.services.workouts import track_point_count

router = APIRouter(prefix="/workouts", tags=["workouts"])


def get_workout_or_404(workout_id: int, db: Session) -> Workout:
    workout = db.execute(select(Workout).where(Workout.id == workout_id)).scalar_one_or_none()
    if workout is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workout not found")
    return workout


@router.get("", response_model=WorkoutList)
def list_workouts(
    user_id: int = Query(..., ge=1),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sport_type: str | None = Query(None, description="Filter to a single sport"),
    db: Session = Depends(get_db),
) -> WorkoutList:
    """Most recent workouts first."""
    filters = [Workout.user_id == user_id]
    if sport_type:
        filters.append(Workout.sport_type == sport_type)

    total = db.execute(select(func.count(Workout.id)).where(*filters)).scalar() or 0
    items = (
        db.execute(
            select(Workout)
            .where(*filters)
            .order_by(Workout.start_time.desc(), Workout.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return WorkoutList(items=items, total=total, limit=limit, offset=offset)


@router.get("/{workout_id}", response_model=WorkoutRead)
def get_workout(workout_id: int, db: Session = Depends(get_db)) -> WorkoutRead:
    workout = get_workout_or_404(workout_id, db)
    return WorkoutRead.model_validate(workout).model_copy(
        update={"track_point_count": track_point_count(db, workout_id)}
    )


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(workout_id: int, db: Session = Depends(get_db)) -> Response:
    """Deletes the workout and, by cascade, its track points."""
    workout = get_workout_or_404(workout_id, db)
    db.delete(workout)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
