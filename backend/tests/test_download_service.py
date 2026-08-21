"""
Tests for Download and ZIP Archiving Service.
"""

import io
import os
import zipfile
import pytest
from app.services.batch_manager import BatchManager
from app.services.download_service import (
    create_batch_zip_archive,
    get_error_file_path,
    get_output_file_path,
    get_summary_file_path,
)
from app.services.summary import generate_batch_summary
from tests.conftest import build_short_record, build_valid_record


class TestDownloadService:
    def test_get_paths_and_create_zip_archive(self):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add 1 valid, 1 error
        valid_content = (build_valid_record() + "\n").encode("utf-8")
        error_content = (build_short_record() + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "file_a.txt", io.BytesIO(valid_content))
        manager.add_file(batch.batch_id, "file_b.txt", io.BytesIO(error_content))
        manager.process_batch(batch.batch_id)
        generate_batch_summary(batch)

        # Check paths
        out_path = get_output_file_path(batch.batch_id, "file_a_output.txt")
        assert out_path is not None and os.path.exists(out_path)

        err_path = get_error_file_path(batch.batch_id, "file_b_errors.txt")
        assert err_path is not None and os.path.exists(err_path)

        sum_path = get_summary_file_path(batch.batch_id)
        assert sum_path is not None and os.path.exists(sum_path)

        # Create zip
        zip_path = create_batch_zip_archive(batch.batch_id)
        assert zip_path is not None and os.path.exists(zip_path)

        # Verify zip archive contents
        with zipfile.ZipFile(zip_path, "r") as z:
            names = z.namelist()
            assert any("file_a_output.txt" in n for n in names)
            assert any("file_b_errors.txt" in n for n in names)
            assert any("batch_summary.txt" in n for n in names)
