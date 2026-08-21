"""
File metadata model.

Tracks per-file state throughout the processing lifecycle:
upload → dedup check → parsing → validation → completion.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class FileStatus(str, Enum):
    """Lifecycle states for an uploaded file."""

    UPLOADING = "UPLOADING"
    READY = "READY"
    DUPLICATE_FILE = "DUPLICATE_FILE"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


@dataclass
class FileMetadata:
    """
    Metadata for a single uploaded file within a batch.

    Tracks identity (SHA-256), processing stats, and file paths.
    """

    filename: str
    sanitized_filename: str
    sha256: str = ""
    size: int = 0
    status: FileStatus = FileStatus.UPLOADING

    # Processing statistics
    record_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0

    # File paths
    input_path: str = ""
    output_path: str = ""
    error_path: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    # Duplicate info (populated only if status == DUPLICATE_FILE)
    duplicate_of_batch: Optional[str] = None
    duplicate_of_file: Optional[str] = None

    def mark_ready(self, sha256: str, size: int, input_path: str) -> None:
        """Mark file as uploaded and ready for processing."""
        self.sha256 = sha256
        self.size = size
        self.input_path = input_path
        self.status = FileStatus.READY

    def mark_duplicate(self, original_batch: str, original_file: str) -> None:
        """Mark file as a duplicate of an existing file."""
        self.status = FileStatus.DUPLICATE_FILE
        self.duplicate_of_batch = original_batch
        self.duplicate_of_file = original_file

    def mark_processing(self) -> None:
        """Mark file as currently being processed."""
        self.status = FileStatus.PROCESSING

    def mark_completed(
        self,
        record_count: int,
        valid_count: int,
        invalid_count: int,
        skipped_count: int,
        output_path: str,
        error_path: str,
    ) -> None:
        """Mark file processing as complete with statistics."""
        self.record_count = record_count
        self.valid_count = valid_count
        self.invalid_count = invalid_count
        self.skipped_count = skipped_count
        self.output_path = output_path
        self.error_path = error_path
        self.completed_at = datetime.now(timezone.utc)

        if invalid_count > 0:
            self.status = FileStatus.COMPLETED_WITH_ERRORS
        else:
            self.status = FileStatus.COMPLETED

    def mark_failed(self) -> None:
        """Mark file as failed."""
        self.status = FileStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
