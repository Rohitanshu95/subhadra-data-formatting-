"""
Celery worker tasks for streaming APBS file and batch processing with terminal logging.
"""

from __future__ import annotations

import os
from typing import Optional

from app.models.file import FileStatus
from app.services.batch_manager import BatchManager
from app.services.storage import get_batch_paths
from app.services.summary import generate_batch_summary
from app.services.validation import StreamingValidator
from app.workers.celery_app import celery_app

# Global batch manager instance for the app/worker process
default_batch_manager = BatchManager()


@celery_app.task(name="app.workers.file_worker.process_file_task", bind=True)
def process_file_task(self, batch_id: str, filename: str) -> dict:
    """
    Process a single file within a batch using the streaming validator.
    """
    print(f"\n[WORKER] [TASK] Processing Batch: {batch_id} | File: {filename}")
    batch = default_batch_manager.get_batch(batch_id)
    file_meta = batch.get_file(filename)
    if not file_meta or file_meta.status != FileStatus.READY:
        print(f"[WORKER] [SKIP] File {filename} not in READY state. Skipping.")
        return {"status": "SKIPPED", "batch_id": batch_id, "filename": filename}

    file_meta.mark_processing()
    batch_paths = get_batch_paths(batch_id)
    validator = StreamingValidator()

    base_name = os.path.splitext(file_meta.sanitized_filename)[0]
    output_path = os.path.join(str(batch_paths.output_dir), f"{base_name}_output.txt")
    error_path = os.path.join(str(batch_paths.errors_dir), f"{base_name}_errors.txt")

    try:
        result = validator.process_file(
            input_path=file_meta.input_path,
            output_path=output_path,
            error_path=error_path,
        )
        file_meta.mark_completed(
            record_count=result.total_lines,
            valid_count=result.valid_records,
            invalid_count=result.invalid_records,
            skipped_count=result.skipped_lines,
            output_path=output_path,
            error_path=error_path,
        )
    except Exception as e:
        print(f"[WORKER] [ERROR] Error processing {filename}: {str(e)}")
        file_meta.mark_failed()

    # Check if all files in the batch are completed
    remaining = [
        f for f in batch.files.values()
        if f.status in (FileStatus.READY, FileStatus.PROCESSING, FileStatus.UPLOADING)
    ]
    if not remaining:
        batch.mark_completed()
        print(f"\n[WORKER] [DONE] All files completed for Batch {batch_id}! Status: {batch.status.value}")
        print(f"  * Total Valid Records across batch: {batch.valid_records:,}")
        print(f"  * Total Invalid Errors: {batch.invalid_records:,}")
        summary_text = generate_batch_summary(batch)
        print(f"[WORKER] [SUMMARY] Batch summary report generated at storage/logs/{batch_id}/batch_summary.txt")

    return {
        "status": file_meta.status.value,
        "batch_id": batch_id,
        "filename": filename,
        "valid_records": file_meta.valid_count,
        "invalid_records": file_meta.invalid_count,
    }


@celery_app.task(name="app.workers.file_worker.process_batch_task", bind=True)
def process_batch_task(self, batch_id: str) -> dict:
    """
    Enqueue processing for all processable files in a batch.
    """
    print(f"\n[BATCH WORKER] [DISPATCH] Processing Batch: {batch_id}")
    batch = default_batch_manager.get_batch(batch_id)
    batch.mark_processing()

    ready_files = [
        f for f in batch.files.values()
        if f.status == FileStatus.READY
    ]

    print(f"[BATCH WORKER] [INFO] Found {len(ready_files)} READY files out of {batch.total_files} total files.")

    task_ids = []
    for file_meta in ready_files:
        task = process_file_task.delay(batch_id, file_meta.sanitized_filename)
        task_ids.append(str(task.id))

    if not ready_files:
        batch.mark_completed()
        generate_batch_summary(batch)

    return {
        "batch_id": batch_id,
        "enqueued_files": len(ready_files),
        "task_ids": task_ids,
    }
