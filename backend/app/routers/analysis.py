"""Aggregate statistics used by the dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import AnalysisSummary, RecordsSummary, WeeklyAnalysis, ZoneSummary
from app.services.analyzer import user_summary, weekly_summary
from app.services.records import user_records
from app.services.zones import user_zones

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _require_user(user_id: int, db: Session) -> None:
    if db.execute(select(User.id).where(User.id == user_id)).scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


@router.get("/{user_id}", response_model=AnalysisSummary)
def get_summary(user_id: int, db: Session = Depends(get_db)) -> AnalysisSummary:
    """Lifetime totals plus a per-sport breakdown."""
    _require_user(user_id, db)
    return AnalysisSummary.model_validate(user_summary(db, user_id))


@router.get("/{user_id}/weekly", response_model=WeeklyAnalysis)
def get_weekly(
    user_id: int,
    weeks: int = Query(12, ge=1, le=104, description="How many ISO weeks to report"),
    db: Session = Depends(get_db),
) -> WeeklyAnalysis:
    """Per-week totals, oldest first, with empty weeks zero-filled."""
    _require_user(user_id, db)
    return WeeklyAnalysis.model_validate(weekly_summary(db, user_id, weeks=weeks))


@router.get("/{user_id}/records", response_model=RecordsSummary)
def get_records(user_id: int, db: Session = Depends(get_db)) -> RecordsSummary:
    """Per-sport records and standard-distance bests, plus totals by year.

    The distance bests come from windows computed when each file was stored, so
    an activity uploaded before that existed has none until
    scripts/backfill_bests.py has been run.
    """
    _require_user(user_id, db)
    return RecordsSummary.model_validate(user_records(db, user_id))


@router.get("/{user_id}/zones", response_model=ZoneSummary)
def get_zones(
    user_id: int,
    weeks: int = Query(12, ge=1, le=104, description="How many ISO weeks to report"),
    db: Session = Depends(get_db),
) -> ZoneSummary:
    """Time in each heart-rate zone, lifetime and by week, with training load.

    Zones are derived on request rather than stored, because they hang off a
    maximum heart rate that changes: a single harder session moves every
    previous activity's zones. An activity uploaded before the histogram existed
    contributes nothing until scripts/backfill_hr_zones.py has been run.
    """
    _require_user(user_id, db)
    return ZoneSummary.model_validate(user_zones(db, user_id, weeks=weeks))
