"""TCX/GPX upload endpoint: parse, summarise, persist."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import TrackPoint, User, Workout
from app.schemas import WorkoutRead
from app.services.analyzer import compute_metrics
from app.services.parsers import SUPPORTED_FORMATS, ParserError, parse_file

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", response_model=WorkoutRead, status_code=status.HTTP_201_CREATED)
async def upload_workout(
    user_id: int = Query(..., ge=1),
    file: UploadFile = File(..., description=f"One of: {', '.join(SUPPORTED_FORMATS)}"),
    db: Session = Depends(get_db),
) -> WorkoutRead:
    if db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.max_upload_bytes} byte limit",
        )

    try:
        parsed = parse_file(file.filename, content)
    except ParserError as exc:
        # Unsupported extension and malformed content are both the client's problem.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    duplicate = db.execute(
        select(Workout.id).where(
            Workout.user_id == user_id,
            Workout.start_time == parsed.start_time,
            Workout.source == parsed.source,
        )
    ).scalar_one_or_none()
    if duplicate is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This workout is already stored as workout {duplicate}",
        )

    metrics = compute_metrics(parsed)
    workout = Workout(
        user_id=user_id,
        source=parsed.source,
        name=parsed.name,
        sport_type=parsed.sport_type,
        start_time=parsed.start_time,
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

    try:
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
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This workout is already stored"
        ) from exc

    db.refresh(workout)
    return WorkoutRead.model_validate(workout).model_copy(
        update={"track_point_count": len(parsed.track_points)}
    )
