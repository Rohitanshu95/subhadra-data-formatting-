"""
Streaming file upload service.

Handles saving uploaded files to the batch input directory while
computing SHA-256 on the fly. Includes path traversal protection
and filename sanitization.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import BinaryIO

from app.core.config import settings
from app.services.hash import StreamingHasher
from app.services.storage import get_batch_paths


@dataclass(frozen=True, slots=True)
class UploadResult:
    """Result of saving an uploaded file."""

    saved_path: str
    sha256: str
    file_size: int
    original_filename: str
    sanitized_filename: str


class UploadError(Exception):
    """Raised when an upload fails validation."""
    pass


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and unsafe characters.

    Rules:
    - Strip directory components (only keep the basename)
    - Remove null bytes
    - Replace unsafe characters with underscores
    - Reject empty filenames after sanitization

    Args:
        filename: The original filename from the upload.

    Returns:
        A safe filename string.

    Raises:
        UploadError: If the filename is empty or entirely unsafe.
    """
    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Take only the basename (strip any directory path)
    filename = os.path.basename(filename)

    # On Windows, also handle backslash paths
    if "\\" in filename:
        filename = filename.split("\\")[-1]

    # Replace unsafe characters (keep alphanumeric, dots, hyphens, underscores)
    filename = re.sub(r'[^\w.\-]', '_', filename)

    # Remove leading dots (hidden files / traversal)
    filename = filename.lstrip(".")

    # Collapse multiple underscores
    filename = re.sub(r'_+', '_', filename)

    if not filename:
        raise UploadError("Filename is empty or contains only unsafe characters")

    return filename


def validate_filename(filename: str) -> None:
    """
    Validate that a filename does not attempt path traversal.

    Raises:
        UploadError: If the filename is unsafe.
    """
    if not filename:
        raise UploadError("Filename cannot be empty")

    # Check for path traversal attempts
    if ".." in filename:
        raise UploadError(f"Path traversal detected in filename: {filename!r}")

    if filename.startswith("/") or filename.startswith("\\"):
        raise UploadError(f"Absolute path detected in filename: {filename!r}")

    if "\x00" in filename:
        raise UploadError(f"Null byte detected in filename: {filename!r}")


class UploadService:
    """
    Handles streaming file uploads with on-the-fly SHA-256 computation.

    Files are streamed directly to disk in chunks — never fully
    buffered in memory. The SHA-256 hash is computed during the
    write pass, not as a separate re-read.
    """

    def __init__(self, chunk_size: int | None = None):
        self._chunk_size = chunk_size or settings.CHUNK_SIZE

    def save_uploaded_file(
        self,
        batch_id: str,
        filename: str,
        file_stream: BinaryIO,
    ) -> UploadResult:
        """
        Stream an uploaded file to the batch input directory.

        Args:
            batch_id: The batch this file belongs to.
            filename: Original filename from the upload.
            file_stream: A binary file-like object to read from.

        Returns:
            UploadResult with saved path, SHA-256, and file size.

        Raises:
            UploadError: If the filename is unsafe.
        """
        # Validate and sanitize
        validate_filename(filename)
        safe_name = sanitize_filename(filename)

        # Resolve the destination path
        batch_paths = get_batch_paths(batch_id)
        dest_path = os.path.join(str(batch_paths.input_dir), safe_name)

        # Ensure the input directory exists
        os.makedirs(str(batch_paths.input_dir), exist_ok=True)

        # Stream write + hash in a single pass
        hasher = StreamingHasher()
        total_size = 0

        with open(dest_path, "wb") as out_file:
            while True:
                chunk = file_stream.read(self._chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                hasher.update(chunk)
                total_size += len(chunk)

        return UploadResult(
            saved_path=dest_path,
            sha256=hasher.hexdigest(),
            file_size=total_size,
            original_filename=filename,
            sanitized_filename=safe_name,
        )
