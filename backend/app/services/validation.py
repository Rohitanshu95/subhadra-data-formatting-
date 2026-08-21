"""
Streaming file validator for APBS 177-character records.

Reads an input file line-by-line (constant memory), validates
each record, and writes results to output/error files via the
OutputWriter and ErrorWriter, with detailed terminal console logging.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.core.config import settings
from app.services.apbs_parser import is_non_credit_line, parse_line, validate_fields
from app.services.output import ErrorWriter, OutputWriter
from app.utils.masking import mask_aadhaar, mask_account_number


@dataclass
class ProcessingResult:
    """Aggregated statistics from processing a single file."""

    input_file: str
    output_file: str
    error_file: str
    total_lines: int = 0
    valid_records: int = 0
    invalid_records: int = 0
    skipped_lines: int = 0           # non-credit header/trailer lines
    invalid_length_lines: int = 0    # lines that aren't 177 chars
    error_details: list[str] = field(default_factory=list)

    @property
    def processed_records(self) -> int:
        """Lines that were actually parsed (excludes skipped)."""
        return self.valid_records + self.invalid_records

    @property
    def success_rate(self) -> float:
        """Percentage of parsed records that were valid."""
        total = self.processed_records
        if total == 0:
            return 0.0
        return (self.valid_records / total) * 100.0


class StreamingValidator:
    """
    Processes an APBS input file in a streaming fashion with batch buffering.
    """

    def __init__(
        self,
        record_length: int | None = None,
        buffer_size: int | None = None,
    ):
        self._record_length = record_length or settings.APBS_RECORD_LENGTH
        self._buffer_size = buffer_size or getattr(settings, "PROCESSING_BUFFER_SIZE", 5000)

    def process_file(
        self,
        input_path: str,
        output_path: str,
        error_path: str,
    ) -> ProcessingResult:
        """
        Stream-process an entire APBS file with buffered formatting and live console logging.
        """
        filename = os.path.basename(input_path)
        file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
        
        print("\n" + "=" * 85)
        print(f"[STREAM PARSER] [START] Starting Processing: {filename} ({file_size:,} bytes, buffer_size={self._buffer_size})")
        print(f"[STREAM PARSER] Output Path : {output_path}")
        print(f"[STREAM PARSER] Error Path  : {error_path}")
        print("=" * 85)

        result = ProcessingResult(
            input_file=input_path,
            output_file=output_path,
            error_file=error_path,
        )

        with (
            OutputWriter(output_path, buffer_size=self._buffer_size) as output_writer,
            ErrorWriter(error_path, buffer_size=min(self._buffer_size, 1000)) as error_writer,
            open(input_path, "r", encoding="utf-8", buffering=1024 * 1024) as infile,
        ):
            for line_no, raw_line in enumerate(infile, start=1):
                result.total_lines += 1

                # Strip trailing newline/carriage return only
                line = raw_line.rstrip("\r\n")

                # ── Skip empty lines ────────────────────────────
                if not line.strip():
                    result.skipped_lines += 1
                    continue

                # ── Length validation ───────────────────────────
                if len(line) != self._record_length:
                    result.invalid_length_lines += 1
                    result.invalid_records += 1
                    err_msg = f"Length error: expected {self._record_length} chars, got {len(line)}"
                    error_writer.write_error(
                        line_no=line_no,
                        error_type="INVALID_RECORD_LENGTH",
                        detail=err_msg,
                        raw_line=line,
                    )
                    if result.invalid_records <= 5:
                        print(f"[PARSER] [ERROR] Line {line_no:04d}: [INVALID_RECORD_LENGTH] {err_msg}")
                    continue

                # ── Non-credit line detection ───────────────────
                if is_non_credit_line(line):
                    result.skipped_lines += 1
                    continue

                # ── Parse the 17 fields ─────────────────────────
                parsed = parse_line(line)

                # ── Validate fields ─────────────────────────────
                errors = validate_fields(parsed)

                if errors:
                    result.invalid_records += 1
                    error_writer.write_validation_errors(line_no, errors, line)
                    if result.invalid_records <= 5:
                        err_summary = ", ".join([f"{e.field_name}: {e.detail}" for e in errors])
                        print(f"[PARSER] [WARN]  Line {line_no:04d}: Validation Error(s) -> {err_summary}")
                    for err in errors:
                        result.error_details.append(
                            f"Line {line_no}: [{err.error_type}] {err.detail}"
                        )
                else:
                    result.valid_records += 1
                    output_writer.write_record(parsed)

                # Periodic progress heartbeat every 5,000 records
                if line_no % 5000 == 0:
                    print(f"[STREAM PARSER] [PROGRESS] {filename} -> {line_no:,} records processed ({result.valid_records:,} clean, {result.invalid_records:,} invalid)...")

        print("-" * 85)
        print(f"[STREAM PARSER] [DONE] Finished File: {filename}")
        print(f"  * Total Lines Read    : {result.total_lines:,}")
        print(f"  * Valid Clean Records : {result.valid_records:,} (written to clean output)")
        print(f"  * Invalid Error Lines : {result.invalid_records:,} (logged to errors file)")
        print(f"  * Skipped Headers/Etc : {result.skipped_lines:,}")
        print(f"  * File Clean Rate     : {result.success_rate:.2f}%")
        print("=" * 85 + "\n")

        return result
