"""
Service for retrieving, paginating, and deleting parsed APBS records per batch or record-wise.
Handles PII masking, pipeline status labeling, and dual data-source routing
(records_staging vs. production SQL transactions).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.batch import BatchStatus
from app.models.db_models import DBBatch, DBDuplicateLog, DBFile, DBTransaction
from app.services.apbs_parser import FIELD_SCHEMA
from app.services.storage import get_batch_paths
from app.utils.masking import mask_record_dict


CANONICAL_FIELD_NAMES = [
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
]


def _parse_error_line(line: str, source_file: str = "", batch_id: str = "") -> Optional[Dict[str, Any]]:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return None

    # ErrorWriter writes: LINE:<line_no>|ERROR:<error_type>|DETAIL:<detail>|RAW:<raw_line>
    parts = stripped.split("|")
    entry_data = {}
    for part in parts:
        if ":" in part:
            k, v = part.split(":", 1)
            entry_data[k.upper()] = v

    raw = entry_data.get("RAW", "")
    # Restore pipe character replacement if any
    raw_restored = raw.replace("¦", "|")
    line_no_str = entry_data.get("LINE", "")
    error_type = entry_data.get("ERROR", "INVALID_RECORD")
    detail = entry_data.get("DETAIL", "")

    rec = {f_name: "" for f_name in CANONICAL_FIELD_NAMES}

    if len(raw_restored) == settings.APBS_RECORD_LENGTH:
        try:
            from app.services.apbs_parser import parse_line
            parsed = parse_line(raw_restored)
            for f_name in CANONICAL_FIELD_NAMES:
                rec[f_name] = getattr(parsed, f_name, "").strip()
        except Exception:
            pass
        if not rec.get("beneficiary_name"):
            rec["beneficiary_name"] = f"Beneficiary (Line {line_no_str})" if line_no_str else "Unidentified Beneficiary"
        if not rec.get("user_credit_reference"):
            rec["user_credit_reference"] = f"ERR_L{line_no_str}" if line_no_str else "ERR_UNKNOWN"
    else:
        # For non-177 length records, field column positions are misaligned / corrupt
        rec["beneficiary_name"] = f"Unparsed Record ({len(raw_restored)} chars / expected 177)"
        rec["beneficiary_aadhaar_number"] = "N/A (Length Violation)"
        rec["user_credit_reference"] = f"ERR_L{line_no_str}" if line_no_str else "ERR_UNKNOWN"
        rec["amount"] = "0"
        rec["destination_bank_account_number"] = "N/A"
        rec["destination_bank_iin"] = "N/A"

    rec["id"] = f"err_{batch_id}_{line_no_str}_{rec.get('user_credit_reference', '')}"
    rec["status"] = "Invalid"
    rec["reason_code"] = error_type
    rec["error_type"] = error_type
    rec["error_detail"] = detail
    rec["line_no"] = line_no_str
    rec["raw_line"] = raw_restored
    rec["_source_file"] = source_file
    rec["batch_id"] = batch_id
    return rec


def _parse_output_line(line: str, source_file: str = "") -> Optional[Dict[str, Any]]:
    parts = line.rstrip("\r\n").split(settings.OUTPUT_DELIMITER)
    if len(parts) != len(FIELD_SCHEMA):
        return None
    rec = {}
    for f_def, val in zip(FIELD_SCHEMA, parts):
        rec[f_def.name] = val
    rec["_source_file"] = source_file
    return rec


_RECORDS_CACHE: Dict[str, Any] = {
    "system_all": None,
    "system_errors": None,
    "batches": {},
    "batch_errors": {},
}


def clear_records_cache():
    """Clear in-memory cached record datasets when database or files are modified."""
    global _RECORDS_CACHE
    _RECORDS_CACHE = {
        "system_all": None,
        "system_errors": None,
        "batches": {},
        "batch_errors": {},
    }


def get_paginated_parsed_records(
    batch_id: Optional[str] = None,
    batch_status: Optional[str] = None,
    db: Optional[Session] = None,
    page: int = 1,
    page_size: int = 50,
    success_flag: Optional[str] = None,
    reason_code: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Retrieve server-side paginated and filtered parsed records across all batches or for a specific batch.
    Uses in-memory cache to ensure database is queried only once per session/cycle.
    """
    if force_refresh:
        clear_records_cache()

    records: List[Dict[str, Any]] = []
    data_source = "Production Database & Staging Records"
    b_id = (batch_id or "ALL").upper()

    # Special Fast-Path: If querying exclusively Invalid / Error records
    if status_filter and status_filter.upper() == "INVALID":
        data_source = "Storage Error Logs"
        err_records = []

        if b_id == "ALL":
            cached_err = _RECORDS_CACHE.get("system_errors")
            if cached_err is not None:
                err_records = cached_err
            else:
                err_base = os.path.join(str(settings.STORAGE_BASE_DIR), "errors")
                if os.path.exists(err_base):
                    for sub_dir in os.listdir(err_base):
                        err_dir = os.path.join(err_base, sub_dir)
                        if os.path.isdir(err_dir):
                            for fname in sorted(os.listdir(err_dir)):
                                if fname.endswith("_errors.txt"):
                                    fpath = os.path.join(err_dir, fname)
                                    with open(fpath, "r", encoding="utf-8") as f:
                                        for line in f:
                                            parsed_err = _parse_error_line(line, source_file=fname, batch_id=sub_dir)
                                            if parsed_err:
                                                err_records.append(parsed_err)
                _RECORDS_CACHE["system_errors"] = err_records
        else:
            cached_err = _RECORDS_CACHE.get("batch_errors", {}).get(batch_id)
            if cached_err is not None:
                err_records = cached_err
            else:
                batch_paths = get_batch_paths(batch_id)
                err_dir = str(batch_paths.errors_dir)
                if os.path.exists(err_dir):
                    for fname in sorted(os.listdir(err_dir)):
                        if fname.endswith("_errors.txt"):
                            fpath = os.path.join(err_dir, fname)
                            with open(fpath, "r", encoding="utf-8") as f:
                                for line in f:
                                    parsed_err = _parse_error_line(line, source_file=fname, batch_id=batch_id)
                                    if parsed_err:
                                        err_records.append(parsed_err)
                _RECORDS_CACHE["batch_errors"][batch_id] = err_records

        filtered = []
        for r in err_records:
            if reason_code and str(reason_code).strip() != "":
                if str(reason_code).strip().lower() not in str(r.get("reason_code", "")).strip().lower() and \
                   str(reason_code).strip().lower() not in str(r.get("error_type", "")).strip().lower():
                    continue
            if search and str(search).strip() != "":
                s = str(search).lower().strip()
                searchable_fields = [
                    str(r.get("beneficiary_aadhaar_number", "")),
                    str(r.get("beneficiary_name", "")),
                    str(r.get("user_credit_reference", "")),
                    str(r.get("destination_bank_account_number", "")),
                    str(r.get("destination_bank_iin", "")),
                    str(r.get("reason_code", "")),
                    str(r.get("error_type", "")),
                    str(r.get("error_detail", "")),
                    str(r.get("_source_file", "")),
                    str(r.get("batch_id", "")),
                ]
                if not any(s in f.lower() for f in searchable_fields):
                    continue
            filtered.append(r)

        total = len(filtered)
        page_size = min(max(1, page_size), 1000)
        total_pages = max(1, (total + page_size - 1) // page_size)
        offset = (page - 1) * page_size
        paged_slice = filtered[offset : offset + page_size]
        return {
            "batch_id": batch_id,
            "data_source": data_source,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "columns": CANONICAL_FIELD_NAMES + ["status"],
            "records": paged_slice,
        }

    # If querying all batches or a single batch
    if b_id == "ALL":
        cached_recs = _RECORDS_CACHE.get("system_all")
        if cached_recs is not None:
            records = cached_recs
        else:
            if db:
                tx_query = db.query(DBTransaction)
                for tx in tx_query.all():
                    rec = {f_name: getattr(tx, f_name, "") for f_name in CANONICAL_FIELD_NAMES}
                    rec["id"] = str(tx.id)
                    rec["status"] = "Committed"
                    rec["batch_id"] = tx.batch_id
                    rec["_source_file"] = tx.file_id or ""
                    records.append(rec)

                dup_query = db.query(DBDuplicateLog)
                for dup in dup_query.all():
                    rec = {f_name: "" for f_name in CANONICAL_FIELD_NAMES}
                    rec["id"] = f"dup_{dup.id}"
                    rec["user_credit_reference"] = dup.record_hash[:13]
                    rec["status"] = "Duplicate"
                    rec["reason_code"] = "DUP"
                    rec["batch_id"] = dup.attempted_batch_id
                    rec["_source_file"] = dup.attempted_file_id or ""
                    records.append(rec)

            input_base = os.path.join(str(settings.STORAGE_BASE_DIR), "output")
            if os.path.exists(input_base):
                for b_dir in os.listdir(input_base):
                    out_dir = os.path.join(input_base, b_dir)
                    if os.path.isdir(out_dir):
                        has_db_tx = any(r.get("batch_id") == b_dir for r in records)
                        if not has_db_tx:
                            for fname in sorted(os.listdir(out_dir)):
                                if fname.endswith("_output.txt"):
                                    fpath = os.path.join(out_dir, fname)
                                    with open(fpath, "r", encoding="utf-8") as f:
                                        f.readline()
                                        for line in f:
                                            parsed = _parse_output_line(line, source_file=fname)
                                            if parsed:
                                                parsed["id"] = f"staging_{parsed.get('user_credit_reference', '')}"
                                                parsed["status"] = "Pending Verification"
                                                parsed["batch_id"] = b_dir
                                                records.append(parsed)

            err_base = os.path.join(str(settings.STORAGE_BASE_DIR), "errors")
            if os.path.exists(err_base):
                for b_dir in os.listdir(err_base):
                    err_dir = os.path.join(err_base, b_dir)
                    if os.path.isdir(err_dir):
                        for fname in sorted(os.listdir(err_dir)):
                            if fname.endswith("_errors.txt"):
                                fpath = os.path.join(err_dir, fname)
                                with open(fpath, "r", encoding="utf-8") as f:
                                    for line in f:
                                        parsed_err = _parse_error_line(line, source_file=fname, batch_id=b_dir)
                                        if parsed_err:
                                            records.append(parsed_err)
            _RECORDS_CACHE["system_all"] = records
    else:
        cached_recs = _RECORDS_CACHE.get("batches", {}).get(batch_id)
        if cached_recs is not None:
            records = cached_recs
        else:
            is_imported = (batch_status == BatchStatus.IMPORTED.value or batch_status == "IMPORTED")
            if is_imported and db:
                data_source = "Production Database (transactions table)"
                tx_query = db.query(DBTransaction).filter(DBTransaction.batch_id == batch_id)
                for tx in tx_query.all():
                    rec = {f_name: getattr(tx, f_name, "") for f_name in CANONICAL_FIELD_NAMES}
                    rec["id"] = str(tx.id)
                    rec["status"] = "Committed"
                    rec["batch_id"] = tx.batch_id
                    rec["_source_file"] = tx.file_id or ""
                    records.append(rec)

                dup_query = db.query(DBDuplicateLog).filter(DBDuplicateLog.attempted_batch_id == batch_id)
                for dup in dup_query.all():
                    rec = {f_name: "" for f_name in CANONICAL_FIELD_NAMES}
                    rec["id"] = f"dup_{dup.id}"
                    rec["user_credit_reference"] = dup.record_hash[:13]
                    rec["status"] = "Duplicate"
                    rec["reason_code"] = "DUP"
                    rec["batch_id"] = dup.attempted_batch_id
                    rec["_source_file"] = dup.attempted_file_id or ""
                    records.append(rec)
            else:
                data_source = "records_staging"
                batch_paths = get_batch_paths(batch_id)
                out_dir = str(batch_paths.output_dir)
                if os.path.exists(out_dir):
                    for fname in sorted(os.listdir(out_dir)):
                        if fname.endswith("_output.txt"):
                            fpath = os.path.join(out_dir, fname)
                            with open(fpath, "r", encoding="utf-8") as f:
                                f.readline()
                                for line in f:
                                    parsed = _parse_output_line(line, source_file=fname)
                                    if parsed:
                                        parsed["id"] = f"staging_{parsed.get('user_credit_reference', '')}"
                                        parsed["status"] = "Pending Verification"
                                        parsed["batch_id"] = batch_id
                                        records.append(parsed)

                err_dir = str(batch_paths.errors_dir)
                if os.path.exists(err_dir):
                    for fname in sorted(os.listdir(err_dir)):
                        if fname.endswith("_errors.txt"):
                            fpath = os.path.join(err_dir, fname)
                            with open(fpath, "r", encoding="utf-8") as f:
                                for line in f:
                                    parsed_err = _parse_error_line(line, source_file=fname, batch_id=batch_id)
                                    if parsed_err:
                                        records.append(parsed_err)
            _RECORDS_CACHE["batches"][batch_id] = records

    # Apply dynamic in-memory filtering
    filtered = []
    for r in records:
        # Success Flag matching ('1' or '0')
        if success_flag is not None and str(success_flag).strip() != "":
            req_flag = str(success_flag).strip()
            item_flag = str(r.get("success_flag", "")).strip()
            if not item_flag.startswith(req_flag):
                continue

        # Reason Code matching
        if reason_code is not None and str(reason_code).strip() != "":
            req_reason = str(reason_code).strip().lower()
            item_reason = str(r.get("reason_code", "")).strip().lower()
            if req_reason not in item_reason:
                continue

        # Status matching ('Committed', 'Duplicate', 'Pending Verification', 'Invalid')
        if status_filter is not None and status_filter.upper() != "ALL" and str(status_filter).strip() != "":
            req_status = status_filter.upper().strip()
            item_status = str(r.get("status", "")).upper().strip()
            if req_status not in item_status:
                continue

        # Keyword search matching across all primary fields
        if search and str(search).strip() != "":
            s = str(search).lower().strip()
            searchable_fields = [
                str(r.get("beneficiary_aadhaar_number", "")),
                str(r.get("beneficiary_name", "")),
                str(r.get("user_credit_reference", "")),
                str(r.get("user_number", "")),
                str(r.get("user_name_narration", "")),
                str(r.get("destination_bank_account_number", "")),
                str(r.get("destination_bank_iin", "")),
                str(r.get("reason_code", "")),
                str(r.get("error_type", "")),
                str(r.get("error_detail", "")),
                str(r.get("_source_file", "")),
                str(r.get("batch_id", "")),
            ]
            if not any(s in f.lower() for f in searchable_fields):
                continue

        filtered.append(r)

    total = len(filtered)
    page_size = min(max(1, page_size), 1000)
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    paged_slice = filtered[offset : offset + page_size]

    # Return unmasked records in exact canonical order with error diagnostics
    result_items = []
    for r in paged_slice:
        item = {k: r.get(k, "") for k in CANONICAL_FIELD_NAMES}
        item["id"] = r.get("id") or r.get("user_credit_reference", "")
        item["status"] = r.get("status", "Pending Verification")
        item["_source_file"] = r.get("_source_file", "")
        item["batch_id"] = r.get("batch_id", "")
        item["error_type"] = r.get("error_type", "")
        item["error_detail"] = r.get("error_detail", "")
        item["line_no"] = r.get("line_no", "")
        item["raw_line"] = r.get("raw_line", "")
        result_items.append(item)

    return {
        "batch_id": batch_id,
        "data_source": data_source,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "columns": CANONICAL_FIELD_NAMES + ["status"],
        "records": result_items,
    }


def delete_single_record(
    record_id: Optional[str] = None,
    user_credit_reference: Optional[str] = None,
    batch_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Delete a single record / transaction from database and physical staging files.
    """
    deleted_from_db = False
    deleted_from_staging = False

    # 1. Delete from SQL Database
    if db:
        try:
            # Match by integer id if numeric
            if record_id and record_id.isdigit():
                tx = db.query(DBTransaction).filter(DBTransaction.id == int(record_id)).first()
                if tx:
                    db.delete(tx)
                    deleted_from_db = True
            
            # Match by user_credit_reference
            if not deleted_from_db and user_credit_reference:
                q = db.query(DBTransaction).filter(DBTransaction.user_credit_reference == user_credit_reference)
                if batch_id and batch_id.upper() != "ALL":
                    q = q.filter(DBTransaction.batch_id == batch_id)
                tx_list = q.all()
                for tx in tx_list:
                    db.delete(tx)
                    deleted_from_db = True

            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[RECORD DELETE] Database delete notice: {e}")

    # 2. Delete from physical staging files if applicable
    if batch_id and batch_id.upper() != "ALL":
        batch_paths = get_batch_paths(batch_id)
        out_dir = str(batch_paths.output_dir)
        if os.path.exists(out_dir):
            for fname in os.listdir(out_dir):
                if fname.endswith("_output.txt"):
                    fpath = os.path.join(out_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        if lines:
                            header = lines[0]
                            kept_lines = [header]
                            for line in lines[1:]:
                                stripped = line.strip()
                                if user_credit_reference and user_credit_reference in stripped:
                                    deleted_from_staging = True
                                    continue
                                kept_lines.append(line)
                            with open(fpath, "w", encoding="utf-8") as f:
                                f.writelines(kept_lines)
                    except Exception as e:
                        print(f"[STAGING DELETE] Warning: {e}")

    clear_records_cache()

    return {
        "success": True,
        "record_id": record_id,
        "user_credit_reference": user_credit_reference,
        "deleted_from_db": deleted_from_db,
        "deleted_from_staging": deleted_from_staging,
        "message": "Record successfully deleted from database and staging storage.",
    }
