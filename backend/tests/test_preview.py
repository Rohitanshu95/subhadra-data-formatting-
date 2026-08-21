"""
Tests for Preview Service.
"""

import io
import pytest
from app.services.batch_manager import BatchManager
from app.services.preview import (
    get_clean_records_preview,
    get_error_records_preview,
    get_summary_content,
)
from app.services.summary import generate_batch_summary
from tests.conftest import build_short_record, build_valid_record


class TestPreviewService:
    def test_get_clean_records_preview(self):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add valid record
        line = build_valid_record(beneficiary_name="TEST USER PREVIEW")
        content = (line + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "prev_valid.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        clean_preview = get_clean_records_preview(batch.batch_id, limit=5)
        assert len(clean_preview) == 1
        assert clean_preview[0]["beneficiary_name"].strip() == "TEST USER PREVIEW"
        assert "_source_file" in clean_preview[0]

    def test_get_error_records_preview(self):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add invalid record (short)
        short_line = build_short_record()
        content = (short_line + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "prev_error.txt", io.BytesIO(content))
        manager.process_batch(batch.batch_id)

        error_preview = get_error_records_preview(batch.batch_id, limit=5)
        assert len(error_preview) >= 1
        assert "error" in error_preview[0]
        assert error_preview[0]["error"] == "INVALID_RECORD_LENGTH"

    def test_get_summary_content(self):
        manager = BatchManager()
        batch = manager.create_batch()
        generate_batch_summary(batch)

        summary_text = get_summary_content(batch.batch_id)
        assert summary_text is not None
        assert batch.batch_id in summary_text
