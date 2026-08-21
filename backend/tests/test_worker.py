"""
Tests for Celery Worker Tasks (in eager execution mode).
"""

import io
import pytest
from app.workers.celery_app import celery_app
from app.workers.file_worker import default_batch_manager, process_batch_task, process_file_task
from tests.conftest import build_valid_record


@pytest.fixture(autouse=True)
def enable_eager_celery():
    celery_app.conf.task_always_eager = True
    yield
    celery_app.conf.task_always_eager = False


class TestCeleryWorkerTasks:
    def test_process_batch_task_eager(self):
        batch = default_batch_manager.create_batch()
        # Use a unique reference so it's not caught as duplicate from previous tests
        line = build_valid_record(user_credit_ref="WORKER_TEST_1")
        content = (line + "\n").encode("utf-8")
        file_meta = default_batch_manager.add_file(batch.batch_id, "worker_unique.txt", io.BytesIO(content))
        assert file_meta.status.value == "READY"

        # Run process batch task
        result = process_batch_task.apply(args=[batch.batch_id]).get()
        assert result["batch_id"] == batch.batch_id
        assert result["enqueued_files"] == 1

        updated_batch = default_batch_manager.get_batch(batch.batch_id)
        assert updated_batch.status.value in ("COMPLETED", "COMPLETED_WITH_ERRORS")
        assert updated_batch.valid_records == 1
