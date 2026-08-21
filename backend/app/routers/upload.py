"""TCX/GPX upload endpoints, for one file or a whole export archive."""

from dataclasses import asdict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.schemas import ArchiveMemberRead, ArchiveUploadRead, WorkoutRead
from app.services.archives import ArchiveError, looks_like_zip
from app.services.parsers import SUPPORTED_FORMATS, ParserError
from app.services.uploads import EmptyUploadError, UploadTooLargeError, read_upload
from app.services.workouts import (
    DuplicateWorkoutError,
    UserNotFoundError,
    store_archive,
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

    if looks_like_zip(file.filename, content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="That looks like an archive. Send it to /api/upload/archive instead.",
        )

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


@router.post("/archive", response_model=ArchiveUploadRead, status_code=status.HTTP_200_OK)
def upload_archive(
    user_id: int = Query(..., ge=1),
    file: UploadFile = File(..., description="A .zip holding .tcx or .gpx files"),
    db: Session = Depends(get_db),
) -> ArchiveUploadRead:
    """Unpack an export archive and store every activity it holds.

    200 rather than 201: a mixed result is the normal one — some files new, some
    already present, some not activities at all — so the status describes the
    request succeeding and the body describes what happened to each file.

    Sync for the same reason as the single-file route, and more so: this parses
    and writes hundreds of files, none of which belongs on the event loop.
    """
    try:
        content = read_upload(file, settings.max_archive_bytes)
    except EmptyUploadError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except UploadTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        ) from exc

    if not looks_like_zip(file.filename, content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Not an archive. Send a single .tcx or .gpx to /api/upload instead.",
        )

    try:
        outcome = store_archive(db, user_id, content)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except ArchiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    reported = outcome.members[: settings.max_reported_members]
    return ArchiveUploadRead(
        stored=outcome.stored,
        duplicates=outcome.duplicates,
        skipped=outcome.skipped,
        failed=outcome.failed,
        members=[ArchiveMemberRead(**asdict(member)) for member in reported],
        truncated=len(outcome.members) > len(reported),
    )
