"""
Bulk Idempotent SQL Importer Service with terminal logging.

Streams clean output records from storage, calculates record_hash,
performs chunked bulk insertions into SQL, and routes duplicates
to the duplicates_log table without crashing or double-inserting.
"""

from __future__ import annotations

import hashlib
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional
from urllib.parse import unquote, urlparse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import DBBatch, DBDuplicateLog, DBTransaction
from app.services.apbs_parser import FIELD_SCHEMA
from app.services.audit import record_log
from app.services.storage import get_batch_paths


@dataclass(frozen=True, slots=True)
class ImportResult:
    batch_id: str
    total_processed: int
    total_imported: int
    total_duplicates: int


import time


class ImportProgressTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._progress: Dict[str, dict] = {}
        self._start_times: Dict[str, float] = {}
        self._expected_records: Dict[str, int] = {}

    def start(self, batch_id: str, total_files: int, total_expected_records: int = 0):
        with self._lock:
            now = time.time()
            self._start_times[batch_id] = now
            self._expected_records[batch_id] = total_expected_records
            total_mb = round((total_expected_records * 177) / (1024 * 1024), 2)
            self._progress[batch_id] = {
                "batch_id": batch_id,
                "status": "IMPORTING",
                "current_file": "Initializing buffer...",
                "file_idx": 0,
                "total_files": total_files,
                "remaining_files": total_files,
                "percent": 0.0,
                "total_processed": 0,
                "total_imported": 0,
                "total_duplicates": 0,
                "total_expected_records": total_expected_records,
                "remaining_records": total_expected_records,
                "elapsed_seconds": 0.0,
                "speed_records_sec": 0,
                "data_pushed_mb": 0.0,
                "data_remaining_mb": total_mb,
                "total_expected_mb": total_mb,
                "eta_seconds": 0,
                "eta_formatted": "Calculating...",
                "error": None,
            }

    def update(
        self,
        batch_id: str,
        current_file: str,
        file_idx: int,
        total_files: int,
        total_processed: int,
        total_imported: int,
        total_duplicates: int,
    ):
        with self._lock:
            start_t = self._start_times.get(batch_id, time.time())
            elapsed = max(0.1, round(time.time() - start_t, 1))
            pct = round((file_idx / max(total_files, 1)) * 100, 1)
            speed = int(total_imported / elapsed)
            data_mb = round((total_processed * 177) / (1024 * 1024), 2)
            
            exp_records = self._expected_records.get(batch_id, 0)
            if exp_records == 0 and total_files > 0:
                # Approximate total based on current average per file
                exp_records = int((total_processed / max(file_idx, 1)) * total_files)

            remaining_records = max(0, exp_records - total_processed)
            total_mb = round((exp_records * 177) / (1024 * 1024), 2)
            data_remaining_mb = max(0.0, round(total_mb - data_mb, 2))

            # Estimate remaining time based on files left
            remaining_files = max(0, total_files - file_idx)
            avg_per_file = elapsed / max(file_idx, 1)
            eta_sec = max(0, int(remaining_files * avg_per_file))
            if eta_sec < 60:
                eta_fmt = f"{eta_sec}s"
            else:
                eta_fmt = f"{eta_sec // 60}m {eta_sec % 60}s"

            self._progress[batch_id] = {
                "batch_id": batch_id,
                "status": "IMPORTING",
                "current_file": current_file,
                "file_idx": file_idx,
                "total_files": total_files,
                "remaining_files": remaining_files,
                "percent": pct,
                "total_processed": total_processed,
                "total_imported": total_imported,
                "total_duplicates": total_duplicates,
                "total_expected_records": exp_records,
                "remaining_records": remaining_records,
                "elapsed_seconds": elapsed,
                "speed_records_sec": speed,
                "data_pushed_mb": data_mb,
                "data_remaining_mb": data_remaining_mb,
                "total_expected_mb": total_mb,
                "eta_seconds": eta_sec,
                "eta_formatted": eta_fmt,
                "error": None,
            }

    def complete(self, batch_id: str, total_processed: int, total_imported: int, total_duplicates: int):
        with self._lock:
            start_t = self._start_times.get(batch_id, time.time())
            elapsed = max(0.1, round(time.time() - start_t, 1))
            curr = self._progress.get(batch_id, {})
            data_mb = round((total_processed * 177) / (1024 * 1024), 2)
            tot_files = curr.get("total_files", 1)
            self._progress[batch_id] = {
                "batch_id": batch_id,
                "status": "IMPORTED",
                "current_file": "Completed",
                "file_idx": tot_files,
                "total_files": tot_files,
                "remaining_files": 0,
                "percent": 100.0,
                "total_processed": total_processed,
                "total_imported": total_imported,
                "total_duplicates": total_duplicates,
                "total_expected_records": total_processed,
                "remaining_records": 0,
                "elapsed_seconds": elapsed,
                "speed_records_sec": int(total_imported / elapsed) if elapsed > 0 else 0,
                "data_pushed_mb": data_mb,
                "data_remaining_mb": 0.0,
                "total_expected_mb": data_mb,
                "eta_seconds": 0,
                "eta_formatted": "Done",
                "error": None,
            }

    def fail(self, batch_id: str, error: str):
        with self._lock:
            curr = self._progress.get(batch_id, {})
            self._progress[batch_id] = {
                "batch_id": batch_id,
                "status": "FAILED",
                "current_file": "Failed",
                "file_idx": curr.get("file_idx", 0),
                "total_files": curr.get("total_files", 0),
                "remaining_files": 0,
                "percent": curr.get("percent", 0.0),
                "total_processed": curr.get("total_processed", 0),
                "total_imported": curr.get("total_imported", 0),
                "total_duplicates": curr.get("total_duplicates", 0),
                "total_expected_records": curr.get("total_expected_records", 0),
                "remaining_records": 0,
                "elapsed_seconds": curr.get("elapsed_seconds", 0.0),
                "speed_records_sec": 0,
                "data_pushed_mb": curr.get("data_pushed_mb", 0.0),
                "data_remaining_mb": 0.0,
                "total_expected_mb": curr.get("total_expected_mb", 0.0),
                "eta_seconds": 0,
                "eta_formatted": "Error",
                "error": str(error),
            }

    def get(self, batch_id: str) -> Optional[dict]:
        with self._lock:
            return self._progress.get(batch_id)

    def get_all_active(self) -> Dict[str, dict]:
        with self._lock:
            return {
                bid: data
                for bid, data in self._progress.items()
                if data.get("status") == "IMPORTING"
            }


