"""
Tests for OutputWriter and ErrorWriter.

Covers:
- Output file format (pipe-delimited with header)
- Error file format (LINE:N|ERROR:type|DETAIL:...|RAW:...)
- Context manager usage
- Record counts
"""

import os
import tempfile

import pytest

from app.services.apbs_parser import FIELD_SCHEMA, ValidationError, parse_line
from app.services.output import ErrorWriter, OutputWriter
from tests.conftest import build_valid_record


class TestOutputWriter:

    def test_creates_output_file_with_header(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "output.txt")

        with OutputWriter(path) as writer:
            pass  # just open and close

        with open(path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1  # header only
        header = lines[0].strip()
        field_names = header.split("|")
        assert len(field_names) == 17
        assert field_names[0] == "apbs_transaction_code"

    def test_writes_records_in_pipe_delimited_format(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "output.txt")

        record = parse_line(build_valid_record())

        with OutputWriter(path) as writer:
            writer.write_record(record)
            writer.write_record(record)

        with open(path, "r") as f:
            lines = f.readlines()

        # Header + 2 records
        assert len(lines) == 3
        # Each data line should have 16 pipe separators (17 fields)
        assert lines[1].count("|") == 16

    def test_records_written_count(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "output.txt")

        record = parse_line(build_valid_record())

        with OutputWriter(path) as writer:
            for _ in range(5):
                writer.write_record(record)
            assert writer.records_written == 5

    def test_custom_delimiter(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "output.txt")

        record = parse_line(build_valid_record())

        with OutputWriter(path, delimiter="\t") as writer:
            writer.write_record(record)

        with open(path, "r") as f:
            lines = f.readlines()

        assert "\t" in lines[0]  # header uses tab
        assert "\t" in lines[1]  # data uses tab


class TestErrorWriter:

    def test_creates_error_file(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "errors.txt")

        with ErrorWriter(path) as writer:
            writer.write_error(1, "TEST_ERROR", "Something went wrong", "raw line here")

        assert os.path.exists(path)
        with open(path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 1
        assert lines[0].startswith("LINE:1|ERROR:TEST_ERROR|DETAIL:")

    def test_error_format(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "errors.txt")

        with ErrorWriter(path) as writer:
            writer.write_error(42, "INVALID_RECORD_LENGTH", "Expected 177, got 100", "X" * 100)

        with open(path, "r") as f:
            content = f.read()

        assert "LINE:42" in content
        assert "ERROR:INVALID_RECORD_LENGTH" in content
        assert "DETAIL:Expected 177, got 100" in content
        assert "RAW:" in content

    def test_write_validation_errors(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "errors.txt")

        errors = [
            ValidationError("field_a", 1, "REQUIRED_FIELD_EMPTY", "Field A is empty", "   "),
            ValidationError("field_b", 2, "INVALID_NUMERIC", "Field B not numeric", "abc"),
        ]

        with ErrorWriter(path) as writer:
            writer.write_validation_errors(10, errors, "raw line")

        with open(path, "r") as f:
            lines = f.readlines()

        assert len(lines) == 2  # one entry per validation error
        assert writer.errors_written == 2

    def test_pipes_in_raw_line_are_sanitized(self):
        """Pipes in the raw line content must not break the format."""
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "errors.txt")

        with ErrorWriter(path) as writer:
            writer.write_error(1, "TEST", "detail", "raw|with|pipes")

        with open(path, "r") as f:
            content = f.read()

        # The raw section should not contain literal pipes
        # (they should be replaced with the broken bar character)
        raw_section = content.split("RAW:")[1]
        assert "|" not in raw_section.strip()

    def test_output_writer_buffering_and_flush(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "output_buffered.txt")

        record = parse_line(build_valid_record())

        # buffer size 3
        with OutputWriter(path, buffer_size=3) as writer:
            writer.write_record(record)
            writer.write_record(record)
            # Before threshold, 2 records are buffered in memory
            assert len(writer._buffer) == 2
            
            # Adding 3rd record triggers automatic buffer flush
            writer.write_record(record)
            assert len(writer._buffer) == 0

            # Adding 4th record
            writer.write_record(record)
            assert len(writer._buffer) == 1

        # Closing writer flushes remaining 1 record
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 5  # 1 header + 4 records

    def test_error_writer_buffering_and_flush(self):
        out_dir = tempfile.mkdtemp()
        path = os.path.join(out_dir, "errors_buffered.txt")

        with ErrorWriter(path, buffer_size=2) as writer:
            writer.write_error(1, "ERR1", "Detail 1", "raw 1")
            assert len(writer._buffer) == 1
            writer.write_error(2, "ERR2", "Detail 2", "raw 2")
            assert len(writer._buffer) == 0  # auto flushed
            writer.write_error(3, "ERR3", "Detail 3", "raw 3")
            assert len(writer._buffer) == 1

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 3
