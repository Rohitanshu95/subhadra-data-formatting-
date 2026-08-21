"""
Preview Service for Human Verification Checkpoint with PII Masking.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional
from app.core.config import settings
from app.services.apbs_parser import FIELD_SCHEMA
from app.services.storage import get_batch_paths
from app.utils.masking import mask_record_dict


def get_clean_records_preview(batch_id: str, limit: int = 20, mask_pii: bool = True) -> List[Dict[str, str]]:
    """
    Read up to `limit` clean records from the batch output directory.
    PII fields are automatically masked by default.
    """
    batch_paths = get_batch_paths(batch_id)
    output_dir = str(batch_paths.output_dir)

    if not os.path.exists(output_dir):
        return []

    output_files = [f for f in os.listdir(output_dir) if f.endswith("_output.txt")]
    records: List[Dict[str, str]] = []

    for filename in sorted(output_files):
        file_path = os.path.join(output_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            header = f.readline()
            if not header:
                continue

            for line in f:
                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue

                parts = stripped.split(settings.OUTPUT_DELIMITER)
                if len(parts) == len(FIELD_SCHEMA):
                    rec = {f_def.name: val for f_def, val in zip(FIELD_SCHEMA, parts)}
                    rec["_source_file"] = filename
                    
                    if mask_pii:
                        rec = mask_record_dict(rec)

                    records.append(rec)

                    if len(records) >= limit:
                        return records

    return records


def get_error_records_preview(batch_id: str, limit: int = 20) -> List[Dict[str, str]]:
    """
    Read up to `limit` error log rows from the batch errors directory.
    """
    batch_paths = get_batch_paths(batch_id)
    errors_dir = str(batch_paths.errors_dir)

    if not os.path.exists(errors_dir):
        return []

    error_files = [f for f in os.listdir(errors_dir) if f.endswith("_errors.txt")]
    errors: List[Dict[str, str]] = []

    for filename in sorted(error_files):
        file_path = os.path.join(errors_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue

                entry = {"_source_file": filename, "raw_entry": stripped}
                parts = stripped.split("|")
                for part in parts:
                    if ":" in part:
                        k, v = part.split(":", 1)
                        entry[k.lower()] = v

                errors.append(entry)
                if len(errors) >= limit:
                    return errors

    return errors


def get_summary_content(batch_id: str) -> Optional[str]:
    """
    Read the contents of batch_summary.txt.
    """
    batch_paths = get_batch_paths(batch_id)
    summary_path = os.path.join(str(batch_paths.logs_dir), "batch_summary.txt")

    if not os.path.exists(summary_path):
        return None

    with open(summary_path, "r", encoding="utf-8") as f:
        return f.read()
