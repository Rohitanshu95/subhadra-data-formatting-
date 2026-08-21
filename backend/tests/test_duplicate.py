"""
Tests for file-level deduplication engine.
"""

import pytest
from app.services.duplicate import DuplicateInfo, FileDeduplicationService


class TestFileDeduplicationService:
    def test_register_and_detect_duplicate(self):
        dedup = FileDeduplicationService()
        hash_val = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        
        # Initially not registered
        assert dedup.check_duplicate(hash_val) is None
        assert not dedup.is_registered(hash_val)

        # Register file
        dedup.register_file(
            sha256=hash_val,
            batch_id="BATCH-001",
            filename="first_file.txt",
        )

        assert dedup.is_registered(hash_val)
        assert dedup.registered_count == 1

        # Check duplicate
        dup_info = dedup.check_duplicate(hash_val)
        assert dup_info is not None
        assert dup_info.original_batch_id == "BATCH-001"
        assert dup_info.original_filename == "first_file.txt"

    def test_different_hashes_not_duplicates(self):
        dedup = FileDeduplicationService()
        hash1 = "1111111111111111111111111111111111111111111111111111111111111111"
        hash2 = "2222222222222222222222222222222222222222222222222222222222222222"

        dedup.register_file(hash1, "BATCH-001", "file1.txt")
        assert dedup.check_duplicate(hash2) is None
