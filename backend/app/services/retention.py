"""
Data Retention and Cleanup Service.

Removes raw input files from storage/input/ for batches older than
the configured retention threshold, while keeping clean outputs and logs.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import List
from app.core.config import settings


def cleanup_expired_raw_inputs(retention_days: int = 30) -> List[str]:
    """
    Remove raw input directories in storage/input/ older than retention_days.

    Returns:
        List of cleaned batch directory paths.
    """
    base_input = Path(settings.STORAGE_BASE_DIR) / "input"
    if not base_input.exists():
        return []

    cutoff_time = time.time() - (retention_days * 86400)
    cleaned = []

    for entry in os.scandir(base_input):
        if entry.is_dir():
            mtime = entry.stat().st_mtime
            if mtime < cutoff_time:
                shutil.rmtree(entry.path, ignore_errors=True)
                cleaned.append(entry.path)

    return cleaned
