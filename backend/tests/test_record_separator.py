"""
Tests for the streaming record separator.

Covers:
- Continuous stream format (no newlines, 177-char fixed-width records)
- Newline-delimited format (legacy, auto-detection)
- Character boundary verification (Record 2 starts at char 178)
- Partial records at EOF
- Heading record detection and skipping
- Full regression test suite
"""

import os
import pytest
import io

from app.services.record_separator import stream_apbs_records, detect_file_format
from app.services.validation import StreamingValidator
from tests.conftest import (
    build_valid_record,
    build_non_credit_record,
    build_record_with_empty_required_field,
    build_record_with_invalid_numeric,
    build_short_record,
    build_long_record,
    create_output_paths,
    create_test_file,
)


class TestRecordSeparatorContinuousStream:
    """Test record separator with continuous stream format (no newlines)."""

    def test_continuous_stream_three_records(self):
        """
        Test continuous stream with heading + 2 data records (531 total chars).
        
        Record 1 (chars 1-177): Heading row (should be skipped)
        Record 2 (chars 178-354): Data record 1
        Record 3 (chars 355-531): Data record 2
        """
        # Create a heading record (transaction code '33')
        heading_record = build_non_credit_record()
        data_record_1 = build_valid_record()
        data_record_2 = build_valid_record(user_number="USR0002")
        
        # Concatenate without newlines (continuous stream)
        continuous_stream = heading_record + data_record_1 + data_record_2
        assert len(continuous_stream) == 531
        
        # Parse with stream_apbs_records
        file_obj = io.StringIO(continuous_stream)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        # Should yield 3 records
        assert len(records) == 3
        assert records[0] == (1, heading_record)
        assert records[1] == (2, data_record_1)
        assert records[2] == (3, data_record_2)

    def test_continuous_stream_character_boundary(self):
        """
        Verify that Record 2 starts at precisely character 178.
        
        Record 1: chars 1-177
        Record 2: chars 178-354
        """
        heading_record = build_non_credit_record()
        data_record_1 = build_valid_record(user_number="USRTEST1")
        
        continuous_stream = heading_record + data_record_1
        assert len(continuous_stream) == 354
        
        # Verify characters
        assert continuous_stream[0:177] == heading_record
        assert continuous_stream[177:354] == data_record_1
        
        # Parse and verify
        file_obj = io.StringIO(continuous_stream)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        assert records[0][1] == heading_record
        assert records[1][1] == data_record_1

    def test_continuous_stream_partial_record_at_eof(self):
        """
        Test that partial records at EOF are yielded (so validator can flag as INVALID_RECORD_LENGTH).
        
        File: 354 chars (2 complete records) + 45 chars (partial 3rd record)
        """
        heading_record = build_non_credit_record()
        data_record_1 = build_valid_record()
        partial_record = "X" * 45  # Incomplete record
        
        continuous_stream = heading_record + data_record_1 + partial_record
        expected_length = 177 + 177 + 45
        assert len(continuous_stream) == expected_length
        
        file_obj = io.StringIO(continuous_stream)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        # Should yield 3 records: 2 complete + 1 partial
        assert len(records) == 3
        assert records[0][1] == heading_record
        assert records[1][1] == data_record_1
        assert records[2] == (3, partial_record)
        assert len(records[2][1]) == 45  # Confirm it's the partial

    def test_continuous_stream_multiple_data_records(self):
        """Test continuous stream with many data records (stress test)."""
        heading_record = build_non_credit_record()
        data_records = [
            build_valid_record(user_number=f"USR{i:04d}") 
            for i in range(1, 11)
        ]
        
        continuous_stream = heading_record + "".join(data_records)
        assert len(continuous_stream) == 177 + (10 * 177)
        
        file_obj = io.StringIO(continuous_stream)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        assert len(records) == 11
        assert records[0][1] == heading_record
        for i, (record_num, record_str) in enumerate(records[1:], start=1):
            assert record_num == i + 1
            assert record_str == data_records[i - 1]


