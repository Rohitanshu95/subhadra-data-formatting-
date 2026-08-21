"""
Batch metadata model.

Tracks the overall batch lifecycle and aggregated statistics
across all files in the batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from app.models.file import FileMetadata, FileStatus


class BatchStatus(str, Enum):
    """Lifecycle states for a batch."""

    CREATED = "CREATED"
    UPLOADING = "UPLOADING"
    READY = "READY"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    AWAITING_VERIFICATION = "AWAITING_VERIFICATION"
    VERIFIED = "VERIFIED"
    IMPORTING = "IMPORTING"
    IMPORTED = "IMPORTED"
    FAILED = "FAILED"


@dataclass
class BatchMetadata:
    """
    Metadata for a processing batch.

    Aggregates file-level statistics and tracks the overall
    batch lifecycle.
    """

    batch_id: str
    status: BatchStatus = BatchStatus.CREATED

    # File registry: sanitized_filename → FileMetadata
    files: dict[str, FileMetadata] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # DB Persistence stats
    db_committed_count: int = 0
    db_duplicates_count: int = 0

    # ── Computed properties ─────────────────────────────────────

    @property
    def db_push_status(self) -> str:
        """Human-readable DB commit status for pipeline tracking."""
        if self.status == BatchStatus.IMPORTED:
            if self.db_committed_count > 0 or self.db_duplicates_count > 0:
                return f"Committed — {self.db_committed_count} new / {self.db_duplicates_count} dup"
            return f"Committed — {self.valid_records} new / 0 dup"
        if self.status == BatchStatus.VERIFIED:
            return "Verified — Ready to Commit"
        if self.status == BatchStatus.FAILED:
            return "Failed"
        return "Not yet committed"

    @property
    def total_files(self) -> int:
        """Total number of files added to this batch."""
        return len(self.files)

    @property
    def total_size(self) -> int:
        """Total size of all files in bytes."""
        return sum(f.size for f in self.files.values())

    @property
    def total_size_gb(self) -> float:
        """Total size in gigabytes."""
        return self.total_size / (1024 ** 3)

    @property
    def duplicate_files(self) -> int:
        """Number of files flagged as duplicates."""
        return sum(
            1 for f in self.files.values()
            if f.status == FileStatus.DUPLICATE_FILE
        )

    @property
    def processable_files(self) -> int:
        """Number of non-duplicate files eligible for processing."""
        return self.total_files - self.duplicate_files

    @property
    def total_records(self) -> int:
        return sum(f.record_count for f in self.files.values())

    @property
    def valid_records(self) -> int:
        return sum(f.valid_count for f in self.files.values())

    @property
    def invalid_records(self) -> int:
        return sum(f.invalid_count for f in self.files.values())

    @property
    def completed_files(self) -> int:
        return sum(
            1 for f in self.files.values()
            if f.status in (FileStatus.COMPLETED, FileStatus.COMPLETED_WITH_ERRORS)
        )

    @property
    def failed_files(self) -> int:
        return sum(
            1 for f in self.files.values()
            if f.status == FileStatus.FAILED
        )

    # ── Lifecycle methods ───────────────────────────────────────

    def add_file(self, file_meta: FileMetadata) -> None:
        """Register a file in this batch."""
        self.files[file_meta.sanitized_filename] = file_meta

    def get_file(self, sanitized_filename: str) -> Optional[FileMetadata]:
        """Look up a file by its sanitized filename."""
        return self.files.get(sanitized_filename)

    def mark_processing(self) -> None:
        """Transition batch to PROCESSING state."""
        self.status = BatchStatus.PROCESSING
        self.started_at = datetime.now(timezone.utc)

    def mark_completed(self) -> None:
        """
        Transition batch to completed state.

        Uses COMPLETED_WITH_ERRORS if any file had errors or failed.
        """
        self.completed_at = datetime.now(timezone.utc)

        if self.failed_files > 0 or self.invalid_records > 0:
            self.status = BatchStatus.COMPLETED_WITH_ERRORS
        else:
            self.status = BatchStatus.COMPLETED

    def mark_failed(self) -> None:
        """Transition batch to FAILED (infrastructure failure)."""
        self.status = BatchStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
