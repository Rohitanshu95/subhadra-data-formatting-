"""
REST API routes for Batch Management, Streaming Processing, Verification, and SQL Import.
Includes real-time terminal output and error logging.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, init_db
from app.models.batch import BatchStatus
from app.models.file import FileStatus
from app.schemas.batch import BatchMetadataSchema, FileMetadataSchema
from app.services.batch_manager import BatchLimitError, BatchNotFoundError
from app.services.download_service import (
    create_batch_zip_archive,
    get_error_file_path,
    get_output_file_path,
    get_summary_file_path,
)
from app.services.import_service import ImportResult, ImportService
from app.services.preview import (
    get_clean_records_preview,
    get_error_records_preview,
    get_summary_content,
)
from app.workers.file_worker import default_batch_manager, process_batch_task

# Ensure database tables exist
init_db()

router = APIRouter(prefix="/api/batches", tags=["batches"])


class ProgressResponse(BaseModel):
    batch_id: str
    status: str
    total_files: int
    completed_files: int
    duplicate_files: int
    progress_percentage: float
    total_records: int
    valid_records: int
    invalid_records: int


class ImportResponseSchema(BaseModel):
    batch_id: str
    status: str
    total_processed: int
    total_imported: int
    total_duplicates: int


def run_batch_synchronously(batch_id: str):
    """Background fallback to process batch when Celery/Redis is not running."""
    try:
        print(f"\n[BACKGROUND ENGINE] [RUN] Processing batch {batch_id} in FastAPI process...")
        default_batch_manager.process_batch(batch_id)
        from app.services.summary import generate_batch_summary
        batch = default_batch_manager.get_batch(batch_id)
        generate_batch_summary(batch)
        print(f"[BACKGROUND ENGINE] [DONE] Completed batch {batch_id} processing!\n")
    except Exception as e:
        print(f"[BACKGROUND ENGINE] [ERROR] Error processing batch {batch_id}: {e}")


@router.post("", response_model=BatchMetadataSchema, status_code=status.HTTP_201_CREATED)
async def create_batch():
    """Create a new batch."""
    batch = default_batch_manager.create_batch()
    print(f"\n[API] [CREATE] Created new batch: {batch.batch_id}")
    return batch


@router.get("", response_model=List[BatchMetadataSchema])
async def list_batches():
    """List all batches."""
    return default_batch_manager.list_batches()


@router.get("/overview/stats")
async def get_overview_stats(db: Session = Depends(get_db)):
    """
    Get system-wide overview statistics structured around the 5 DB pipeline stages.
    Guarantees 100% mathematical reconciliation with the registered batches table.
    """
    from app.models.db_models import DBTransaction, DBDuplicateLog
    batches = default_batch_manager.list_batches()
    
    total_records_parsed = sum(b.total_records for b in batches)
    awaiting_verification = sum(
        b.valid_records for b in batches
        if b.status in (
            BatchStatus.COMPLETED,
            BatchStatus.COMPLETED_WITH_ERRORS,
            BatchStatus.AWAITING_VERIFICATION,
            BatchStatus.VERIFIED,
        )
    )
    
    # Live counts directly from SQL database
    committed_to_db = db.query(DBTransaction).count()
    db_dups_count = db.query(DBDuplicateLog).count()
    file_dups_count = sum(b.duplicate_files for b in batches)
    duplicates_skipped = db_dups_count + file_dups_count
    failed_records = sum(b.invalid_records for b in batches)
    
    return {
        "total_batches": len(batches),
        "total_records_parsed": total_records_parsed,
        "awaiting_verification": awaiting_verification,
        "committed_to_db": committed_to_db,
        "duplicates_skipped": duplicates_skipped,
        "failed_records": failed_records,
        # Backward-compatible fields
        "total_records": total_records_parsed,
        "valid_records": sum(b.valid_records for b in batches),
        "invalid_records": failed_records,
        "duplicate_files": file_dups_count,
        "db_transactions_count": committed_to_db,
        "db_duplicates_count": db_dups_count,
    }


@router.get("/{batch_id}/records")
async def get_batch_parsed_records(
    batch_id: str,
    page: int = 1,
    page_size: int = 50,
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    refresh: bool = False,
    db: Session = Depends(get_db),
):
    """
    Get server-side paginated and filtered parsed records for a batch.
    Includes all 17 schema columns in canonical order + Status column, with PII masked.
    """
    try:
        from app.services.record_service import get_paginated_parsed_records
        if batch_id.lower() == "all":
            return get_paginated_parsed_records(
                batch_id="ALL",
                batch_status=None,
                db=db,
                page=page,
                page_size=page_size,
                success_flag=success_flag,
                reason_code=reason_code,
                status_filter=status,
                search=search,
                force_refresh=refresh,
            )

        batch = default_batch_manager.get_batch(batch_id)
        return get_paginated_parsed_records(
            batch_id=batch_id,
            batch_status=batch.status.value if hasattr(batch.status, "value") else str(batch.status),
            db=db,
            page=page,
            page_size=page_size,
            success_flag=success_flag,
            reason_code=reason_code,
            status_filter=status,
            search=search,
            force_refresh=refresh,
        )
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}", response_model=BatchMetadataSchema)
async def get_batch(batch_id: str):
    """Get metadata and statistics for a specific batch."""
    try:
        return default_batch_manager.get_batch(batch_id)
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/files", response_model=List[FileMetadataSchema])
async def get_batch_files(batch_id: str):
    """List all files in a specific batch."""
    try:
        batch = default_batch_manager.get_batch(batch_id)
        return list(batch.files.values())
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.post("/{batch_id}/upload", response_model=List[FileMetadataSchema])
async def upload_files(batch_id: str, files: List[UploadFile] = File(...)):
    """
    Stream upload one or more files to a batch with on-the-fly SHA-256 hashing.
    """
    try:
        print(f"\n[API] [UPLOAD] Received {len(files)} uploaded file(s) for Batch: {batch_id}")
        uploaded_results = []
        for file in files:
            file_meta = default_batch_manager.add_file(
                batch_id=batch_id,
                filename=file.filename,
                file_stream=file.file,
            )
            print(f"  * Uploaded: {file_meta.sanitized_filename} ({file_meta.size:,} bytes) | SHA-256: {file_meta.sha256[:16]}... | Status: {file_meta.status.value}")
            uploaded_results.append(file_meta)
        return uploaded_results
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")
    except BatchLimitError as e:
        print(f"[API] [ERROR] Batch limit exceeded: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] [ERROR] Upload error: {e}")
        raise HTTPException(status_code=400, detail=f"Upload error: {str(e)}")


@router.post("/{batch_id}/process", response_model=BatchMetadataSchema)
async def process_batch(batch_id: str, background_tasks: BackgroundTasks):
    """
    Trigger background processing for all READY files in the batch.
    """
    try:
        batch = default_batch_manager.get_batch(batch_id)
        ready_files = [f for f in batch.files.values() if f.status == FileStatus.READY]
        if not ready_files:
            if batch.total_files > 0:
                # All files in the batch are duplicate files or already processed
                batch.mark_completed()
                default_batch_manager._sync_batch_to_db(batch)
                try:
                    from app.services.summary import generate_batch_summary
                    generate_batch_summary(batch)
                except Exception as sum_err:
                    print(f"[API] [WARN] Summary generation notice: {sum_err}")
                print(f"[API] [PROCESS] Batch {batch_id} consists entirely of duplicate files ({batch.duplicate_files} dup). Marked completed.")
                return batch
            raise HTTPException(status_code=400, detail="No files uploaded in batch to process")

        print(f"\n[API] [PROCESS] Triggering batch processing for {batch_id} ({len(ready_files)} ready files)...")
        
        # Immediate non-blocking dispatch: Try Celery or dispatch to FastAPI background task
        dispatched = False
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            try:
                process_batch_task.delay(batch_id)
                dispatched = True
            except Exception as e:
                print(f"[API] [EAGER ERROR] {e}")

        if not dispatched:
            try:
                import redis
                r = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=0.3, socket_timeout=0.3)
                r.ping()
                process_batch_task.delay(batch_id)
                dispatched = True
            except Exception as queue_err:
                print(f"[API] [INFO] Redis/Celery broker not running ({queue_err}). Executing in local background worker task.")
                background_tasks.add_task(run_batch_synchronously, batch_id)

        return batch
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/progress", response_model=ProgressResponse)
async def get_batch_progress(batch_id: str):
    """Get real-time progress for a batch."""
    try:
        batch = default_batch_manager.get_batch(batch_id)
        processable = batch.processable_files
        pct = 0.0
        if processable > 0:
            pct = (batch.completed_files / processable) * 100.0
        elif batch.total_files > 0:
            pct = 100.0

        return ProgressResponse(
            batch_id=batch.batch_id,
            status=batch.status.value,
            total_files=batch.total_files,
            completed_files=batch.completed_files,
            duplicate_files=batch.duplicate_files,
            progress_percentage=round(pct, 2),
            total_records=batch.total_records,
            valid_records=batch.valid_records,
            invalid_records=batch.invalid_records,
        )
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


# ── Phase 5: Verification Checkpoint, Previews, Downloads, SQL Import ───

@router.post("/{batch_id}/verify", response_model=BatchMetadataSchema)
async def verify_batch(batch_id: str):
    """
    Human verification checkpoint: marks the batch as VERIFIED.
    """
    try:
        batch = default_batch_manager.get_batch(batch_id)
        if batch.status not in (
            BatchStatus.COMPLETED,
            BatchStatus.COMPLETED_WITH_ERRORS,
            BatchStatus.AWAITING_VERIFICATION,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot verify batch in state '{batch.status.value}'. Must be COMPLETED.",
            )
        batch.status = BatchStatus.VERIFIED
        default_batch_manager._sync_batch_to_db(batch)
        print(f"\n[API] [VERIFY] Batch {batch_id} marked as VERIFIED by operator.")
        return batch
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/preview/clean")
async def preview_clean_records(batch_id: str, limit: int = 20):
    """Get sample clean output records for review."""
    try:
        default_batch_manager.get_batch(batch_id)
        return get_clean_records_preview(batch_id, limit=limit)
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/preview/errors")
async def preview_error_records(batch_id: str, limit: int = 20):
    """Get sample error log records for review."""
    try:
        default_batch_manager.get_batch(batch_id)
        return get_error_records_preview(batch_id, limit=limit)
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/summary", response_class=PlainTextResponse)
async def get_summary_text(batch_id: str):
    """Retrieve full batch summary report as plain text."""
    try:
        default_batch_manager.get_batch(batch_id)
        content = get_summary_content(batch_id)
        if content is None:
            raise HTTPException(status_code=404, detail="Batch summary report not found")
        return content
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.get("/{batch_id}/download/output/{filename}")
async def download_output_file(batch_id: str, filename: str):
    """Download clean delimited TXT output file."""
    path = get_output_file_path(batch_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail=f"Output file '{filename}' not found")
    print(f"[API] [DOWNLOAD] Output file: {filename} for Batch: {batch_id}")
    return FileResponse(path, filename=filename, media_type="text/plain")


@router.get("/{batch_id}/download/errors/{filename}")
async def download_error_file(batch_id: str, filename: str):
    """Download structured error log TXT file."""
    path = get_error_file_path(batch_id, filename)
    if not path:
        raise HTTPException(status_code=404, detail=f"Error file '{filename}' not found")
    print(f"[API] [DOWNLOAD] Error log: {filename} for Batch: {batch_id}")
    return FileResponse(path, filename=filename, media_type="text/plain")


@router.get("/{batch_id}/download/summary")
async def download_summary_file(batch_id: str):
    """Download batch summary report."""
    path = get_summary_file_path(batch_id)
    if not path:
        raise HTTPException(status_code=404, detail="Batch summary not found")
    print(f"[API] [DOWNLOAD] Summary report for Batch: {batch_id}")
    return FileResponse(path, filename="batch_summary.txt", media_type="text/plain")


@router.get("/{batch_id}/download/all")
async def download_all_artifacts_zip(batch_id: str):
    """Download all output, error, and summary files bundled in a single ZIP."""
    zip_path = create_batch_zip_archive(batch_id)
    if not zip_path or not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="No downloadable files available for this batch")
    print(f"[API] [DOWNLOAD] ZIP package for Batch: {batch_id}")
    return FileResponse(zip_path, filename=f"{batch_id}_results.zip", media_type="application/zip")


@router.get("/{batch_id}/download/records/csv")
async def download_records_as_csv(
    batch_id: str,
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Download all parsed records (committed/shown in dashboard) as CSV format.
    Includes all 17 APBS schema columns plus Status column.
    
    Query Parameters:
        success_flag: Filter by success flag (e.g., "1", "0")
        reason_code: Filter by reason code
        status: Filter by status (COMMITTED, INVALID, etc.)
        search: Full-text search across Aadhaar, name, account numbers
    """
    try:
        from app.services.record_service import get_paginated_parsed_records
        from app.services.download_service import export_records_as_csv
        
        # Get all records (using large page size to get everything)
        records_response = get_paginated_parsed_records(
            batch_id=batch_id if batch_id.lower() != "all" else "ALL",
            batch_status=None,
            db=db,
            page=1,
            page_size=1000000,  # Large number to get all records
            success_flag=success_flag,
            reason_code=reason_code,
            status_filter=status,
            search=search,
            force_refresh=False,
        )
        
        columns = records_response.get("columns", [])
        records = records_response.get("records", [])
        
        csv_content = export_records_as_csv(records, columns)
        
        print(f"[API] [DOWNLOAD] CSV export: {batch_id} ({len(records)} records)")
        
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{batch_id}_records.csv"'}
        )
    except Exception as e:
        print(f"[API] [ERROR] Failed to export CSV: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{batch_id}/download/records/text")
