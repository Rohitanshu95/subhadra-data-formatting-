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
    print(f"\n[WORKER] [TASK] 📥 Processing Batch: {batch_id} | File: {filename}")
    batch = default_batch_manager.get_batch(batch_id)
    file_meta = batch.get_file(filename)
    if not file_meta or file_meta.status != FileStatus.READY:
        print(f"[WORKER] [SKIP] ⚠️  File {filename} not in READY state (current: {file_meta.status.value if file_meta else 'NOT FOUND'}). Skipping.")
        return {"status": "SKIPPED", "batch_id": batch_id, "filename": filename}

    print(f"[WORKER] [INFO] File Details: {file_meta.size_bytes:,} bytes | Status: {file_meta.status.value}")
    
    file_meta.mark_processing()
    batch_paths = get_batch_paths(batch_id)
    validator = StreamingValidator()

    base_name = os.path.splitext(file_meta.sanitized_filename)[0]
    output_path = os.path.join(str(batch_paths.output_dir), f"{base_name}_output.txt")
    error_path = os.path.join(str(batch_paths.errors_dir), f"{base_name}_errors.txt")

    try:
        print(f"[WORKER] [START] Beginning file processing...")
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
        
        print("\n" + "-"*85)
        print(f"[WORKER] [FILE COMPLETE] {filename}")
        print(f"  ✓ Total Lines Read      : {result.total_lines:,}")
        print(f"  ✓ Valid Records         : {result.valid_records:,}")
        print(f"  ✓ Validation Warnings   : {result.invalid_records:,}")
        print(f"  ✓ Skipped Headers/Etc   : {result.skipped_lines:,}")
        print(f"  ✓ Output File           : {output_path}")
        print(f"  ✓ Processing Mode       : LENIENT (accept all data as-is)")
        print("-"*85 + "\n")
        
    except Exception as e:
        print(f"\n[WORKER] [ERROR] ❌ Error processing {filename}: {str(e)}")
        print(f"[WORKER] [ERROR] Stack trace: {type(e).__name__}")
        file_meta.mark_failed()

    # Check if all files in the batch are completed
    remaining = [
        f for f in batch.files.values()
        if f.status in (FileStatus.READY, FileStatus.PROCESSING, FileStatus.UPLOADING)
    ]
    if not remaining:
        batch.mark_completed()
        print("\n" + "="*90)
        print(f"[WORKER] [COMPLETE] Batch {batch_id} Processing Finished!")
        print("="*90)
        print(f"  ✓ Batch Status          : {batch.status.value}")
        print(f"  ✓ Total Files Processed : {batch.total_files}")
        print(f"  ✓ Total Valid Records   : {batch.valid_records:,}")
        print(f"  ✓ Total Invalid Records : {batch.invalid_records:,}")
        print(f"  ✓ Total Skipped Lines   : {sum(f.skipped_count or 0 for f in batch.files.values()):,}")
        
        success_rate = (batch.valid_records / (batch.valid_records + batch.invalid_records) * 100) if (batch.valid_records + batch.invalid_records) > 0 else 0
        print(f"  ✓ Success Rate          : {success_rate:.2f}%")
        
        print("\nFile Details:")
        for fname, fmeta in batch.files.items():
            print(f"    📄 {fname}")
            print(f"       - Status: {fmeta.status.value}")
            print(f"       - Valid Records: {fmeta.valid_count:,} | Invalid: {fmeta.invalid_count:,} | Skipped: {fmeta.skipped_count:,}")
            if fmeta.output_path:
                print(f"       - Output: {fmeta.output_path}")
        
        summary_text = generate_batch_summary(batch)
        print(f"\n[WORKER] [SUMMARY] Batch summary report generated at storage/logs/{batch_id}/batch_summary.txt")
        print("="*90 + "\n")

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
    print("\n" + "="*90)
    print(f"[BATCH WORKER] 🚀 Starting Batch Processing: {batch_id}")
    print("="*90)
    
    batch = default_batch_manager.get_batch(batch_id)
    batch.mark_processing()

    ready_files = [
        f for f in batch.files.values()
        if f.status == FileStatus.READY
    ]

    print(f"[BATCH WORKER] 📋 Files to Process: {len(ready_files)} out of {batch.total_files} total")
    
    for i, f in enumerate(ready_files, 1):
        print(f"  {i}. {f.sanitized_filename} ({f.size_bytes:,} bytes)")

    task_ids = []
    for file_meta in ready_files:
        task = process_file_task.delay(batch_id, file_meta.sanitized_filename)
        task_ids.append(str(task.id))
        print(f"[BATCH WORKER] ⏳ Queued: {file_meta.sanitized_filename} (Task ID: {task.id})")

    if not ready_files:
        batch.mark_completed()
        print(f"[BATCH WORKER] ⚠️  No files ready for processing. Marking batch as completed.")
        generate_batch_summary(batch)
    
    print("="*90 + "\n")

    return {
        "batch_id": batch_id,
        "enqueued_files": len(ready_files),
        "task_ids": task_ids,
    }
