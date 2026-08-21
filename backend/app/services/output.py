"""
Output writers for APBS processing results.

OutputWriter  — writes valid parsed records to pipe-delimited .txt files with memory buffering.
ErrorWriter   — writes error records with line numbers and failure reasons with memory buffering.

Both writers support configurable batch buffering to maximize disk I/O throughput
during high-volume batch processing and formatting.
"""

from __future__ import annotations

import os
from typing import List, Optional, TextIO

from app.core.config import settings
from app.services.apbs_parser import (
    FIELD_SCHEMA,
    ParsedRecord,
    ValidationError,
)


class OutputWriter:
    """
    Streams valid parsed APBS records to a pipe-delimited text file with batch buffering.

    Format:
        - First line: header row with field names
        - Subsequent lines: one record per line, fields separated by delimiter

    Usage:
        with OutputWriter("output.txt", buffer_size=5000) as writer:
            writer.write_record(parsed_record)
    """

    def __init__(
        self,
        output_path: str,
        delimiter: Optional[str] = None,
        buffer_size: Optional[int] = None,
    ):
        self._output_path = output_path
        self._delimiter = delimiter or settings.OUTPUT_DELIMITER
        self._buffer_size = buffer_size or getattr(settings, "PROCESSING_BUFFER_SIZE", 5000)
        self._file: Optional[TextIO] = None
        self._header_written = False
        self._count = 0
        self._buffer: List[str] = []

    def open(self) -> "OutputWriter":
        """Open the output file and write the header."""
        os.makedirs(os.path.dirname(self._output_path), exist_ok=True)
        self._file = open(self._output_path, "w", encoding="utf-8", buffering=1024 * 1024)
        self._write_header()
        return self

    def _write_header(self) -> None:
        """Write the column header row."""
        if self._file is None:
            raise RuntimeError("OutputWriter is not open")
        header = self._delimiter.join(f.name for f in FIELD_SCHEMA)
        self._file.write(header + "\n")
        self._header_written = True

    def write_record(self, record: ParsedRecord) -> None:
        """Format a single valid record and buffer it for writing."""
        if self._file is None:
            raise RuntimeError("OutputWriter is not open")
        values = [record.fields.get(f.name, "") for f in FIELD_SCHEMA]
        line = self._delimiter.join(values) + "\n"
        self._buffer.append(line)
        self._count += 1

        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self) -> None:
        """Flush buffered formatted lines to disk in a single batch write."""
        if self._file is not None and self._buffer:
            self._file.writelines(self._buffer)
            self._buffer.clear()
            self._file.flush()

    @property
    def records_written(self) -> int:
        return self._count

    def close(self) -> None:
        """Flush remaining buffered records and close the output file."""
        if self._file is not None:
            self.flush()
            self._file.close()
            self._file = None

    def __enter__(self) -> "OutputWriter":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()


class ErrorWriter:
    """
    Streams error records to a structured text file with batch buffering.

    Each line has the format:
        LINE:<line_no>|ERROR:<error_type>|DETAIL:<detail>|RAW:<raw_line>

    Usage:
        with ErrorWriter("errors.txt", buffer_size=1000) as writer:
            writer.write_error(line_no, "INVALID_RECORD_LENGTH", "Expected 177, got 150", raw)
            writer.write_validation_errors(line_no, errors, raw_line)
    """

    def __init__(self, error_path: str, buffer_size: int = 1000):
        self._error_path = error_path
        self._buffer_size = buffer_size
        self._file: Optional[TextIO] = None
        self._count = 0
        self._buffer: List[str] = []

    def open(self) -> "ErrorWriter":
        """Open the error file."""
        os.makedirs(os.path.dirname(self._error_path), exist_ok=True)
        self._file = open(self._error_path, "w", encoding="utf-8", buffering=256 * 1024)
        return self

    def write_error(
        self,
        line_no: int,
        error_type: str,
        detail: str,
        raw_line: str,
    ) -> None:
        """Format an error entry and buffer it for writing."""
        if self._file is None:
            raise RuntimeError("ErrorWriter is not open")
        # Sanitize raw_line: replace pipes and newlines to avoid format corruption
        sanitized = raw_line.replace("|", "¦").replace("\n", "").replace("\r", "")
        entry = f"LINE:{line_no}|ERROR:{error_type}|DETAIL:{detail}|RAW:{sanitized}\n"
        self._buffer.append(entry)
        self._count += 1

        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def write_validation_errors(
        self,
        line_no: int,
        errors: list[ValidationError],
        raw_line: str,
    ) -> None:
        """Write one error entry per validation failure for a single line."""
        for err in errors:
            self.write_error(line_no, err.error_type, err.detail, raw_line)

    def flush(self) -> None:
        """Flush buffered formatted error lines to disk in a single batch write."""
        if self._file is not None and self._buffer:
            self._file.writelines(self._buffer)
            self._buffer.clear()
            self._file.flush()

    @property
    def errors_written(self) -> int:
        return self._count

    def close(self) -> None:
        """Flush remaining buffered errors and close the error file."""
        if self._file is not None:
            self.flush()
            self._file.close()
            self._file = None

    def __enter__(self) -> "ErrorWriter":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
