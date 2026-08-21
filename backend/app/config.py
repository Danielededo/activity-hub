"""Application settings, loaded from the environment or a local .env file."""

import json
from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

#: Slack allowed on top of max_upload_bytes for multipart framing and headers.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # No default on purpose. A missing DATABASE_URL is a deployment mistake, and
    # a fallback DSN would let the app start and quietly talk to the wrong
    # database — or to a guessable one — instead of failing loudly at boot.
    database_url: str = Field(min_length=1)

    api_prefix: str = "/api"
    # NoDecode because the environment source would otherwise try to JSON-decode
    # this before any validator runs, which fails on both "" and the
    # comma-separated form below. With it, the raw string reaches _split_origins.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024

    #: Wall-clock timezone used to bucket activities whose file states no UTC
    #: offset. An IANA name, e.g. "Europe/Rome".
    display_timezone: str = "UTC"

    # Only used by scripts.ensure_user, for headless setups that never open the
    # dashboard. The normal path is the first-run screen asking who you are.
    default_first_name: str = "Athlete"
    default_last_name: str | None = None

    #: Hard ceiling on track points returned in one response.
    max_track_points: int = 20_000

    #: Two activities from the same user starting within this window and sharing
    #: a sport are treated as the same session exported twice.
    duplicate_window_seconds: int = 300

    debug: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string so .env stays readable.

        An empty value means no origin needs allowing, which is the normal case:
        the dashboard proxies /api on its own origin.
        """
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("display_timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        """Reject an unknown zone at boot rather than at query time."""
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown IANA timezone: {value!r}") from exc
        return value

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.display_timezone)

    @property
    def max_request_bytes(self) -> int:
        """Cap for a whole request body: the file plus multipart framing."""
        return self.max_upload_bytes + MULTIPART_OVERHEAD_BYTES


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
