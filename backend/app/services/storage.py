"""
Storage directory scaffolding service.

Creates the per-batch directory structure under STORAGE_BASE_DIR:
    storage/input/{batch_id}/
    storage/output/{batch_id}/
    storage/errors/{batch_id}/
    storage/logs/{batch_id}/
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from app.core.config import settings


class BatchPaths(NamedTuple):
    """All paths associated with a batch."""

    input_dir: Path
    output_dir: Path
    errors_dir: Path
    logs_dir: Path


def ensure_storage_dirs(batch_id: str) -> BatchPaths:
    """
    Create the full directory tree for a given batch.

    Args:
        batch_id: Unique batch identifier (e.g. 'BATCH-20260820-001-8F3A').

    Returns:
        BatchPaths with all four directory paths.
    """
    base = Path(settings.STORAGE_BASE_DIR)
    paths = BatchPaths(
        input_dir=base / "input" / batch_id,
        output_dir=base / "output" / batch_id,
        errors_dir=base / "errors" / batch_id,
        logs_dir=base / "logs" / batch_id,
    )

    for p in paths:
        os.makedirs(p, exist_ok=True)

    return paths


def get_batch_paths(batch_id: str) -> BatchPaths:
    """
    Return the expected paths for a batch WITHOUT creating them.

    Useful for read operations where the directories should already exist.
    """
    base = Path(settings.STORAGE_BASE_DIR)
    return BatchPaths(
        input_dir=base / "input" / batch_id,
        output_dir=base / "output" / batch_id,
        errors_dir=base / "errors" / batch_id,
        logs_dir=base / "logs" / batch_id,
    )
