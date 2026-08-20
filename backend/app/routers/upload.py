"""TCX/GPX upload endpoint."""

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import WorkoutRead
from app.services.parsers import SUPPORTED_FORMATS, ParserError
from app.services.uploads import EmptyUploadError, UploadTooLargeError, read_upload
from app.services.workouts import (
    DuplicateWorkoutError,
    UserNotFoundError,
    store_workout,
    track_point_count,
)

router = APIRouter(prefix="/upload", tags=["upload"])


# Deliberately sync: parsing and the SQLAlchemy writes both block, and an
# `async def` route runs on the event loop, so a large upload would stall every
# other request. A sync route runs in the threadpool instead.
@router.post("", response_model=WorkoutRead, status_code=status.HTTP_201_CREATED)
def upload_workout(
    user_id: int = Query(..., ge=1),
    file: UploadFile = File(..., description=f"One of: {', '.join(SUPPORTED_FORMATS)}"),
    db: Session = Depends(get_db),
) -> WorkoutRead:
    try:
        content = read_upload(file, settings.max_upload_bytes)
    except EmptyUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc

    try:
        workout = store_workout(db, user_id, file.filename, content)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except DuplicateWorkoutError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ParserError as exc:
        # Unsupported extension and malformed content are both the client's problem.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This workout is already stored"
        ) from exc

    return WorkoutRead.model_validate(workout).model_copy(
        update={"track_point_count": track_point_count(db, workout.id)}
    )
