"""Application settings, loaded from the environment or a local .env file."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Slack allowed on top of max_upload_bytes for multipart framing and headers.
MULTIPART_OVERHEAD_BYTES = 1024 * 1024


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # No default on purpose. A missing DATABASE_URL is a deployment mistake, and
    # a fallback DSN would let the app start and quietly talk to the wrong
    # database — or to a guessable one — instead of failing loudly at boot.
    database_url: str = Field(min_length=1)

    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 20 * 1024 * 1024

    #: Wall-clock timezone used to bucket activities whose file states no UTC
    #: offset. An IANA name, e.g. "Europe/Rome".
    display_timezone: str = "UTC"

    #: Two activities from the same user starting within this window and sharing
    #: a sport are treated as the same session exported twice.
    duplicate_window_seconds: int = 300

    debug: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        """Accept a comma-separated string so .env stays readable."""
        if isinstance(value, str) and not value.strip().startswith("["):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def max_request_bytes(self) -> int:
        """Cap for a whole request body: the file plus multipart framing."""
        return self.max_upload_bytes + MULTIPART_OVERHEAD_BYTES


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
