"""
Tests for the APBS 177-character fixed-width parser.

Covers:
- Schema width assertion (sums to 177)
- Valid record parsing — all 17 fields extracted correctly
- Non-credit line detection (transaction code '33')
- Field-level validation (required fields, numeric checks)
- Malformed inputs
"""

import pytest

from app.services.apbs_parser import (
    FIELD_SCHEMA,
    ParsedRecord,
    is_non_credit_line,
    parse_line,
    validate_fields,
)
from tests.conftest import (
    build_non_credit_record,
    build_record_with_empty_required_field,
    build_record_with_invalid_numeric,
    build_valid_record,
)


# ── Schema integrity ────────────────────────────────────────────────

class TestSchemaDefinition:
    """Verify the FIELD_SCHEMA itself is correct."""

    def test_total_width_is_177(self):
        total = sum(f.width for f in FIELD_SCHEMA)
        assert total == 177

    def test_field_count_is_17(self):
        assert len(FIELD_SCHEMA) == 17

    def test_offsets_are_contiguous(self):
        """Each field's offset should equal the previous field's offset + width."""
        for i in range(1, len(FIELD_SCHEMA)):
            prev = FIELD_SCHEMA[i - 1]
            curr = FIELD_SCHEMA[i]
            expected_offset = prev.offset + prev.width
            assert curr.offset == expected_offset, (
                f"Field {curr.name} offset={curr.offset}, "
                f"expected {expected_offset} (after {prev.name})"
            )

    def test_first_field_starts_at_zero(self):
        assert FIELD_SCHEMA[0].offset == 0

    def test_field_indices_are_sequential(self):
        for i, field_def in enumerate(FIELD_SCHEMA, start=1):
            assert field_def.index == i


# ── Non-credit line detection ───────────────────────────────────────

class TestNonCreditDetection:

    def test_header_trailer_line_detected(self):
        line = build_non_credit_record()
        assert is_non_credit_line(line) is True

    def test_credit_line_not_detected(self):
        line = build_valid_record(transaction_code="77")
        assert is_non_credit_line(line) is False

    def test_return_transaction_not_detected(self):
        line = build_valid_record(transaction_code="88")
        assert is_non_credit_line(line) is False

    def test_empty_line(self):
        assert is_non_credit_line("") is False

    def test_single_char_line(self):
        assert is_non_credit_line("3") is False


# ── Line parsing ────────────────────────────────────────────────────

class TestParseLine:

    def test_parse_valid_record_extracts_all_fields(self):
        line = build_valid_record()
        record = parse_line(line)

        assert isinstance(record, ParsedRecord)
        assert len(record.fields) == 17
        assert record.raw_line == line

    def test_transaction_code_extracted(self):
        line = build_valid_record(transaction_code="77")
        record = parse_line(line)
        assert record.fields["apbs_transaction_code"] == "77"

    def test_aadhaar_extracted(self):
        line = build_valid_record(aadhaar="123456789012345")
        record = parse_line(line)
        # Aadhaar field is 15 wide, value is exactly 15 chars
        assert record.fields["beneficiary_aadhaar_number"].strip() == "123456789012345"

    def test_beneficiary_name_extracted(self):
        line = build_valid_record(beneficiary_name="ROHIT KUMAR")
        record = parse_line(line)
        assert record.fields["beneficiary_name"].strip() == "ROHIT KUMAR"

    def test_amount_property(self):
        line = build_valid_record(amount_paise="0000000150000")
        record = parse_line(line)
        assert record.amount_paise == 150000
        assert record.amount_rupees == 1500.00

    def test_success_flag_property(self):
        line = build_valid_record(success_flag="1")
        record = parse_line(line)
        assert record.success_flag == "1"

    def test_all_fields_have_correct_width(self):
        """Every extracted field should have exactly the width defined in the schema."""
        line = build_valid_record()
        record = parse_line(line)
        for field_def in FIELD_SCHEMA:
            value = record.fields[field_def.name]
            assert len(value) == field_def.width, (
                f"Field {field_def.name}: expected width {field_def.width}, "
                f"got {len(value)} (value='{value}')"
            )


# ── Field validation ────────────────────────────────────────────────

class TestValidateFields:

    def test_valid_record_has_no_errors(self):
        line = build_valid_record()
        record = parse_line(line)
        errors = validate_fields(record)
        assert errors == []

    def test_empty_required_field_detected(self):
        line = build_record_with_empty_required_field()
        record = parse_line(line)
        errors = validate_fields(record)

        assert len(errors) >= 1
        error_types = [e.error_type for e in errors]
        assert "REQUIRED_FIELD_EMPTY" in error_types

        # Should flag aadhaar specifically
        aadhaar_errors = [e for e in errors if e.field_name == "beneficiary_aadhaar_number"]
        assert len(aadhaar_errors) == 1

    def test_invalid_numeric_field_detected(self):
        line = build_record_with_invalid_numeric()
        record = parse_line(line)
        errors = validate_fields(record)

        assert len(errors) >= 1
        error_types = [e.error_type for e in errors]
        assert "INVALID_NUMERIC" in error_types

    def test_returned_transaction_code_88_is_valid(self):
        """Transaction code 88 (returned) is still a valid credit line."""
        line = build_valid_record(transaction_code="88", success_flag="0", reason_code="01")
        record = parse_line(line)
        errors = validate_fields(record)
        assert errors == []

    def test_optional_empty_fields_pass_validation(self):
        """Optional fields that are blank should not generate errors."""
        line = build_valid_record(
            dest_account_type="  ",
            ledger_folio="   ",
            beneficiary_name=" " * 40,
            user_narration=" " * 20,
            dest_bank_account=" " * 20,
        )
        record = parse_line(line)
        errors = validate_fields(record)
        assert errors == []
