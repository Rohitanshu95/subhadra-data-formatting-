"""
In-Memory Cache Service for APBS Dashboard & Records.

Provides fast RAM-based caching to avoid continuous database queries:
- User Default: Returns data directly from RAM cache (0ms latency, zero DB queries).
- User Refresh: Queries the database, refreshes the RAM cache, and returns fresh data.
- Auto-invalidation: Clears or updates cache when batches are uploaded, processed, imported, or deleted.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


class AppCache:
    """Thread-safe in-memory cache with timestamp tracking."""

    def __init__(self) -> None:
        self._overview_stats: Optional[Dict[str, Any]] = None
        self._overview_stats_time: float = 0.0

        self._batches_list: Optional[List[Any]] = None
        self._batches_list_time: float = 0.0

        self._records_cache: Dict[str, Any] = {
            "system_all": None,
            "batches": {},
        }
        self._records_cache_time: Dict[str, float] = {}

    # ── Overview Stats ──────────────────────────────────────────

    def get_overview_stats(self) -> Optional[Dict[str, Any]]:
        """Return cached overview statistics if present."""
        return self._overview_stats

    def set_overview_stats(self, stats: Dict[str, Any]) -> None:
        """Store overview statistics in RAM cache."""
        self._overview_stats = stats
        self._overview_stats_time = time.time()

    def invalidate_overview_stats(self) -> None:
        """Invalidate overview stats cache."""
        self._overview_stats = None
        self._overview_stats_time = 0.0

    # ── Batches List ────────────────────────────────────────────

    def get_batches(self) -> Optional[List[Any]]:
        """Return cached batch metadata list if present."""
        return self._batches_list

    def set_batches(self, batches: List[Any]) -> None:
        """Store batch metadata list in RAM cache."""
        self._batches_list = batches
        self._batches_list_time = time.time()

    def invalidate_batches(self) -> None:
        """Invalidate batches list cache."""
        self._batches_list = None
        self._batches_list_time = 0.0

    # ── Records Cache ───────────────────────────────────────────

    def get_records(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Return cached records for a batch or system_all."""
        if key == "system_all":
            return self._records_cache.get("system_all")
        return self._records_cache.get("batches", {}).get(key)

    def set_records(self, key: str, records: List[Dict[str, Any]]) -> None:
        """Cache records for a batch or system_all in RAM."""
        if key == "system_all":
            self._records_cache["system_all"] = records
        else:
            if "batches" not in self._records_cache:
                self._records_cache["batches"] = {}
            self._records_cache["batches"][key] = records
        self._records_cache_time[key] = time.time()

    def invalidate_records(self, key: Optional[str] = None) -> None:
        """Invalidate records cache for a specific batch or globally."""
        if key is None:
            self._records_cache = {
                "system_all": None,
                "batches": {},
            }
            self._records_cache_time.clear()
        elif key == "system_all":
            self._records_cache["system_all"] = None
            self._records_cache_time.pop("system_all", None)
        else:
            if "batches" in self._records_cache and key in self._records_cache["batches"]:
                del self._records_cache["batches"][key]
            self._records_cache_time.pop(key, None)

    # ── Full Invalidation ───────────────────────────────────────

    def invalidate_all(self) -> None:
        """Flush the entire in-memory cache."""
        self.invalidate_overview_stats()
        self.invalidate_batches()
        self.invalidate_records()
        print("[CACHE] Flushed all in-memory caches.")


# Global cache singleton
app_cache = AppCache()
