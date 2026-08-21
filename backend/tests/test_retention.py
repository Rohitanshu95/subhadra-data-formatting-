"""
Tests for Data Retention and Cleanup Service.
"""

import os
import time
import pytest
from app.core.config import settings
from app.services.retention import cleanup_expired_raw_inputs


class TestRetentionService:
    def test_cleanup_expired_raw_inputs(self, tmp_path, monkeypatch):
        # Override storage base dir to tmp_path
        monkeypatch.setattr(settings, "STORAGE_BASE_DIR", tmp_path)
        input_base = tmp_path / "input"
        input_base.mkdir(parents=True)

        old_batch_dir = input_base / "BATCH-OLD-001"
        old_batch_dir.mkdir()
        (old_batch_dir / "old_file.txt").write_text("old data")

        # Set mtime to 40 days ago
        old_time = time.time() - (40 * 86400)
        os.utime(str(old_batch_dir), (old_time, old_time))

        new_batch_dir = input_base / "BATCH-NEW-001"
        new_batch_dir.mkdir()
        (new_batch_dir / "new_file.txt").write_text("new data")

        # Run retention cleaner for >30 days
        cleaned = cleanup_expired_raw_inputs(retention_days=30)
        assert len(cleaned) == 1
        assert "BATCH-OLD-001" in cleaned[0]
        assert not old_batch_dir.exists()
        assert new_batch_dir.exists()
