"""
Tests for BatchManager lifecycle and orchestration.
"""

import io
import os
import pytest
from app.models.batch import BatchStatus
from app.models.file import FileStatus
from app.services.batch_manager import BatchLimitError, BatchManager, BatchNotFoundError
from tests.conftest import build_valid_record


class TestBatchManager:
    def test_create_batch_and_add_files(self):
        manager = BatchManager()
        batch = manager.create_batch()
        assert batch.batch_id.startswith("BATCH-")
        assert batch.status == BatchStatus.CREATED
        assert batch.total_files == 0

        # Upload valid file
        line = build_valid_record()
        stream1 = io.BytesIO((line + "\n").encode("utf-8"))
        file_meta1 = manager.add_file(batch.batch_id, "file1.txt", stream1)

        assert file_meta1.status == FileStatus.READY
        assert batch.total_files == 1
        assert batch.processable_files == 1
        assert batch.duplicate_files == 0

    def test_duplicate_file_detection_in_batch(self):
        manager = BatchManager()
        batch = manager.create_batch()

        content = (build_valid_record() + "\n").encode("utf-8")
        
        # Upload first file
        file_meta1 = manager.add_file(batch.batch_id, "original.txt", io.BytesIO(content))
        assert file_meta1.status == FileStatus.READY

        # Upload same content with different filename
        file_meta2 = manager.add_file(batch.batch_id, "renamed_copy.txt", io.BytesIO(content))
        assert file_meta2.status == FileStatus.DUPLICATE_FILE
        assert file_meta2.duplicate_of_file == "original.txt"
        assert batch.duplicate_files == 1
        assert batch.processable_files == 1

    def test_process_batch_executes_streaming_validation(self):
        manager = BatchManager()
        batch = manager.create_batch()

        # Add 2 files: 1 valid, 1 duplicate
        content = (build_valid_record() + "\n").encode("utf-8")
        manager.add_file(batch.batch_id, "file1.txt", io.BytesIO(content))
        manager.add_file(batch.batch_id, "file1_copy.txt", io.BytesIO(content))

        # Process batch
        processed_batch = manager.process_batch(batch.batch_id)
        assert processed_batch.status == BatchStatus.COMPLETED
        assert processed_batch.valid_records == 1
        assert processed_batch.completed_files == 1
        assert processed_batch.duplicate_files == 1

    def test_non_existent_batch_raises_error(self):
        manager = BatchManager()
        with pytest.raises(BatchNotFoundError):
            manager.get_batch("BATCH-NON-EXISTENT")
