"""
Batch Summary Report Generator.

Generates human-readable batch summary report files stored at:
    storage/logs/{batch_id}/batch_summary.txt
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from app.models.batch import BatchMetadata
from app.services.storage import get_batch_paths


def generate_batch_summary(batch: BatchMetadata) -> str:
    """
    Generate a structured batch summary text file and return the summary content.

    Args:
        batch: The batch metadata object.

    Returns:
        The generated summary string.
    """
    batch_paths = get_batch_paths(batch.batch_id)
    os.makedirs(str(batch_paths.logs_dir), exist_ok=True)
    summary_path = os.path.join(str(batch_paths.logs_dir), "batch_summary.txt")

    lines = []
    lines.append("=" * 80)
    lines.append(f" APBS BATCH PROCESSING SUMMARY: {batch.batch_id}")
    lines.append("=" * 80)
    lines.append(f"Status              : {batch.status.value}")
    lines.append(f"Created At (UTC)    : {batch.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    started = batch.started_at.strftime('%Y-%m-%d %H:%M:%S') if batch.started_at else "N/A"
    completed = batch.completed_at.strftime('%Y-%m-%d %H:%M:%S') if batch.completed_at else "N/A"
    lines.append(f"Started At (UTC)    : {started}")
    lines.append(f"Completed At (UTC)  : {completed}")
    lines.append("-" * 80)
    lines.append(f"Total Files Uploaded: {batch.total_files}")
    lines.append(f"Processable Files   : {batch.processable_files}")
    lines.append(f"Duplicate Files     : {batch.duplicate_files}")
    lines.append(f"Completed Files     : {batch.completed_files}")
    lines.append(f"Failed Files        : {batch.failed_files}")
    lines.append(f"Total Size          : {batch.total_size:,} bytes ({batch.total_size_gb:.4f} GB)")
    lines.append("-" * 80)
    lines.append(f"Total Records Read  : {batch.total_records:,}")
    lines.append(f"Valid Clean Records : {batch.valid_records:,}")
    lines.append(f"Invalid Records     : {batch.invalid_records:,}")
    
    success_rate = 0.0
    if batch.total_records > 0:
        success_rate = (batch.valid_records / batch.total_records) * 100.0
    lines.append(f"Overall Success Rate: {success_rate:.2f}%")
    lines.append("=" * 80)
    lines.append(" FILE-BY-FILE BREAKDOWN")
    lines.append("-" * 80)
    
    header = f"{'Filename':<28} | {'Status':<16} | {'Total':<8} | {'Valid':<8} | {'Invalid':<8} | {'SHA-256':<16}"
    lines.append(header)
    lines.append("-" * 80)

    for filename, fmeta in batch.files.items():
        short_hash = fmeta.sha256[:12] + "..." if len(fmeta.sha256) > 15 else fmeta.sha256
        row = (
            f"{fmeta.sanitized_filename[:28]:<28} | "
            f"{fmeta.status.value[:16]:<16} | "
            f"{fmeta.record_count:<8} | "
            f"{fmeta.valid_count:<8} | "
            f"{fmeta.invalid_count:<8} | "
            f"{short_hash:<16}"
        )
        lines.append(row)

    lines.append("=" * 80)
    summary_content = "\n".join(lines) + "\n"

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(summary_content)

    return summary_content
