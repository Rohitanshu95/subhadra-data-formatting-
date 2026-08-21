"""
Batch ID generator.

Produces human-readable batch identifiers in the format:
    BATCH-YYYYMMDD-NNN-XXXX

Where:
- YYYYMMDD is the current date
- NNN is a zero-padded sequential counter (resets daily)
- XXXX is a 4-character hex suffix for uniqueness
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone


class BatchIdGenerator:
    """
    Thread-safe batch ID generator.

    Uses an in-memory counter per date. In Phase 4 this will be
    backed by the database for persistence across restarts.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}  # date_str → counter

    def generate(self) -> str:
        """
        Generate a new unique batch ID.

        Format: BATCH-YYYYMMDD-NNN-XXXX

        Returns:
            A unique batch identifier string.
        """
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y%m%d")

        with self._lock:
            count = self._counters.get(date_str, 0) + 1
            self._counters[date_str] = count

        # 4-char hex suffix from UUID for extra uniqueness
        hex_suffix = uuid.uuid4().hex[:4].upper()

        return f"BATCH-{date_str}-{count:03d}-{hex_suffix}"


# Module-level singleton
_generator = BatchIdGenerator()


def generate_batch_id() -> str:
    """Generate a new batch ID using the module-level generator."""
    return _generator.generate()
