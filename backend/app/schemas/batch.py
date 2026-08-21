"""
Pydantic schemas for Batches and Files.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class FileMetadataSchema(BaseModel):
    filename: str
    sanitized_filename: str
    sha256: str = ""
    size: int = 0
    status: str
    record_count: int = 0
    valid_count: int = 0
    invalid_count: int = 0
    duplicate_count: int = 0
    skipped_count: int = 0
    input_path: str = ""
    output_path: str = ""
    error_path: str = ""
    created_at: datetime
    completed_at: Optional[datetime] = None
    duplicate_of_batch: Optional[str] = None
    duplicate_of_file: Optional[str] = None

    model_config = {"from_attributes": True}


class BatchMetadataSchema(BaseModel):
    batch_id: str
    status: str
    total_files: int
    total_size: int
    total_size_gb: float
    duplicate_files: int
    processable_files: int
    total_records: int
    valid_records: int
    invalid_records: int
    completed_files: int
    failed_files: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    db_push_status: Optional[str] = "Not yet committed"
    db_committed_count: int = 0
    db_duplicates_count: int = 0
    files: dict[str, FileMetadataSchema] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
