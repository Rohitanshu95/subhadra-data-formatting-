"""
Download and Archiving Service.

Provides secure path retrieval and generates bundled ZIP archives
for outputs, error logs, and batch summaries.
Also provides CSV and text export for parsed records.
"""

from __future__ import annotations

import csv
import io
import os
import zipfile
from typing import Any, Dict, List, Optional
from app.services.storage import get_batch_paths
from app.services.upload import sanitize_filename


def get_output_file_path(batch_id: str, filename: str) -> Optional[str]:
    """Retrieve verified absolute path to an output file."""
    safe_name = sanitize_filename(filename)
    batch_paths = get_batch_paths(batch_id)
    path = os.path.join(str(batch_paths.output_dir), safe_name)
    return path if os.path.isfile(path) else None


def get_error_file_path(batch_id: str, filename: str) -> Optional[str]:
    """Retrieve verified absolute path to an error file."""
    safe_name = sanitize_filename(filename)
    batch_paths = get_batch_paths(batch_id)
    path = os.path.join(str(batch_paths.errors_dir), safe_name)
    return path if os.path.isfile(path) else None


def get_summary_file_path(batch_id: str) -> Optional[str]:
    """Retrieve verified absolute path to the batch summary file."""
    batch_paths = get_batch_paths(batch_id)
    path = os.path.join(str(batch_paths.logs_dir), "batch_summary.txt")
    return path if os.path.isfile(path) else None


def create_batch_zip_archive(batch_id: str) -> Optional[str]:
    """
    Package all outputs, errors, and logs for a batch into a single ZIP archive.

    Returns:
        Path to the generated .zip file, or None if no files exist.
    """
    batch_paths = get_batch_paths(batch_id)
    zip_dir = str(batch_paths.output_dir)
    os.makedirs(zip_dir, exist_ok=True)
    zip_path = os.path.join(zip_dir, f"{batch_id}_results.zip")

    added_files = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add output files
        if os.path.exists(str(batch_paths.output_dir)):
            for f in os.listdir(str(batch_paths.output_dir)):
                if f.endswith("_output.txt"):
                    full_p = os.path.join(str(batch_paths.output_dir), f)
                    zipf.write(full_p, arcname=f"output/{f}")
                    added_files += 1

        # Add error files
        if os.path.exists(str(batch_paths.errors_dir)):
            for f in os.listdir(str(batch_paths.errors_dir)):
                if f.endswith("_errors.txt"):
                    full_p = os.path.join(str(batch_paths.errors_dir), f)
                    zipf.write(full_p, arcname=f"errors/{f}")
                    added_files += 1

        # Add summary file
        summary_p = os.path.join(str(batch_paths.logs_dir), "batch_summary.txt")
        if os.path.isfile(summary_p):
            zipf.write(summary_p, arcname="logs/batch_summary.txt")
            added_files += 1

    return zip_path if added_files > 0 else None


