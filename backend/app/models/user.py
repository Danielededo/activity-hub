"""The profile of the person this deployment belongs to."""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TimestampMixin


class User(Base, TimestampMixin):
    """Who the dashboard is for.

    No username and no email: with one user and no authentication there is
    nothing to log in as and nothing to send mail to, so the profile is just a
    name. The table stays multi-row so a second person remains possible.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    # Optional: plenty of people go by a single name, and demanding a surname
    # would turn them away for no technical gain.
    last_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    workouts: Mapped[list["Workout"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}" if self.last_name else self.first_name

    def __repr__(self) -> str:
        return f"<User id={self.id} name={self.full_name!r}>"
