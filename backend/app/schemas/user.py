"""User request/response models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserCreate(BaseModel):
    """What the dashboard's first-run screen collects."""

    first_name: str = Field(min_length=1, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)

    @field_validator("first_name", "last_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        """Trim, and treat a blank surname as absent rather than empty."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("first_name")
    @classmethod
    def _require_first_name(cls, value: str | None) -> str:
        if not value:
            raise ValueError("first_name cannot be blank")
        return value


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str | None
    #: Convenience for the UI: the surname is often absent.
    full_name: str
    created_at: datetime
    updated_at: datetime
