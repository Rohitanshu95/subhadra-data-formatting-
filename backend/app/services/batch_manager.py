"""
Batch manager — orchestrates the full batch lifecycle.

Ties together: batch creation, file upload, deduplication,
storage layout, persistent SQL synchronization, and processing.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import BinaryIO, List, Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.batch import BatchMetadata, BatchStatus
from app.models.db_models import DBBatch, DBFile
from app.models.file import FileMetadata, FileStatus
from app.services.audit import record_log
from app.services.batch import generate_batch_id
from app.services.duplicate import DuplicateInfo, FileDeduplicationService
from app.services.hash import compute_file_hash
from app.services.storage import ensure_storage_dirs, get_batch_paths
from app.services.upload import UploadService
from app.services.validation import StreamingValidator


class BatchLimitError(Exception):
    """Raised when batch limits are exceeded."""
    pass


class BatchNotFoundError(Exception):
    """Raised when a batch ID is not found."""
    pass


class BatchStateError(Exception):
    """Raised when an operation is invalid for the current batch state."""
    pass


class BatchManager:
    """
    Orchestrates the full batch lifecycle with automatic storage hydration
    and SQL persistence.
    """

    def __init__(
        self,
        dedup_service: Optional[FileDeduplicationService] = None,
        upload_service: Optional[UploadService] = None,
    ) -> None:
        self._dedup = dedup_service or FileDeduplicationService()
        self._upload = upload_service or UploadService()
        self._batches: dict[str, BatchMetadata] = {}
        self._hydrate_from_storage()

    # ── Storage & DB Hydration ──────────────────────────────────

    def _load_from_db(self) -> None:
        """
        Load all existing batches and files from the SQL database into memory.
        """
        try:
            db = SessionLocal()
            try:
                db_batches = db.query(DBBatch).all()
                for db_b in db_batches:
                    batch_id = db_b.batch_uuid
                    
                    # Parse status safely
                    try:
                        status = BatchStatus(db_b.status)
                    except ValueError:
                        status = BatchStatus.CREATED

                    batch = BatchMetadata(
                        batch_id=batch_id,
                        status=status,
                        created_at=db_b.created_at or datetime.utcnow(),
                        started_at=db_b.started_at,
                        completed_at=db_b.completed_at,
                    )

                    # Hydrate files from db_b.files relationship
                    if db_b.files:
                        for db_f in db_b.files:
                            try:
                                f_status = FileStatus(db_f.status)
                            except ValueError:
                                f_status = FileStatus.READY

                            file_meta = FileMetadata(
                                filename=db_f.filename,
                                sanitized_filename=db_f.sanitized_filename,
                                sha256=db_f.sha256 or "",
                                size=db_f.size or 0,
                                status=f_status,
                                record_count=db_f.record_count or 0,
                                valid_count=db_f.valid_records or 0,
                                invalid_count=db_f.invalid_records or 0,
                                duplicate_count=db_f.duplicate_records or 0,
                                skipped_count=0,
                                input_path=db_f.input_path or "",
                                output_path=db_f.output_path or "",
                                error_path=db_f.error_path or "",
                                created_at=db_f.created_at or datetime.utcnow(),
                                completed_at=db_f.completed_at,
                            )
                            batch.files[file_meta.sanitized_filename] = file_meta

                    self._batches[batch_id] = batch
            finally:
                db.close()
        except Exception as e:
            print(f"[DB HYDRATION] Warning: Could not hydrate from DB ({e})")

    def _sync_batch_to_db(self, batch: BatchMetadata) -> None:
        """
        Synchronize a BatchMetadata and its FileMetadata to the SQL database.
        """
        try:
            db = SessionLocal()
            try:
                db_b = db.query(DBBatch).filter(DBBatch.batch_uuid == batch.batch_id).first()
                if not db_b:
                    db_b = DBBatch(
                        batch_uuid=batch.batch_id,
                        status=batch.status.value,
                        total_files=batch.total_files,
                        total_size=batch.total_size,
                        total_records=batch.total_records,
                        valid_records=batch.valid_records,
                        invalid_records=batch.invalid_records,
                        duplicate_records=batch.duplicate_files,
                        created_at=batch.created_at,
                        started_at=batch.started_at,
                        completed_at=batch.completed_at,
                    )
                    db.add(db_b)
                    db.flush()
                else:
                    db_b.status = batch.status.value
                    db_b.total_files = batch.total_files
                    db_b.total_size = batch.total_size
                    db_b.total_records = batch.total_records
                    db_b.valid_records = batch.valid_records
                    db_b.invalid_records = batch.invalid_records
                    db_b.duplicate_records = batch.duplicate_files
                    db_b.started_at = batch.started_at
                    db_b.completed_at = batch.completed_at

                # Sync files
                for f in batch.files.values():
                    db_f = (
                        db.query(DBFile)
                        .filter(DBFile.batch_id == db_b.id, DBFile.sanitized_filename == f.sanitized_filename)
                        .first()
                    )
                    if not db_f:
                        db_f = DBFile(
                            batch_id=db_b.id,
                            filename=f.filename,
                            sanitized_filename=f.sanitized_filename,
                            sha256=f.sha256,
                            size=f.size,
                            status=f.status.value,
                            record_count=f.record_count,
                            valid_records=f.valid_count,
                            invalid_records=f.invalid_count,
                            duplicate_records=f.duplicate_count,
                            input_path=f.input_path,
                            output_path=f.output_path,
                            error_path=f.error_path,
                            created_at=f.created_at,
                            completed_at=f.completed_at,
                        )
                        db.add(db_f)
                    else:
                        db_f.sha256 = f.sha256
                        db_f.size = f.size
                        db_f.status = f.status.value
                        db_f.record_count = f.record_count
                        db_f.valid_records = f.valid_count
                        db_f.invalid_records = f.invalid_count
                        db_f.duplicate_records = f.duplicate_count
                        db_f.input_path = f.input_path
                        db_f.output_path = f.output_path
                        db_f.error_path = f.error_path
                        db_f.completed_at = f.completed_at

                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[DB SYNC] Warning: Failed to sync batch {batch.batch_id} to DB: {e}")
            finally:
                db.close()
        except Exception as e:
            print(f"[DB SYNC] Warning: Database connection error during batch sync: {e}")

    def _hydrate_from_storage(self) -> None:
        """
        Scan storage directories and synchronize existing batches into memory and DB.
        """
        self._load_from_db()

        input_base = os.path.join(str(settings.STORAGE_BASE_DIR), "input")
        if not os.path.exists(input_base):
            return

        for batch_dir_name in sorted(os.listdir(input_base)):
            batch_input_path = os.path.join(input_base, batch_dir_name)
            if not os.path.isdir(batch_input_path):
                continue

            batch_id = batch_dir_name
            if batch_id in self._batches:
                continue

            batch = BatchMetadata(batch_id=batch_id)
            ensure_storage_dirs(batch_id)

            paths = get_batch_paths(batch_id)
            if not os.path.exists(str(paths.input_dir)):
                continue

            input_files = [
                f for f in os.listdir(str(paths.input_dir))
                if os.path.isfile(os.path.join(str(paths.input_dir), f))
            ]

            for fname in input_files:
                fpath = os.path.join(str(paths.input_dir), fname)
                fsize = os.path.getsize(fpath)

                file_meta = FileMetadata(
                    filename=fname,
                    sanitized_filename=fname,
                )
                file_meta.mark_ready(
                    sha256="",
                    size=fsize,
                    input_path=fpath,
                )

                base_name = os.path.splitext(fname)[0]
                out_path = os.path.join(str(paths.output_dir), f"{base_name}_output.txt")
                err_path = os.path.join(str(paths.errors_dir), f"{base_name}_errors.txt")

                if os.path.exists(out_path):
                    valid_cnt = 0
                    try:
                        with open(out_path, "r", encoding="utf-8") as of:
                            for idx, l in enumerate(of):
                                if idx > 0 and l.strip():
                                    valid_cnt += 1
                    except Exception:
                        pass

                    invalid_cnt = 0
                    if os.path.exists(err_path):
                        try:
                            with open(err_path, "r", encoding="utf-8") as ef:
                                for l in ef:
                                    if l.strip():
                                        invalid_cnt += 1
                        except Exception:
                            pass

                    file_meta.mark_completed(
                        record_count=valid_cnt + invalid_cnt,
                        valid_count=valid_cnt,
                        invalid_count=invalid_cnt,
                        skipped_count=0,
                        output_path=out_path,
                        error_path=err_path,
                    )

                batch.add_file(file_meta)

            if batch.total_files > 0:
                if batch.completed_files == batch.total_files:
                    batch.status = (
                        BatchStatus.COMPLETED_WITH_ERRORS
                        if batch.invalid_records > 0
                        else BatchStatus.COMPLETED
                    )
                self._batches[batch_id] = batch
                self._sync_batch_to_db(batch)

    # ── Batch creation ──────────────────────────────────────────

    def create_batch(self) -> BatchMetadata:
        """Create a new batch with a unique ID and storage directories."""
        batch_id = generate_batch_id()
        ensure_storage_dirs(batch_id)

        batch = BatchMetadata(batch_id=batch_id)
        self._batches[batch_id] = batch
        self._sync_batch_to_db(batch)
        record_log("RECORD", f"Batch initialized with unique identifier {batch_id}", batch_id=batch_id)
        return batch

    # ── File upload ─────────────────────────────────────────────

    def add_file(
        self,
        batch_id: str,
        filename: str,
        file_stream: BinaryIO,
    ) -> FileMetadata:
        """Upload a file to a batch, computing SHA-256 and checking for duplicates."""
        batch = self._get_batch_or_raise(batch_id)

        if batch.total_files >= settings.MAX_FILES_PER_BATCH:
            raise BatchLimitError(
                f"Batch {batch_id} already has {batch.total_files} files "
                f"(max {settings.MAX_FILES_PER_BATCH})"
            )

        upload_result = self._upload.save_uploaded_file(
            batch_id=batch_id,
            filename=filename,
            file_stream=file_stream,
        )

        new_total_size = batch.total_size + upload_result.file_size
        max_bytes = settings.MAX_BATCH_SIZE_GB * (1024 ** 3)
        if new_total_size > max_bytes:
            if os.path.exists(upload_result.saved_path):
                os.unlink(upload_result.saved_path)
            raise BatchLimitError(
                f"Adding {filename} ({upload_result.file_size} bytes) would exceed "
                f"the {settings.MAX_BATCH_SIZE_GB} GB batch size limit"
            )

        file_meta = FileMetadata(
            filename=upload_result.original_filename,
            sanitized_filename=upload_result.sanitized_filename,
        )
        file_meta.mark_ready(
            sha256=upload_result.sha256,
            size=upload_result.file_size,
            input_path=upload_result.saved_path,
        )

        dup_info = self._dedup.check_duplicate(upload_result.sha256)
        # If duplicate points to a batch that no longer exists (e.g. was deleted), discard orphan entry
        if dup_info is not None and dup_info.original_batch_id not in self._batches:
            self._dedup.unregister_file(upload_result.sha256)
            dup_info = None

        if dup_info is not None:
            file_meta.mark_duplicate(
                original_batch=dup_info.original_batch_id,
                original_file=dup_info.original_filename,
            )
            record_log("INDIVIDUAL DATA", f"Duplicate file detected: {filename} (matches batch {dup_info.original_batch_id})", batch_id=batch_id, file_id=file_meta.sanitized_filename)
        else:
            self._dedup.register_file(
                sha256=upload_result.sha256,
                batch_id=batch_id,
                filename=upload_result.sanitized_filename,
            )
            record_log("INDIVIDUAL DATA", f"Uploaded file {filename} ({file_meta.size:,} bytes) SHA-256: {file_meta.sha256[:16]}...", batch_id=batch_id, file_id=file_meta.sanitized_filename)

        batch.add_file(file_meta)
        batch.status = BatchStatus.UPLOADING
        self._sync_batch_to_db(batch)
        return file_meta

    # ── Batch processing ────────────────────────────────────────

    def process_batch(self, batch_id: str) -> BatchMetadata:
        """Process all non-duplicate files in a batch."""
        batch = self._get_batch_or_raise(batch_id)

        ready_files = [
            f for f in batch.files.values()
            if f.status == FileStatus.READY
        ]
        if not ready_files:
            raise BatchStateError(
                f"Batch {batch_id} has no files in READY state to process"
            )

        batch.mark_processing()
        batch_paths = get_batch_paths(batch_id)
        validator = StreamingValidator()
        record_log("RECORD", f"Started processing {len(ready_files)} file(s) for batch {batch_id}", batch_id=batch_id)

        for file_meta in ready_files:
            file_meta.mark_processing()

            base_name = os.path.splitext(file_meta.sanitized_filename)[0]
            output_path = os.path.join(
                str(batch_paths.output_dir), f"{base_name}_output.txt"
            )
            error_path = os.path.join(
                str(batch_paths.errors_dir), f"{base_name}_errors.txt"
            )

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
                record_log("INDIVIDUAL DATA", f"Processed {file_meta.sanitized_filename}: {result.valid_records:,} valid, {result.invalid_records:,} invalid", batch_id=batch_id, file_id=file_meta.sanitized_filename)
            except Exception as e:
                print(f"[PROCESS ERROR] Failed on {file_meta.sanitized_filename}: {e}")
                file_meta.mark_failed()
                record_log("ERROR", f"File validation failed for {file_meta.sanitized_filename}: {e}", batch_id=batch_id, file_id=file_meta.sanitized_filename)

        batch.mark_completed()
        self._sync_batch_to_db(batch)
        record_log("RECORD", f"Batch {batch_id} processing completed. Status: {batch.status.value}, Total Valid: {batch.valid_records:,}, Invalid: {batch.invalid_records:,}", batch_id=batch_id)
        return batch

    # ── Batch retrieval ─────────────────────────────────────────

    def get_batch(self, batch_id: str) -> BatchMetadata:
        """Retrieve batch metadata by ID."""
        return self._get_batch_or_raise(batch_id)

    def list_batches(self) -> List[BatchMetadata]:
        """List all batches in reverse chronological order from DB and memory."""
        self._load_from_db()
        return sorted(
            self._batches.values(),
            key=lambda b: b.created_at,
            reverse=True,
        )

    def delete_batch(self, batch_id: str, db: Optional[SessionLocal] = None) -> dict:
        """
        Delete a batch completely from memory, physical storage disk, and SQL database.
        Cascading removes: DB files, transactions, duplicate logs, and audit logs.
        """
        import shutil
        from app.models.db_models import DBTransaction, DBDuplicateLog, DBLog

        # 1. Remove from database
        local_db = db or SessionLocal()
        try:
            # Delete transactions
            local_db.query(DBTransaction).filter(DBTransaction.batch_id == batch_id).delete(synchronize_session=False)
            # Delete duplicate logs
            local_db.query(DBDuplicateLog).filter(DBDuplicateLog.attempted_batch_id == batch_id).delete(synchronize_session=False)
            # Delete logs
            local_db.query(DBLog).filter(DBLog.batch_id == batch_id).delete(synchronize_session=False)
            # Delete batch row (cascades to DBFile)
            db_b = local_db.query(DBBatch).filter(DBBatch.batch_uuid == batch_id).first()
            if db_b:
                local_db.delete(db_b)
            local_db.commit()
        except Exception as e:
            local_db.rollback()
            print(f"[DB DELETE] Warning: Error deleting batch {batch_id} from SQL: {e}")
        finally:
            if not db:
                local_db.close()

        # 2. Remove physical storage folders
        batch_paths = get_batch_paths(batch_id)
        for p in (batch_paths.input_dir, batch_paths.output_dir, batch_paths.errors_dir, batch_paths.logs_dir):
            if os.path.exists(p):
                try:
                    shutil.rmtree(p, ignore_errors=True)
                except Exception as e:
                    print(f"[STORAGE DELETE] Warning: Could not remove directory {p}: {e}")

        # 3. Unregister file SHA-256 hashes from deduplication registry
        self._dedup.unregister_batch(batch_id)

        # 4. Remove from in-memory dictionary
        if batch_id in self._batches:
            del self._batches[batch_id]

        print(f"\n[API] [DELETE] Batch {batch_id} successfully deleted from Database, Deduplication Registry & Storage.")
        return {
            "success": True,
            "batch_id": batch_id,
            "message": f"Batch '{batch_id}' and all associated transactions, logs, and files deleted successfully.",
        }

    def _get_batch_or_raise(self, batch_id: str) -> BatchMetadata:
        if batch_id not in self._batches:
            self._load_from_db()
        if batch_id not in self._batches:
            self._hydrate_from_storage()
        if batch_id not in self._batches:
            raise BatchNotFoundError(f"Batch '{batch_id}' not found")
        return self._batches[batch_id]