def export_records_as_csv(records: List[Dict[str, Any]], columns: List[str]) -> str:
    """
    Export parsed records as CSV format.
    
    Args:
        records: List of record dictionaries
        columns: List of column names to include
        
    Returns:
        CSV content as string
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, restval="")
    
    # Write header
    writer.writeheader()
    
    # Write data rows
    for record in records:
        writer.writerow({col: record.get(col, "") for col in columns})
    
    return output.getvalue()


def export_records_as_text(records: List[Dict[str, Any]], columns: List[str]) -> str:
    """
    Export parsed records as pipe-delimited text format.
    Matches the format shown in dashboard.
    
    Args:
        records: List of record dictionaries
        columns: List of column names to include
        
    Returns:
        Text content as string (pipe-delimited)
    """
    lines = []
    
    # Write header
    header = "|".join(columns)
    lines.append(header)
    
    # Write data rows
    for record in records:
        row_values = [str(record.get(col, "")).strip() for col in columns]
        row = "|".join(row_values)
        lines.append(row)
    
    return "\n".join(lines)


EXPORT_COLUMNS = [
    "batch_id",
    "apbs_transaction_code",
    "destination_bank_iin",
    "destination_account_type",
    "ledger_folio_number",
    "beneficiary_aadhaar_number",
    "beneficiary_name",
    "sponsor_bank_iin",
    "user_number",
    "user_name_narration",
    "user_credit_reference",
    "amount",
    "item_sequence_number",
    "checksum",
    "success_flag",
    "filler",
    "reason_code",
    "destination_bank_account_number",
    "status",
]


def stream_records_as_csv(
    db,
    batch_id: str = "all",
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    Stream records directly to HTTP client in CSV format with constant memory.
    Streams ALL data from the MySQL database when batch_id is 'all' or not filtered.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    
    # 1. Yield CSV Header
    writer.writerow(EXPORT_COLUMNS)
    yield buffer.getvalue()
    buffer.seek(0)
    buffer.truncate(0)
    
    is_all = (not batch_id or batch_id.lower() == "all")
    
    from app.models.db_models import DBTransaction
    query = db.query(
        DBTransaction.batch_id,
        DBTransaction.apbs_transaction_code,
        DBTransaction.destination_bank_iin,
        DBTransaction.destination_account_type,
        DBTransaction.ledger_folio_number,
        DBTransaction.beneficiary_aadhaar_number,
        DBTransaction.beneficiary_name,
        DBTransaction.sponsor_bank_iin,
        DBTransaction.user_number,
        DBTransaction.user_name_narration,
        DBTransaction.user_credit_reference,
        DBTransaction.amount,
        DBTransaction.item_sequence_number,
        DBTransaction.checksum,
        DBTransaction.success_flag,
        DBTransaction.filler,
        DBTransaction.reason_code,
        DBTransaction.destination_bank_account_number,
    )
    
    if not is_all:
        query = query.filter(DBTransaction.batch_id == batch_id)
    if success_flag is not None and str(success_flag).strip() != "":
        query = query.filter(DBTransaction.success_flag == str(success_flag).strip())
    if reason_code is not None and str(reason_code).strip() != "":
        query = query.filter(DBTransaction.reason_code == str(reason_code).strip())
    if search and str(search).strip() != "":
        s = f"%{str(search).strip()}%"
        query = query.filter(
            (DBTransaction.beneficiary_aadhaar_number.like(s)) |
            (DBTransaction.beneficiary_name.like(s)) |
            (DBTransaction.user_credit_reference.like(s)) |
            (DBTransaction.destination_bank_account_number.like(s))
        )
        
    row_count = 0
    for row in query.yield_per(5000):
        writer.writerow(list(row) + ["Committed"])
        row_count += 1
        if row_count % 5000 == 0:
            chunk = buffer.getvalue()
            buffer.seek(0)
            buffer.truncate(0)
            yield chunk
            
    remaining = buffer.getvalue()
    if remaining:
        yield remaining
        
    # When downloading ALL, also check if any batches in storage/output are uncommitted to DB
    if is_all:
        from app.core.config import settings
        input_base = os.path.join(str(settings.STORAGE_BASE_DIR), "output")
        if os.path.exists(input_base):
            try:
                from sqlalchemy import distinct
                db_batches = set(r[0] for r in db.query(distinct(DBTransaction.batch_id)).all())
                for b_dir in sorted(os.listdir(input_base)):
                    if b_dir not in db_batches:
                        out_dir = os.path.join(input_base, b_dir)
                        if os.path.isdir(out_dir):
                            for fname in sorted(os.listdir(out_dir)):
                                if fname.endswith("_output.txt"):
                                    fpath = os.path.join(out_dir, fname)
                                    with open(fpath, "r", encoding="utf-8") as f:
                                        f.readline()
                                        for line in f:
                                            parts = line.strip().split("|")
                                            if len(parts) >= 17:
                                                writer.writerow([b_dir] + parts[:17] + ["Pending Verification"])
                                                row_count += 1
                                                if row_count % 5000 == 0:
                                                    chunk = buffer.getvalue()
                                                    buffer.seek(0)
                                                    buffer.truncate(0)
                                                    yield chunk
                rem = buffer.getvalue()
                if rem:
                    yield rem
            except Exception as e:
                print(f"[DOWNLOAD] Warning checking uncommitted staging batches: {e}")
    elif row_count == 0:
        # Fallback to staging files for single batch if 0 DB records
        batch_paths = get_batch_paths(batch_id)
        out_dir = str(batch_paths.output_dir)
        if os.path.exists(out_dir):
            for fname in sorted(os.listdir(out_dir)):
                if fname.endswith("_output.txt"):
                    fpath = os.path.join(out_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        f.readline()
                        for line in f:
                            parts = line.strip().split("|")
                            if len(parts) >= 17:
                                writer.writerow([batch_id] + parts[:17] + ["Pending Verification"])
                                row_count += 1
                                if row_count % 5000 == 0:
                                    chunk = buffer.getvalue()
                                    buffer.seek(0)
                                    buffer.truncate(0)
                                    yield chunk
            rem = buffer.getvalue()
            if rem:
                yield rem


def stream_records_as_text(
    db,
    batch_id: str = "all",
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
):
    """
    Stream records directly to HTTP client in pipe-delimited text format with constant memory.
    Streams ALL data from the MySQL database when batch_id is 'all' or not filtered.
    """
    # 1. Yield Text Header
    yield "|".join(EXPORT_COLUMNS) + "\n"
    
    is_all = (not batch_id or batch_id.lower() == "all")
    
    from app.models.db_models import DBTransaction
    query = db.query(
        DBTransaction.batch_id,
        DBTransaction.apbs_transaction_code,
        DBTransaction.destination_bank_iin,
        DBTransaction.destination_account_type,
        DBTransaction.ledger_folio_number,
        DBTransaction.beneficiary_aadhaar_number,
        DBTransaction.beneficiary_name,
        DBTransaction.sponsor_bank_iin,
        DBTransaction.user_number,
        DBTransaction.user_name_narration,
        DBTransaction.user_credit_reference,
        DBTransaction.amount,
        DBTransaction.item_sequence_number,
        DBTransaction.checksum,
        DBTransaction.success_flag,
        DBTransaction.filler,
        DBTransaction.reason_code,
        DBTransaction.destination_bank_account_number,
    )
    
    if not is_all:
        query = query.filter(DBTransaction.batch_id == batch_id)
    if success_flag is not None and str(success_flag).strip() != "":
        query = query.filter(DBTransaction.success_flag == str(success_flag).strip())
    if reason_code is not None and str(reason_code).strip() != "":
        query = query.filter(DBTransaction.reason_code == str(reason_code).strip())
    if search and str(search).strip() != "":
        s = f"%{str(search).strip()}%"
        query = query.filter(
            (DBTransaction.beneficiary_aadhaar_number.like(s)) |
            (DBTransaction.beneficiary_name.like(s)) |
            (DBTransaction.user_credit_reference.like(s)) |
            (DBTransaction.destination_bank_account_number.like(s))
        )
        
    chunk = []
    row_count = 0
    for row in query.yield_per(5000):
        chunk.append("|".join(str(v or "") for v in row) + "|Committed\n")
        row_count += 1
        if len(chunk) >= 5000:
            yield "".join(chunk)
            chunk = []
            
    if chunk:
        yield "".join(chunk)
        
    # When downloading ALL, also check if any batches in storage/output are uncommitted to DB
    if is_all:
        from app.core.config import settings
        input_base = os.path.join(str(settings.STORAGE_BASE_DIR), "output")
        if os.path.exists(input_base):
            try:
                from sqlalchemy import distinct
                db_batches = set(r[0] for r in db.query(distinct(DBTransaction.batch_id)).all())
                staging_chunk = []
                for b_dir in sorted(os.listdir(input_base)):
                    if b_dir not in db_batches:
                        out_dir = os.path.join(input_base, b_dir)
                        if os.path.isdir(out_dir):
                            for fname in sorted(os.listdir(out_dir)):
                                if fname.endswith("_output.txt"):
                                    fpath = os.path.join(out_dir, fname)
                                    with open(fpath, "r", encoding="utf-8") as f:
                                        f.readline()
                                        for line in f:
                                            parts = line.strip().split("|")
                                            if len(parts) >= 17:
                                                staging_chunk.append(f"{b_dir}|" + "|".join(parts[:17]) + "|Pending Verification\n")
                                                row_count += 1
                                                if len(staging_chunk) >= 5000:
                                                    yield "".join(staging_chunk)
                                                    staging_chunk = []
                if staging_chunk:
                    yield "".join(staging_chunk)
            except Exception as e:
                print(f"[DOWNLOAD] Warning checking uncommitted staging batches (text): {e}")
    elif row_count == 0:
        # Fallback to staging files for single batch if 0 DB records
        batch_paths = get_batch_paths(batch_id)
        out_dir = str(batch_paths.output_dir)
        if os.path.exists(out_dir):
            staging_chunk = []
            for fname in sorted(os.listdir(out_dir)):
                if fname.endswith("_output.txt"):
                    fpath = os.path.join(out_dir, fname)
                    with open(fpath, "r", encoding="utf-8") as f:
                        f.readline()
                        for line in f:
                            parts = line.strip().split("|")
                            if len(parts) >= 17:
                                staging_chunk.append(f"{batch_id}|" + "|".join(parts[:17]) + "|Pending Verification\n")
                                row_count += 1
                                if len(staging_chunk) >= 5000:
                                    yield "".join(staging_chunk)
                                    staging_chunk = []
            if staging_chunk:
                yield "".join(staging_chunk)


