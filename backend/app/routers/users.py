"""User management. No auth: the deployment is single-user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    user = User(username=payload.username, email=payload.email)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with that username or email already exists",
        ) from exc
    db.refresh(user)
    return user


@router.get("/me", response_model=UserRead)
def get_current_user(db: Session = Depends(get_db)) -> User:
    """The single user this deployment serves.

    Declared before /{user_id} so "me" is not read as an id. There is no
    authentication: this deployment has one user, whoever is self-hosting it,
    and the dashboard asks here rather than being configured with an id. The
    row is created by scripts.ensure_user in the entrypoint.
    """
    user = db.execute(select(User).order_by(User.id).limit(1)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user exists yet. Run `python -m scripts.ensure_user`.",
        )
    return user


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: int, db: Session = Depends(get_db)) -> User:
    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
