"""
Tests for file upload service, filename sanitization, and path traversal protection.
"""

import io
import os
import tempfile
import pytest
from app.services.upload import (
    UploadError,
    UploadService,
    sanitize_filename,
    validate_filename,
)


class TestFilenameValidationAndSanitization:
    def test_valid_filename(self):
        validate_filename("apbs_batch_01.txt")
        assert sanitize_filename("apbs_batch_01.txt") == "apbs_batch_01.txt"

    def test_path_traversal_rejected(self):
        with pytest.raises(UploadError, match="Path traversal"):
            validate_filename("../../etc/passwd")

    def test_absolute_path_unix_rejected(self):
        with pytest.raises(UploadError, match="Absolute path"):
            validate_filename("/var/data/test.txt")

    def test_absolute_path_windows_rejected(self):
        with pytest.raises(UploadError, match="Absolute path"):
            validate_filename("\\windows\\system32\\test.txt")

    def test_null_byte_rejected(self):
        with pytest.raises(UploadError, match="Null byte"):
            validate_filename("test\x00.txt")

    def test_empty_filename_rejected(self):
        with pytest.raises(UploadError):
            validate_filename("")

    def test_sanitize_removes_path_and_special_chars(self):
        assert sanitize_filename("test<invalid>:file?.txt") == "test_invalid_file_.txt"
        assert sanitize_filename("..hidden.txt") == "hidden.txt"


class TestUploadService:
    def test_save_uploaded_file(self):
        upload_service = UploadService(chunk_size=128)
        content = b"Sample APBS upload payload content 1234567890" * 10
        stream = io.BytesIO(content)
        
        batch_id = "BATCH-TEST-001"
        result = upload_service.save_uploaded_file(
            batch_id=batch_id,
            filename="data.txt",
            file_stream=stream,
        )

        assert os.path.exists(result.saved_path)
        assert result.file_size == len(content)
        assert result.original_filename == "data.txt"
        assert result.sanitized_filename == "data.txt"
        assert len(result.sha256) == 64

        # Clean up
        os.unlink(result.saved_path)