async def download_records_as_text(
    batch_id: str,
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Download all parsed records (committed/shown in dashboard) as pipe-delimited text format.
    Includes all 17 APBS schema columns plus Status column.
    Matches the format displayed in the dashboard.
    
    Query Parameters:
        success_flag: Filter by success flag (e.g., "1", "0")
        reason_code: Filter by reason code
        status: Filter by status (COMMITTED, INVALID, etc.)
        search: Full-text search across Aadhaar, name, account numbers
    """
    try:
        from app.services.record_service import get_paginated_parsed_records
        from app.services.download_service import export_records_as_text
        
        # Get all records (using large page size to get everything)
        records_response = get_paginated_parsed_records(
            batch_id=batch_id if batch_id.lower() != "all" else "ALL",
            batch_status=None,
            db=db,
            page=1,
            page_size=1000000,  # Large number to get all records
            success_flag=success_flag,
            reason_code=reason_code,
            status_filter=status,
            search=search,
            force_refresh=False,
        )
        
        columns = records_response.get("columns", [])
        records = records_response.get("records", [])
        
        text_content = export_records_as_text(records, columns)
        
        print(f"[API] [DOWNLOAD] Text export: {batch_id} ({len(records)} records)")
        
        return PlainTextResponse(
            content=text_content,
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{batch_id}_records.txt"'}
        )
    except Exception as e:
        print(f"[API] [ERROR] Failed to export text: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{batch_id}/import", response_model=ImportResponseSchema)
async def commit_batch_to_sql(batch_id: str, db: Session = Depends(get_db)):
    """
    Explicit SQL database commit. Imports clean data into transactions table.
    """
    try:
        batch = default_batch_manager.get_batch(batch_id)
        if batch.status not in (
            BatchStatus.VERIFIED,
            BatchStatus.COMPLETED,
            BatchStatus.COMPLETED_WITH_ERRORS,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot import batch in state '{batch.status.value}'. Must be processed/verified.",
            )

        print(f"\n[API] [IMPORT] Authorizing SQL database import for Batch: {batch_id}")
        importer = ImportService()
        result = importer.import_batch(batch_id, db)
        batch.status = BatchStatus.IMPORTED
        default_batch_manager._sync_batch_to_db(batch)

        return ImportResponseSchema(
            batch_id=batch_id,
            status=batch.status.value,
            total_processed=result.total_processed,
            total_imported=result.total_imported,
            total_duplicates=result.total_duplicates,
        )
    except BatchNotFoundError:
        raise HTTPException(status_code=404, detail=f"Batch '{batch_id}' not found")


@router.delete("/{batch_id}")
async def delete_batch_endpoint(batch_id: str, db: Session = Depends(get_db)):
    """
    Delete a complete batch from database, memory, and physical storage.
    """
    try:
        from app.services.record_service import clear_records_cache
        res = default_batch_manager.delete_batch(batch_id, db=db)
        clear_records_cache()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete batch: {str(e)}")


@router.delete("/records/{record_id}")
@router.delete("/{batch_id}/records/{record_id}")
async def delete_single_record_endpoint(
    record_id: str,
    batch_id: Optional[str] = None,
    ref: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Delete a single parsed APBS transaction/record by ID or credit reference from database and storage.
    """
    try:
        from app.services.record_service import delete_single_record
        res = delete_single_record(
            record_id=record_id,
            user_credit_reference=ref,
            batch_id=batch_id,
            db=db,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")

