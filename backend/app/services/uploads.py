"""Reading uploaded files without trusting their declared size."""

from fastapi import UploadFile

#: Read granularity. Large enough to keep syscalls cheap, small enough that the
#: cap is enforced long before a hostile body is fully in memory.
CHUNK_BYTES = 64 * 1024


class UploadTooLargeError(Exception):
    """Raised when an upload exceeds the configured limit."""

    def __init__(self, limit: int) -> None:
        super().__init__(f"File exceeds the {limit} byte limit")
        self.limit = limit


class EmptyUploadError(Exception):
    """Raised when an upload carries no bytes."""


def read_upload(file: UploadFile, limit: int) -> bytes:
    """Read an upload into memory, refusing to exceed `limit` bytes.

    Starlette has already spooled the body by the time a route runs, so the
    declared size is checked first and the chunked read is the backstop for a
    body whose Content-Length lied. The request-level guard in main.py is what
    stops an oversized body from being spooled at all.
    """
    declared = getattr(file, "size", None)
    if declared is not None and declared > limit:
        raise UploadTooLargeError(limit)

    chunks: list[bytes] = []
    total = 0
    while chunk := file.file.read(CHUNK_BYTES):
        total += len(chunk)
        if total > limit:
            raise UploadTooLargeError(limit)
        chunks.append(chunk)

    if not total:
        raise EmptyUploadError("Uploaded file is empty")
    return b"".join(chunks)
