"""
Tests for Batch Summary Report Generator.
"""

import io
import os
import pytest
from app.services.batch_manager import BatchManager
from app.services.summary import generate_batch_summary
from tests.conftest import build_valid_record


class TestBatchSummary:
    def test_generate_batch_summary(self):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add and process a valid file
        line = build_valid_record()
        content = (line + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "file_01.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        summary_text = generate_batch_summary(batch)
        assert "APBS BATCH PROCESSING SUMMARY" in summary_text
        assert batch.batch_id in summary_text
        assert "Total Files Uploaded: 1" in summary_text
        assert "Valid Clean Records : 1" in summary_text
        assert "file_01.txt" in summary_text
