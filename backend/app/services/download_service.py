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

