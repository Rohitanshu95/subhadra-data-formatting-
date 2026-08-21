"""
Shared test fixtures and helper utilities for APBS tests.

Provides functions to generate valid/invalid 177-character records
and to create temporary test files with known content.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
import pytest
from app.core.config import settings

# Isolate all tests to an isolated test SQLite DB so test runs never touch the production database
os.environ["DATABASE_URL"] = "sqlite:///:memory:"


def build_valid_record(
    transaction_code: str = "77",
    dest_bank_iin: str = "123456789",
    dest_account_type: str = "10",
    ledger_folio: str = "AB1",
    aadhaar: str = "123456789012345",
    beneficiary_name: str = "BENEFICIARY TEST",
    sponsor_bank_iin: str = "987654321",
    user_number: str = "USR0001",
    user_narration: str = "SALARY PAYMENT",
    user_credit_ref: str = "REF0000000001",
    amount_paise: str = "0000000150000",
    item_seq: str = "0000000001",
    checksum: str = "1234567890",
    success_flag: str = "1",
    filler: str = "0",
    reason_code: str = "00",
    dest_bank_account: str = "12345678901234567890",
) -> str:
    """
    Build a valid 177-character APBS record from individual field values.

    All fields are padded/truncated to their exact required widths.
    """
    fields = [
        (transaction_code, 2),
        (dest_bank_iin, 9),
        (dest_account_type, 2),
        (ledger_folio, 3),
        (aadhaar, 15),
        (beneficiary_name, 40),
        (sponsor_bank_iin, 9),
        (user_number, 7),
        (user_narration, 20),
        (user_credit_ref, 13),
        (amount_paise, 13),
        (item_seq, 10),
        (checksum, 10),
        (success_flag, 1),
        (filler, 1),
        (reason_code, 2),
        (dest_bank_account, 20),
    ]

    parts = []
    for value, width in fields:
        # Pad with spaces on the right, truncate to exact width
        parts.append(value.ljust(width)[:width])

    record = "".join(parts)
    assert len(record) == 177, f"Generated record is {len(record)} chars, expected 177"
    return record


def build_non_credit_record() -> str:
    """Build a 177-character header/trailer record with transaction code '33'."""
    return build_valid_record(transaction_code="33")


def build_short_record() -> str:
    """Build a record that is too short (100 chars)."""
    return "X" * 100


def build_long_record() -> str:
    """Build a record that is too long (200 chars)."""
    return "0" * 200


def build_record_with_invalid_numeric() -> str:
    """Build a 177-char record with non-numeric characters in the amount field."""
    return build_valid_record(amount_paise="NOTANUMBER123")


def build_record_with_empty_required_field() -> str:
    """Build a 177-char record with an empty required field (aadhaar)."""
    return build_valid_record(aadhaar="               ")  # 15 spaces


def create_test_file(lines: list[str], suffix: str = ".txt") -> str:
    """
    Write lines to a temporary file and return the path.

    Each line gets a trailing newline appended.
    The caller is responsible for cleanup.
    """
    fd, path = tempfile.mkstemp(suffix=suffix, prefix="apbs_test_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return path


def create_output_paths() -> tuple[str, str]:
    """Create temp file paths for output and error files. Returns (output_path, error_path)."""
    output_dir = tempfile.mkdtemp(prefix="apbs_out_")
    output_path = os.path.join(output_dir, "output.txt")
    error_path = os.path.join(output_dir, "errors.txt")
    return output_path, error_path