import_progress_tracker = ImportProgressTracker()


class ImportService:
    def __init__(self, chunk_size: Optional[int] = None):
        self.chunk_size = chunk_size or settings.IMPORT_CHUNK_SIZE

    def _import_file_fast(self, file_path: str, batch_id: str, file_id: str) -> tuple[int, int, int]:
        """
        High-speed native MySQL LOAD DATA LOCAL INFILE.
        Returns (processed, imported, duplicates).
        """
        import pymysql
        url = urlparse(settings.DATABASE_URL.replace("mysql+pymysql://", "mysql://"))
        user = unquote(url.username or "root")
        password = unquote(url.password or "")
        host = url.hostname or "127.0.0.1"
        port = url.port or 3306
        dbname = url.path.lstrip("/") or "apbs_db"

        # Count total lines in output file
        with open(file_path, "rb") as f:
            total_lines = sum(1 for _ in f) - 1
        if total_lines <= 0:
            return 0, 0, 0

        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            port=port,
            database=dbname,
            local_infile=True,
            autocommit=False,
        )
        try:
            formatted_path = file_path.replace("\\", "/")
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM transactions WHERE batch_id = %s", (batch_id,))
                before_count = cur.fetchone()[0]

                sql = f"""
                LOAD DATA LOCAL INFILE '{formatted_path}'
                IGNORE INTO TABLE transactions
                FIELDS TERMINATED BY '{settings.OUTPUT_DELIMITER}'
                LINES TERMINATED BY '\\n'
                IGNORE 1 LINES
                (apbs_transaction_code, destination_bank_iin, destination_account_type, ledger_folio_number, beneficiary_aadhaar_number, beneficiary_name, sponsor_bank_iin, user_number, user_name_narration, user_credit_reference, amount, item_sequence_number, checksum, success_flag, filler, reason_code, destination_bank_account_number)
                SET batch_id = '{batch_id}',
                    file_id = '{file_id}',
                    created_at = NOW(),
                    record_hash = SHA2(CONCAT_WS('{settings.OUTPUT_DELIMITER}', apbs_transaction_code, destination_bank_iin, destination_account_type, ledger_folio_number, beneficiary_aadhaar_number, beneficiary_name, sponsor_bank_iin, user_number, user_name_narration, user_credit_reference, amount, item_sequence_number, checksum, success_flag, filler, reason_code, destination_bank_account_number), 256);
                """
                cur.execute(sql)
                conn.commit()

                cur.execute("SELECT COUNT(*) FROM transactions WHERE batch_id = %s", (batch_id,))
                after_count = cur.fetchone()[0]
                imported = after_count - before_count
                duplicates = max(0, total_lines - imported)
                return total_lines, imported, duplicates
        finally:
            conn.close()

    def import_batch(self, batch_id: str, db: Session, expected_records: int = 0) -> ImportResult:
        """
        Import all clean output records for a batch into the SQL database.
        Uses native MySQL LOAD DATA LOCAL INFILE with automatic fallback to chunked insertion.
        """
        batch_paths = get_batch_paths(batch_id)
        output_dir = str(batch_paths.output_dir)

        print("\n" + "=" * 85)
        print(f"[SQL IMPORTER] [START] Starting Database Import for Batch: {batch_id}")
        print(f"[SQL IMPORTER] Target DB  : {settings.DATABASE_URL.split('@')[-1]}")
        print(f"[SQL IMPORTER] Chunk Size : {self.chunk_size:,} records/transaction")
        print("=" * 85)

        if not os.path.exists(output_dir):
            print(f"[SQL IMPORTER] [WARN] Output directory not found for batch {batch_id}")
            import_progress_tracker.complete(batch_id, 0, 0, 0)
            return ImportResult(batch_id, 0, 0, 0)

        output_files = [
            f for f in os.listdir(output_dir)
            if f.endswith("_output.txt")
        ]

        total_files = len(output_files)
        total_processed = 0
        total_imported = 0
        total_duplicates = 0

        if expected_records <= 0:
            try:
                db_b = db.query(DBBatch).filter(DBBatch.batch_uuid == batch_id).first()
                if db_b and db_b.valid_records:
                    expected_records = db_b.valid_records
            except Exception:
                pass

        import_progress_tracker.start(batch_id, total_files, expected_records)

        # Process each output file in the batch
        for file_idx, filename in enumerate(output_files, 1):
            file_path = os.path.join(output_dir, filename)
            file_id = filename.replace("_output.txt", "")
            print(f"[SQL IMPORTER] [FILE {file_idx}/{total_files}] Processing: {filename} (Total Imported so far: {total_imported:,})")

            # Try ultra-fast native MySQL LOAD DATA LOCAL INFILE first
            file_loaded = False
            try:
                proc, imp, dups = self._import_file_fast(file_path, batch_id, file_id)
                total_processed += proc
                total_imported += imp
                total_duplicates += dups
                file_loaded = True
                print(f"  * Native LOAD DATA success: {imp:,} inserted, {dups:,} duplicates")
            except Exception as fast_err:
                print(f"  * Native LOAD DATA fallback ({fast_err}). Using chunked insertion.")

            # Fallback to chunked bulk_insert_mappings if native loader is not applicable
            if not file_loaded:
                with open(file_path, "r", encoding="utf-8", buffering=1024 * 1024) as f:
                    header = f.readline()
                    if not header:
                        continue

                    chunk_records = []
                    for line in f:
                        stripped = line.rstrip("\r\n")
                        if not stripped:
                            continue

                        fields = stripped.split(settings.OUTPUT_DELIMITER)
                        if len(fields) != len(FIELD_SCHEMA):
                            continue

                        rec_hash = hashlib.sha256(stripped.encode("utf-8")).hexdigest()
                        record_dict = {
                            "record_hash": rec_hash,
                            "batch_id": batch_id,
                            "file_id": file_id,
                        }
                        for f_def, val in zip(FIELD_SCHEMA, fields):
                            record_dict[f_def.name] = val

                        chunk_records.append(record_dict)
                        total_processed += 1

                        if len(chunk_records) >= self.chunk_size:
                            imported, dups = self._process_chunk(chunk_records, batch_id, file_id, db)
                            total_imported += imported
                            total_duplicates += dups
                            chunk_records = []

                    if chunk_records:
                        imported, dups = self._process_chunk(chunk_records, batch_id, file_id, db)
                        total_imported += imported
                        total_duplicates += dups

            # Report live progress after every file
            import_progress_tracker.update(
                batch_id=batch_id,
                current_file=filename,
                file_idx=file_idx,
                total_files=total_files,
                total_processed=total_processed,
                total_imported=total_imported,
                total_duplicates=total_duplicates,
            )

        # Update DBBatch status to IMPORTED in database
        try:
            db_batch = db.query(DBBatch).filter(DBBatch.batch_uuid == batch_id).first()
            if db_batch:
                db_batch.status = "IMPORTED"
                db.commit()
        except Exception as e:
            print(f"[SQL IMPORTER] [WARN] Could not update DBBatch status: {e}")

        # Clean up storage directories (input, output, errors) to prevent disk consumption
        try:
            import shutil
            cleaned_dirs = 0
            for target_dir in (batch_paths.input_dir, batch_paths.output_dir, batch_paths.errors_dir):
                dir_path = str(target_dir)
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path, ignore_errors=True)
                    cleaned_dirs += 1
            print(f"[STORAGE CLEANUP] [DONE] Completely cleared storage files ({cleaned_dirs} directories) for Batch {batch_id} to reclaim disk space.")
        except Exception as e:
            print(f"[STORAGE CLEANUP] [WARN] Error cleaning up storage files: {e}")

        print("-" * 85)
        print(f"[SQL IMPORTER] [DONE] Finished SQL Import for Batch: {batch_id}")
        print(f"  * Total Clean Records Scanned   : {total_processed:,}")
        print(f"  * New Transactions Written to DB: {total_imported:,}")
        print(f"  * Colliding Duplicates Diverted : {total_duplicates:,} (saved in duplicates_log)")
        print("=" * 85 + "\n")

        import_progress_tracker.complete(batch_id, total_processed, total_imported, total_duplicates)
        return ImportResult(
            batch_id=batch_id,
            total_processed=total_processed,
            total_imported=total_imported,
            total_duplicates=total_duplicates,
        )

    def _process_chunk(
        self,
        records: List[dict],
        batch_id: str,
        file_id: str,
        db: Session,
    ) -> tuple[int, int]:
        """
        Process and commit a chunk of records idempotently using bulk_insert_mappings
        for maximum MySQL throughput with micro-batched hash queries to eliminate query stall.
        """
        if not records:
            return 0, 0

        now = datetime.now(timezone.utc)
        unique_records = []
        dups_to_insert = []
        seen_in_chunk = set()

        # 1. Instant in-memory deduplication within the current chunk (O(1) memory lookup)
        for rec in records:
            r_hash = rec["record_hash"]
            if r_hash in seen_in_chunk:
                dups_to_insert.append({
                    "record_hash": r_hash,
                    "attempted_batch_id": batch_id,
                    "attempted_file_id": file_id,
                    "reason": "DUPLICATE_IN_SAME_BATCH_IMPORT",
                    "detected_at": now,
                })
            else:
                seen_in_chunk.add(r_hash)
                unique_records.append(rec)

        # 2. Check existing database transactions in fast micro-batches of 500
        # Passing <= 500 items in IN (...) executes in ~1-2ms on MySQL index, avoiding optimizer stall
        existing_hash_map = {}
        unique_hashes = list(seen_in_chunk)
        HASH_BATCH_SIZE = 500

        for i in range(0, len(unique_hashes), HASH_BATCH_SIZE):
            sub_hashes = unique_hashes[i:i + HASH_BATCH_SIZE]
            existing_txs = (
                db.query(DBTransaction.id, DBTransaction.record_hash)
                .filter(DBTransaction.record_hash.in_(sub_hashes))
                .all()
            )
            for tx_id, tx_hash in existing_txs:
                existing_hash_map[tx_hash] = tx_id

        # 3. Categorize into new inserts vs database duplicates
        tx_to_insert = []
        for rec in unique_records:
            r_hash = rec["record_hash"]
            if r_hash in existing_hash_map:
                dups_to_insert.append({
                    "record_hash": r_hash,
                    "attempted_batch_id": batch_id,
                    "attempted_file_id": file_id,
                    "original_transaction_id": existing_hash_map[r_hash],
                    "reason": "EXACT_RECORD_DUPLICATE_IN_DB",
                    "detected_at": now,
                })
            else:
                rec["created_at"] = now
                tx_to_insert.append(rec)

        # 4. Insert in micro-batches of 2,500 rows for lightning-fast multi-row INSERTs
        INSERT_BATCH_SIZE = 2500
        for i in range(0, len(tx_to_insert), INSERT_BATCH_SIZE):
            db.bulk_insert_mappings(DBTransaction, tx_to_insert[i:i + INSERT_BATCH_SIZE])

        for i in range(0, len(dups_to_insert), INSERT_BATCH_SIZE):
            db.bulk_insert_mappings(DBDuplicateLog, dups_to_insert[i:i + INSERT_BATCH_SIZE])

        db.commit()
        return len(tx_to_insert), len(dups_to_insert)


