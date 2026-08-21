"""
Tests for the streaming validation pipeline.

Covers:
- End-to-end processing of valid files
- Mixed files with valid, invalid, and non-credit lines
- INVALID_RECORD_LENGTH detection for short/long lines
- Non-credit lines are skipped without errors
- Output and error file format verification
"""

import os
import pytest

from app.services.validation import StreamingValidator
from tests.conftest import (
    build_long_record,
    build_non_credit_record,
    build_record_with_empty_required_field,
    build_record_with_invalid_numeric,
    build_short_record,
    build_valid_record,
    create_output_paths,
    create_test_file,
)


class TestStreamingValidatorValidFile:
    """Test processing a file that contains only valid records."""

    def test_all_valid_records(self):
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

    def test_output_file_created_with_header(self):
        lines = [build_valid_record()]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            validator.process_file(input_path, output_path, error_path)

            assert os.path.exists(output_path)
            with open(output_path, "r") as f:
                content = f.readlines()
            # Header + 1 data row
            assert len(content) == 2
            # Header should contain field names separated by pipe
            assert "apbs_transaction_code" in content[0]
            assert "|" in content[0]
        finally:
            os.unlink(input_path)


class TestStreamingValidatorMixedFile:
    """Test processing files with a mix of valid, invalid, and non-credit records."""

    def test_mixed_records(self):
        lines = [
            build_valid_record(),                       # valid
            build_valid_record(transaction_code="88"),   # valid (returned)
            build_non_credit_record(),                   # skipped
            build_short_record(),                        # invalid length
            build_record_with_invalid_numeric(),         # invalid field
            build_valid_record(),                       # valid
        ]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 6
            assert result.valid_records == 3
            assert result.invalid_records == 2  # short + invalid numeric
            assert result.skipped_lines == 1    # non-credit line
        finally:
            os.unlink(input_path)

    def test_error_file_has_entries(self):
        lines = [
            build_short_record(),
            build_record_with_empty_required_field(),
        ]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            validator.process_file(input_path, output_path, error_path)

            assert os.path.exists(error_path)
            with open(error_path, "r") as f:
                error_lines = f.readlines()
            # At least 2 error entries (one per invalid line)
            assert len(error_lines) >= 2
            # Check format
            assert error_lines[0].startswith("LINE:")
            assert "ERROR:" in error_lines[0]
        finally:
            os.unlink(input_path)


class TestStreamingValidatorLengthCheck:
    """Test the 177-character length validation."""

    def test_short_record_rejected(self):
        lines = [build_short_record()]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.invalid_records == 1
            assert result.invalid_length_lines == 1
            assert result.valid_records == 0
        finally:
            os.unlink(input_path)

    def test_long_record_rejected(self):
        lines = [build_long_record()]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.invalid_records == 1
            assert result.invalid_length_lines == 1
        finally:
            os.unlink(input_path)


class TestStreamingValidatorNonCreditSkip:
    """Ensure non-credit lines are skipped without being counted as errors."""

    def test_non_credit_lines_skipped(self):
        lines = [build_non_credit_record() for _ in range(5)]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 5
            assert result.skipped_lines == 5
            assert result.valid_records == 0
            assert result.invalid_records == 0
        finally:
            os.unlink(input_path)


class TestStreamingValidatorEmptyFile:
    """Test handling of empty input files."""

    def test_empty_file(self):
        input_path = create_test_file([])
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 0
            assert result.valid_records == 0
            assert result.invalid_records == 0
        finally:
            os.unlink(input_path)


class TestStreamingValidatorResilience:
    """One bad record must not stop processing of subsequent records."""

    def test_bad_record_does_not_stop_processing(self):
        lines = [
            build_valid_record(),
            build_short_record(),           # bad
            build_valid_record(),
            build_long_record(),            # bad
            build_valid_record(),
            build_record_with_invalid_numeric(),  # bad
            build_valid_record(),
        ]
        input_path = create_test_file(lines)
        output_path, error_path = create_output_paths()

        try:
            validator = StreamingValidator()
            result = validator.process_file(input_path, output_path, error_path)

            assert result.total_lines == 7
            assert result.valid_records == 4
            assert result.invalid_records == 3
        finally:
            os.unlink(input_path)
