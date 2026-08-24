"""
File-level deduplication engine.

Detects duplicate files by comparing SHA-256 content hashes.
Same content under a different filename is still recognized as
a duplicate and skipped without reprocessing.

In Phase 2 this uses an in-memory registry. Phase 4 replaces
this with a database-backed lookup.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class DuplicateInfo:
    """Information about the original file that this is a duplicate of."""

    original_batch_id: str
    original_filename: str


class FileDeduplicationService:
    """
    In-memory file deduplication registry.

    Thread-safe. Maintains a mapping of SHA-256 → (batch_id, filename)
    for all files that have been registered.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # sha256 → DuplicateInfo
        self._registry: dict[str, DuplicateInfo] = {}

    def check_duplicate(self, sha256: str) -> Optional[DuplicateInfo]:
        """
        Check if a file with the given SHA-256 hash already exists.

        Args:
            sha256: The SHA-256 hex digest of the file content.

        Returns:
            DuplicateInfo if the file is a duplicate, None if it's new.
        """
        with self._lock:
            return self._registry.get(sha256)

    def register_file(
        self,
        sha256: str,
        batch_id: str,
        filename: str,
    ) -> None:
        """
        Register a new file's hash in the deduplication registry.

        Only call this after confirming the file is NOT a duplicate.

        Args:
            sha256: The SHA-256 hex digest of the file content.
            batch_id: The batch this file belongs to.
            filename: The sanitized filename.
        """
        with self._lock:
            if sha256 not in self._registry:
                self._registry[sha256] = DuplicateInfo(
                    original_batch_id=batch_id,
                    original_filename=filename,
                )

    def is_registered(self, sha256: str) -> bool:
        """Check if a hash is already in the registry."""
        with self._lock:
            return sha256 in self._registry

    @property
    def registered_count(self) -> int:
        """Number of unique files registered."""
        with self._lock:
            return len(self._registry)

    def unregister_batch(self, batch_id: str) -> None:
        """Remove all files registered under a specific batch ID."""
        with self._lock:
            to_remove = [
                sha for sha, info in self._registry.items()
                if info.original_batch_id == batch_id
            ]
            for sha in to_remove:
                del self._registry[sha]

    def unregister_file(self, sha256: str) -> None:
        """Remove a specific file hash from the registry."""
        with self._lock:
            self._registry.pop(sha256, None)

    def clear(self) -> None:
        """Clear the registry (mainly for testing)."""
        with self._lock:
            self._registry.clear()
