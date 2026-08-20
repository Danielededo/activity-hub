"""Aggregate statistics used by the dashboard."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import AnalysisSummary, WeeklyAnalysis
from app.services.analyzer import user_summary, weekly_summary

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
