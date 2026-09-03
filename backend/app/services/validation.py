"""
Streaming file validator for APBS 177-character records.

Reads an input file line-by-line (constant memory), validates
each record, and writes results to output/error files via the
OutputWriter and ErrorWriter, with detailed terminal console logging.

Supports both continuous streams (no newlines) and newline-delimited formats,
automatically detecting the input format.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.core.config import settings
from app.services.apbs_parser import is_heading_or_header_line, is_non_credit_line, parse_line, validate_fields
from app.services.output import ErrorWriter, OutputWriter
from app.services.record_separator import stream_apbs_records, detect_file_format
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
        
        Automatically detects and handles both:
        - Continuous streams (177-char fixed-width records with no newlines)
        - Newline-delimited files (legacy format)
        
        For continuous streams:
        - Record 1 (chars 1-177) is the heading row and is skipped
        - Record 2 onwards are processed as data records
        """
        filename = os.path.basename(input_path)
        file_size = os.path.getsize(input_path) if os.path.exists(input_path) else 0
        
        # Detect file format (continuous stream vs newline-delimited)
        file_format = detect_file_format(input_path)
        is_continuous_stream = file_format == "continuous"
        
        print("\n" + "=" * 85)
        print(f"[STREAM PARSER] [START] Starting Processing: {filename} ({file_size:,} bytes, buffer_size={self._buffer_size})")
        print(f"[STREAM PARSER] File Format: {file_format}")
        print(f"[STREAM PARSER] Output Path : {output_path}")
        print(f"[STREAM PARSER] Error Path  : {error_path}")
        print("=" * 85)

        result = ProcessingResult(
            input_file=input_path,
            output_file=output_path,
            error_file=error_path,
        )
        length_adjusted_count = 0

        with (
            OutputWriter(output_path, buffer_size=self._buffer_size) as output_writer,
            ErrorWriter(error_path, buffer_size=min(self._buffer_size, 1000)) as error_writer,
            open(input_path, "r", encoding="utf-8", buffering=1024 * 1024) as infile,
        ):
            for record_number, raw_line in stream_apbs_records(infile, record_length=self._record_length):
                result.total_lines += 1

                # Strip trailing newline/carriage return only
                line = raw_line.rstrip("\r\n")

                # ── Skip empty lines ────────────────────────────
                if not line.strip():
                    result.skipped_lines += 1
                    continue

                # ── Heading record detection (only for continuous stream format) ────
                # In continuous stream, Record 1 is always the heading row
                if is_continuous_stream and record_number == 1:
                    result.skipped_lines += 1
                    print(f"[STREAM PARSER] [HEADER] Record {record_number:04d}: Headings row detected (177 chars) -> Skipped")
                    continue

                # ── Length validation ───────────────────────────
                # In lenient mode, we still need 177 chars for proper field parsing
                # But we'll pad short records or truncate long ones
                if len(line) != self._record_length:
                    length_adjusted_count += 1
                    if len(line) < self._record_length:
                        # Pad short records with spaces
                        padded_line = line + (" " * (self._record_length - len(line)))
                        if length_adjusted_count <= 10:
                            print(f"[PARSER] [INFO]  Record {record_number:04d}: Length {len(line)} chars, padded to {self._record_length}")
                        line = padded_line
                    else:
                        # Truncate long records to 177 chars
                        if length_adjusted_count <= 10:
                            print(f"[PARSER] [INFO]  Record {record_number:04d}: Length {len(line)} chars, truncated to {self._record_length}")
                        line = line[:self._record_length]

                # ── Non-credit line detection (for legacy newline-delimited files) ───────────────────
                if is_non_credit_line(line):
                    result.skipped_lines += 1
                    continue

                # ── Parse the 17 fields ─────────────────────────
                parsed = parse_line(line)

                # ── Validate fields (lenient mode: strict_mode=False) ────────────
                # In lenient mode, we accept all data as-is and don't reject records
                # Only required fields are checked; all other characters are allowed
                errors = validate_fields(parsed, strict_mode=False)

                if errors:
                    # In lenient mode, validation errors are logged but records are STILL WRITTEN to output
                    result.invalid_records += 1
                    # Log warning but don't write to error file
                    if result.invalid_records <= 5:
                        err_summary = ", ".join([f"{e.field_name}: {e.detail}" for e in errors])
                        print(f"[PARSER] [WARN]  Record {record_number:04d}: Validation Warning(s) -> {err_summary}")
                    for err in errors:
                        result.error_details.append(
                            f"Record {record_number}: [{err.error_type}] {err.detail}"
                        )
                    # IMPORTANT: Write to output anyway (lenient processing)
                    result.valid_records += 1
                    output_writer.write_record(parsed)
                else:
                    result.valid_records += 1
                    output_writer.write_record(parsed)

                # Periodic progress heartbeat every 10,000 records
                if record_number % 10000 == 0:
                    print(f"[STREAM PARSER] [PROGRESS] {filename} -> {record_number:,} records processed ({result.valid_records:,} clean, {result.invalid_records:,} invalid)...")

        print("-" * 85)
        print(f"[STREAM PARSER] [DONE] Finished File: {filename}")
        print(f"  * Total Lines Read    : {result.total_lines:,}")
        print(f"  * Records to Output   : {result.valid_records:,} (all valid & lenient-validated records)")
        print(f"  * Validation Warnings : {result.invalid_records:,} (logged but written to output)")
        print(f"  * Skipped Headers/Etc : {result.skipped_lines:,}")
        if length_adjusted_count > 10:
            print(f"  * Length-Adjusted Recs : {length_adjusted_count:,} total (first 10 logged above)")
        print(f"  * Processing Mode     : LENIENT (accept all data as-is, no records rejected)")
        print("=" * 85 + "\n")

        return result
