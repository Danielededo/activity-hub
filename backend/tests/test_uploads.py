"""Configuration guards and upload size limits."""

import inspect
import io

import pytest
from fastapi import UploadFile
from pydantic import ValidationError

from app.config import MULTIPART_OVERHEAD_BYTES, Settings, settings
from app.routers.upload import upload_workout
from app.services.uploads import (
    EmptyUploadError,
    UploadTooLargeError,
    read_upload,
)


def make_upload(content: bytes, *, declared_size: int | None = None) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        size=len(content) if declared_size is None else declared_size,
        filename="ride.gpx",
    )


# -- configuration -------------------------------------------------------


def test_settings_require_a_database_url(monkeypatch):
    """A missing DATABASE_URL must fail at boot, not fall back to a default."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_accept_an_explicit_database_url():
    assert Settings(_env_file=None, database_url="sqlite://").database_url == "sqlite://"


def test_max_request_bytes_allows_for_multipart_framing():
    assert settings.max_request_bytes == settings.max_upload_bytes + MULTIPART_OVERHEAD_BYTES


def test_cors_origins_accept_a_comma_separated_string():
    parsed = Settings(_env_file=None, database_url="sqlite://", cors_origins="http://a,http://b")

    assert parsed.cors_origins == ["http://a", "http://b"]


# -- the upload reader ---------------------------------------------------


def test_read_upload_returns_the_content():
    assert read_upload(make_upload(b"<gpx/>"), limit=1024) == b"<gpx/>"


def test_read_upload_rejects_content_over_the_limit():
    with pytest.raises(UploadTooLargeError):
        read_upload(make_upload(b"x" * 200), limit=100)


def test_read_upload_rejects_an_understated_size():
    """The chunked read is the backstop when the declared size lies."""
    upload = make_upload(b"x" * 500, declared_size=1)

    with pytest.raises(UploadTooLargeError):
        read_upload(upload, limit=100)


def test_read_upload_rejects_an_overstated_size_without_reading():
    with pytest.raises(UploadTooLargeError):
        read_upload(make_upload(b"x", declared_size=10_000), limit=100)


def test_read_upload_rejects_an_empty_file():
    with pytest.raises(EmptyUploadError):
        read_upload(make_upload(b""), limit=100)


def test_read_upload_accepts_content_exactly_at_the_limit():
    assert read_upload(make_upload(b"x" * 100), limit=100) == b"x" * 100


# -- the request-level guard --------------------------------------------


def test_oversized_body_is_rejected_before_it_is_parsed(client, monkeypatch):
    """The guard must fire on Content-Length, before multipart spools the body."""
    monkeypatch.setattr(settings, "max_upload_bytes", 1024)
    oversized = b"x" * (settings.max_request_bytes + 1)

    response = client.post(
        "/api/upload?user_id=1", files={"file": ("big.gpx", oversized, "application/xml")}
    )

    assert response.status_code == 413
    assert "Request body exceeds" in response.json()["detail"]


def test_a_normal_body_passes_the_guard(client, user, sample_gpx):
    response = client.post(
        f"/api/upload?user_id={user['id']}",
        files={"file": ("run.gpx", sample_gpx, "application/xml")},
    )

    assert response.status_code == 201


# -- event loop safety ---------------------------------------------------


def test_the_upload_route_is_synchronous():
    """An async route would run parsing and DB writes on the event loop.

    Both block, so a large upload would stall every other request. FastAPI
    hands sync routes to a threadpool instead — keep this one sync.
    """
    assert not inspect.iscoroutinefunction(upload_workout)