class TestRecordSeparatorNewlineDelimited:
    """Test record separator with newline-delimited format (legacy)."""

    def test_newline_delimited_three_records(self):
        """Test newline-delimited format with 3 records."""
        lines = [
            build_non_credit_record(),
            build_valid_record(),
            build_valid_record(user_number="USR0002"),
        ]
        
        # Join with newlines (legacy format)
        content = "\n".join(lines)
        
        file_obj = io.StringIO(content)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        # Should yield 3 records with newlines stripped
        assert len(records) == 3
        for i, (record_num, record_str) in enumerate(records, start=1):
            assert record_num == i
            assert record_str == lines[i - 1]
            assert "\n" not in record_str

    def test_newline_delimited_with_crlf(self):
        """Test newline-delimited format with CRLF line endings."""
        lines = [
            build_non_credit_record(),
            build_valid_record(),
        ]
        
        # Join with CRLF
        content = "\r\n".join(lines)
        
        file_obj = io.StringIO(content)
        records = list(stream_apbs_records(file_obj, record_length=177))
        
        assert len(records) == 2
        assert records[0][1] == lines[0]
        assert records[1][1] == lines[1]


class TestRecordSeparatorEmptyFile:
    """Test edge case: empty file."""

    def test_empty_file(self):
        """Test that empty file yields no records."""
        file_obj = io.StringIO("")
        records = list(stream_apbs_records(file_obj, record_length=177))
        assert len(records) == 0


class TestFileFormatDetection:
    """Test automatic file format detection."""

    def test_detect_continuous_stream(self):
        """Detect continuous stream format."""
        heading = build_non_credit_record()
        data = build_valid_record()
        
        with open("/tmp/test_continuous.txt", "w") as f:
            f.write(heading + data)
        
        try:
            fmt = detect_file_format("/tmp/test_continuous.txt")
            assert fmt == "continuous"
        finally:
            os.unlink("/tmp/test_continuous.txt")

    def test_detect_newline_delimited(self):
        """Detect newline-delimited format."""
        lines = [build_non_credit_record(), build_valid_record()]
        
        with open("/tmp/test_newline.txt", "w") as f:
            f.write("\n".join(lines))
        
        try:
            fmt = detect_file_format("/tmp/test_newline.txt")
            assert fmt == "newline-delimited"
        finally:
            os.unlink("/tmp/test_newline.txt")


class TestStreamingValidatorWithContinuousStream:
    """Integration tests: StreamingValidator with continuous stream format."""

    def test_continuous_stream_heading_skipped(self):
        """
        Test that heading record (Record 1) is properly skipped.
        
        - Input: heading (177 chars) + 2 valid data records (354 chars) = 531 chars, no newlines
        - Expected: skipped_lines = 1 (heading), valid_records = 2
        """
        heading = build_non_credit_record()
        data_1 = build_valid_record()
        data_2 = build_valid_record(user_number="USR0002")
        
        continuous_stream = heading + data_1 + data_2
        
        # Write as continuous stream (no newlines)
        with open("/tmp/test_heading_skip.txt", "w") as f:
            f.write(continuous_stream)
        
        output_path, error_path = create_output_paths()
        
        try:
            validator = StreamingValidator()
            result = validator.process_file(
                "/tmp/test_heading_skip.txt",
                output_path,
                error_path
            )
            
            # Verify results
            assert result.total_lines == 3
            assert result.skipped_lines == 1  # Heading row
            assert result.valid_records == 2  # Two data records
            assert result.invalid_records == 0
            assert result.success_rate == 100.0
            
            # Verify output file has header + 2 data rows
            with open(output_path) as f:
                lines = f.readlines()
                # Should have CSV header + 2 data rows
                assert len(lines) >= 2  # At least 2 data rows (header is optional)
        finally:
            os.unlink("/tmp/test_heading_skip.txt")

    def test_continuous_stream_with_invalid_records(self):
        """
        Test continuous stream with mixed valid/invalid records.
        
        - Heading + valid record + invalid record (wrong length) + valid record
        """
        heading = build_non_credit_record()
        valid_1 = build_valid_record()
        invalid = "X" * 100  # Wrong length
        valid_2 = build_valid_record(user_number="USR0002")
        
        # Create test file by writing heading + valid + padding + valid
        # We need to reconstruct since we can't just concatenate different lengths
        continuous_stream = heading + valid_1 + invalid + valid_2
        
        with open("/tmp/test_mixed.txt", "w") as f:
            f.write(continuous_stream)
        
        output_path, error_path = create_output_paths()
        
        try:
            validator = StreamingValidator()
            result = validator.process_file(
                "/tmp/test_mixed.txt",
                output_path,
                error_path
            )
            
            # Verify: 1 heading + 1 valid + 1 invalid + 1 partial
            assert result.total_lines == 4
            assert result.skipped_lines == 1  # Heading
            assert result.valid_records == 1  # Only one valid
            assert result.invalid_records >= 2  # Invalid length + partial/invalid
        finally:
            os.unlink("/tmp/test_mixed.txt")

    def test_continuous_stream_preserves_legacy_support(self):
        """
        Ensure newline-delimited files still work (regression test).
        
        Process a traditional line-by-line file and verify it works.
        """
        lines = [
            build_valid_record(),
            build_valid_record(user_number="USR0002"),
            build_valid_record(user_number="USR0003"),
        ]
        
        input_path = create_test_file(lines)  # Creates newline-delimited file
        output_path, error_path = create_output_paths()
        
        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)
            
            assert result.total_lines == 3
            assert result.valid_records == 3
            assert result.invalid_records == 0
            assert result.skipped_lines == 0
        finally:
            os.unlink(input_path)


