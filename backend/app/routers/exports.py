"""Downloading the library, so the data is never hostage to the database."""

from datetime import date
from tempfile import SpooledTemporaryFile

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.exports import activity_csv, write_archive
from app.services.filters import workout_filters

router = APIRouter(prefix="/export", tags=["export"])

#: Bytes of a zip kept in memory before it spills to disk.
SPOOL_BYTES = 16 * 1024 * 1024

#: Read back to the client in chunks of this size.
STREAM_CHUNK = 64 * 1024


def _require_user(user_id: int, db: Session) -> None:
    if db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def _selection(
    user_id: int,
    db: Session,
    sport_type: str | None,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> list:
    """The same criteria the activity list uses, so an export matches the screen.

    Exporting the whole library when the screen shows one filtered month is the
    kind of surprise that makes people re-download to check.
    """
    _require_user(user_id, db)
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date_from must not be after date_to",
        )
    return workout_filters(
        user_id, sport_type=sport_type, date_from=date_from, date_to=date_to, query=q
    )


@router.get("/activities.csv")
def export_csv(
    user_id: int = Query(..., ge=1),
    sport_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None, max_length=255),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """One row per activity, newest first, for a spreadsheet."""
    filters = _selection(user_id, db, sport_type, date_from, date_to, q)
    return StreamingResponse(
        activity_csv(db, filters),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="activities.csv"'},
    )


@router.get("/activities.zip")
def export_archive(
    user_id: int = Query(..., ge=1),
    sport_type: str | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    q: str | None = Query(None, max_length=255),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Every matching activity as a GPX file, in one zip.

    The mirror image of the archive upload: what this app can swallow, it can
    also hand back. Assembled into a spooled temporary file rather than in
    memory, because a few thousand activities is hundreds of megabytes of XML
    and building all of it to serve one download is how a small server falls
    over.
    """
    filters = _selection(user_id, db, sport_type, date_from, date_to, q)

    # No context manager: the file has to outlive this function so the response
    # generator below can read it, and it is closed in that generator's finally.
    spool = SpooledTemporaryFile(max_size=SPOOL_BYTES)  # noqa: SIM115
    try:
        write_archive(db, filters, spool)
    except Exception:
        spool.close()
        raise
    spool.seek(0)

    def stream():
        try:
            while chunk := spool.read(STREAM_CHUNK):
                yield chunk
        finally:
            # Closing a SpooledTemporaryFile removes the file it spilled into;
            # without this a big export leaks a temporary file per download.
            spool.close()

    return StreamingResponse(
        stream(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="activities.zip"'},
    )
