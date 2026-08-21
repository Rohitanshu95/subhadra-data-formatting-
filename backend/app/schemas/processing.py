"""
Pydantic response schemas for processing results.

These schemas are used by the API layer to serialize
processing results into structured JSON responses.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProcessingResultSchema(BaseModel):
    """API response schema for a single file's processing result."""

    input_file: str = Field(..., description="Path to the input file processed")
    output_file: str = Field(..., description="Path to the generated output file")
    error_file: str = Field(..., description="Path to the generated error file")
    total_lines: int = Field(0, description="Total lines read from the input file")
    valid_records: int = Field(0, description="Number of valid records written to output")
    invalid_records: int = Field(0, description="Number of invalid records written to errors")
    skipped_lines: int = Field(0, description="Non-credit / empty lines skipped")
    invalid_length_lines: int = Field(0, description="Lines with incorrect length (not 177)")
    success_rate: float = Field(0.0, description="Percentage of parsed records that were valid")
    error_details: list[str] = Field(default_factory=list, description="Human-readable error list")

    model_config = {"from_attributes": True}


class HealthCheckSchema(BaseModel):
    """Health check response."""

    status: str = "ok"
    service: str = "apbs-processor"
    version: str = "1.0.0"
