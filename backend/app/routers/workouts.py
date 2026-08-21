"""Listing, detail and deletion of stored workouts."""

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import TrackPoint, Workout
from app.schemas import TrackPointSeries, WorkoutList, WorkoutRead
from app.services.workouts import track_point_count

router = APIRouter(prefix="/workouts", tags=["workouts"])


def get_owned_workout_or_404(workout_id: int, user_id: int, db: Session) -> Workout:
    """Fetch a workout, scoped to its owner.

    Deployments are single-user today, but the schema and every other endpoint
    are multi-user: looking a workout up by id alone would let any caller read
    or delete anyone's activity. A workout owned by someone else answers 404
    rather than 403, so the response does not confirm that the id exists.
    """
    workout = db.execute(
        select(Workout).where(Workout.id == workout_id, Workout.user_id == user_id)
    ).scalar_one_or_none()
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
def get_workout(
    workout_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> WorkoutRead:
    workout = get_owned_workout_or_404(workout_id, user_id, db)
    return WorkoutRead.model_validate(workout).model_copy(
        update={"track_point_count": track_point_count(db, workout_id)}
    )


@router.get("/{workout_id}/track-points", response_model=TrackPointSeries)
def get_track_points(
    workout_id: int,
    user_id: int = Query(..., ge=1),
    max_points: int = Query(
        2_000,
        ge=2,
        le=settings.max_track_points,
        description="Downsample to at most this many samples",
    ),
    db: Session = Depends(get_db),
) -> TrackPointSeries:
    """The workout's samples, for a route map or a heart-rate trace.

    Downsampled rather than paginated: a caller drawing a line wants the shape
    of the whole activity, not page three of it. An hour of riding is some
    3,600 samples and no chart has that many pixels, so the server strides the
    series and says which stride it used.
    """
    get_owned_workout_or_404(workout_id, user_id, db)

    total, last_sequence = db.execute(
        select(func.count(TrackPoint.id), func.max(TrackPoint.sequence)).where(
            TrackPoint.workout_id == workout_id
        )
    ).one()
    if not total:
        return TrackPointSeries(
            workout_id=workout_id, total=0, returned=0, stride=1, items=[]
        )

    stride = max(1, ceil(total / max_points))
    query = select(TrackPoint).where(TrackPoint.workout_id == workout_id)
    if stride > 1:
        # Keep the final sample as well, so a downsampled track does not stop
        # short of where the activity actually ended.
        query = query.where(
            or_(TrackPoint.sequence % stride == 0, TrackPoint.sequence == last_sequence)
        )

    items = db.execute(query.order_by(TrackPoint.sequence)).scalars().all()
    return TrackPointSeries(
        workout_id=workout_id, total=total, returned=len(items), stride=stride, items=items
    )


@router.delete("/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workout(
    workout_id: int,
    user_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> Response:
    """Deletes the workout and, by cascade, its track points."""
    workout = get_owned_workout_or_404(workout_id, user_id, db)
    db.delete(workout)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