class TestHeadingDetection:
    """Test heading record detection logic."""

    def test_heading_record_is_first_record(self):
        """Verify that record_number == 1 is always treated as heading."""
        from app.services.apbs_parser import is_heading_or_header_line
        
        # Any record at position 1 should be a heading
        record = build_valid_record()
        assert is_heading_or_header_line(record, record_number=1)

    def test_data_record_is_not_heading(self):
        """Verify that record_number > 1 are treated as data."""
        from app.services.apbs_parser import is_heading_or_header_line
        
        # Data records should not be headings
        record = build_valid_record()
        assert not is_heading_or_header_line(record, record_number=2)
        assert not is_heading_or_header_line(record, record_number=3)

    def test_transaction_code_33_is_non_credit(self):
        """Verify that transaction code '33' is detected as non-credit."""
        from app.services.apbs_parser import is_non_credit_line
        
        record = build_non_credit_record()
        assert is_non_credit_line(record)

    def test_transaction_code_77_is_credit(self):
        """Verify that transaction code '77' is detected as credit."""
        from app.services.apbs_parser import is_non_credit_line
        
        record = build_valid_record(transaction_code="77")
        assert not is_non_credit_line(record)


class TestRegressionAllExistingTests:
    """
    Regression test: Ensure all existing test files still pass.
    
    This validates that the new record separator doesn't break
    backward compatibility with existing newline-delimited tests.
    """

    def test_all_valid_records_legacy(self):
        """Existing test: all valid records in newline-delimited format."""
        lines = [build_valid_record() for _ in range(10)]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 10
            assert result.valid_records == 10
            assert result.invalid_records == 0
            assert result.skipped_lines == 0
            assert result.success_rate == 100.0
        finally:
            os.unlink(input_path)

    def test_mixed_valid_invalid_legacy(self):
        """Existing test: mixed valid and invalid records."""
        lines = [
            build_valid_record(),
            build_record_with_invalid_numeric(),
            build_valid_record(),
            build_short_record(),
            build_valid_record(),
        ]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 5
            assert result.valid_records == 3
            assert result.invalid_records == 2
        finally:
            os.unlink(input_path)

    def test_non_credit_lines_skipped_legacy(self):
        """Existing test: non-credit lines are skipped without errors."""
        lines = [
            build_valid_record(),
            build_non_credit_record(),
            build_valid_record(),
        ]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 3
            assert result.valid_records == 2
            assert result.invalid_records == 0
            assert result.skipped_lines == 1
        finally:
            os.unlink(input_path)
