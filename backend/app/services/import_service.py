"""
Bulk Idempotent SQL Importer Service with terminal logging.

Streams clean output records from storage, calculates record_hash,
performs chunked bulk insertions into SQL, and routes duplicates
to the duplicates_log table without crashing or double-inserting.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.db_models import DBBatch, DBDuplicateLog, DBTransaction
from app.services.apbs_parser import FIELD_SCHEMA
from app.services.audit import record_log
from app.services.hash import compute_record_hash
from app.services.storage import get_batch_paths


@dataclass(frozen=True, slots=True)
class ImportResult:
    batch_id: str
    total_processed: int
    total_imported: int
    total_duplicates: int


def reconstruct_177_line_from_fields(field_values: List[str]) -> str:
    """
    Reconstruct the 177-character normalized line from the 17 field values
    according to the canonical FIELD_SCHEMA widths.
    """
    parts = []
    for val, field_def in zip(field_values, FIELD_SCHEMA):
        # Pad with spaces to exact width and truncate if necessary
        padded = val.ljust(field_def.width)[:field_def.width]
        parts.append(padded)
    return "".join(parts)


class ImportService:
    def __init__(self, chunk_size: Optional[int] = None):
        self.chunk_size = chunk_size or settings.IMPORT_CHUNK_SIZE

    def import_batch(self, batch_id: str, db: Session) -> ImportResult:
        """
        Import all clean output records for a batch into the SQL database.
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
            return ImportResult(batch_id, 0, 0, 0)

        output_files = [
            f for f in os.listdir(output_dir)
            if f.endswith("_output.txt")
        ]

        total_processed = 0
        total_imported = 0
        total_duplicates = 0

        # Process each output file in the batch
        for filename in output_files:
            file_path = os.path.join(output_dir, filename)
            file_id = filename.replace("_output.txt", "")
            print(f"[SQL IMPORTER] [READ] Reading clean output file: {filename}")

            with open(file_path, "r", encoding="utf-8") as f:
                header = f.readline()  # skip header
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

                    # Reconstruct normalized 177-character line for hashing
                    normalized_line = reconstruct_177_line_from_fields(fields)
                    rec_hash = compute_record_hash(normalized_line)

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
                        print(f"  [SQL CHUNK] [COMMIT] Chunk of {len(chunk_records):,} rows -> {imported:,} new inserted | {dups:,} duplicates recorded.")
                        chunk_records = []

                if chunk_records:
                    imported, dups = self._process_chunk(chunk_records, batch_id, file_id, db)
                    total_imported += imported
                    total_duplicates += dups
                    print(f"  [SQL CHUNK] [COMMIT] Final chunk of {len(chunk_records):,} rows -> {imported:,} new inserted | {dups:,} duplicates recorded.")

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

        record_log("BATCH", f"Batch {batch_id} committed to SQL: {total_imported:,} new transactions inserted, {total_duplicates:,} duplicates recorded", batch_id=batch_id)

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
        Process and commit a chunk of records idempotently.
        """
        if not records:
            return 0, 0

        hashes = [r["record_hash"] for r in records]

        # Query existing transactions with matching hashes
        existing_txs = (
            db.query(DBTransaction.id, DBTransaction.record_hash)
            .filter(DBTransaction.record_hash.in_(hashes))
            .all()
        )
        existing_hash_map = {tx.record_hash: tx.id for tx in existing_txs}

        tx_to_insert = []
        dups_to_insert = []
        seen_in_chunk = set()

        for rec in records:
            r_hash = rec["record_hash"]

            if r_hash in existing_hash_map:
                # Existing in database
                dup = DBDuplicateLog(
                    record_hash=r_hash,
                    attempted_batch_id=batch_id,
                    attempted_file_id=file_id,
                    original_transaction_id=existing_hash_map[r_hash],
                    reason="EXACT_RECORD_DUPLICATE_IN_DB",
                )
                dups_to_insert.append(dup)
            elif r_hash in seen_in_chunk:
                # Duplicate within the same chunk
                dup = DBDuplicateLog(
                    record_hash=r_hash,
                    attempted_batch_id=batch_id,
                    attempted_file_id=file_id,
                    reason="DUPLICATE_IN_SAME_BATCH_IMPORT",
                )
                dups_to_insert.append(dup)
            else:
                seen_in_chunk.add(r_hash)
                tx = DBTransaction(**rec)
                tx_to_insert.append(tx)

        if tx_to_insert:
            db.bulk_save_objects(tx_to_insert)
        if dups_to_insert:
            db.bulk_save_objects(dups_to_insert)

        db.commit()
        return len(tx_to_insert), len(dups_to_insert)
