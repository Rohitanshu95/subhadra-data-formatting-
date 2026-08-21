"""
Streaming SHA-256 hashing service and record-level hash computation.

Computes SHA-256 incrementally — data is fed in chunks, so full
files are never loaded into memory. Used during upload to compute
the content hash in a single pass (no secondary disk re-read).
Also provides compute_record_hash for 177-char line identity.
"""

from __future__ import annotations

import hashlib


class StreamingHasher:
    """
    Computes SHA-256 incrementally from streaming data.
    """

    def __init__(self) -> None:
        self._hasher = hashlib.sha256()
        self._bytes_processed: int = 0

    def update(self, data: bytes) -> None:
        """Feed a chunk of data into the hash computation."""
        self._hasher.update(data)
        self._bytes_processed += len(data)

    def hexdigest(self) -> str:
        """Return the final SHA-256 hash as a lowercase hex string."""
        return self._hasher.hexdigest()

    @property
    def bytes_processed(self) -> int:
        """Total bytes fed into the hasher so far."""
        return self._bytes_processed

    def copy(self) -> "StreamingHasher":
        """Return an independent copy of this hasher's current state."""
        new = StreamingHasher.__new__(StreamingHasher)
        new._hasher = self._hasher.copy()
        new._bytes_processed = self._bytes_processed
        return new


def compute_file_hash(file_path: str, chunk_size: int = 65536) -> str:
    """
    Compute SHA-256 of an existing file by reading it in chunks.
    """
    hasher = StreamingHasher()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_record_hash(line: str) -> str:
    """
    Compute SHA-256 hash of a normalized 177-character APBS record.

    Normalizes the record by stripping trailing newline/carriage return
    and encoding to UTF-8.

    Args:
        line: The raw 177-character record line.

    Returns:
        64-character SHA-256 hex string.
    """
    normalized = line.rstrip("\r\n").encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()
