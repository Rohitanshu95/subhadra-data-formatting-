"""
Tests for record-level hashing functionality.
"""

import hashlib
import pytest
from app.services.hash import compute_record_hash
from tests.conftest import build_valid_record


class TestRecordHash:
    def test_compute_record_hash_deterministic(self):
        line = build_valid_record(user_credit_ref="REF0000000001")
        hash1 = compute_record_hash(line)
        hash2 = compute_record_hash(line + "\n")
        hash3 = compute_record_hash(line + "\r\n")

        assert len(hash1) == 64
        assert hash1 == hash2 == hash3

    def test_different_records_produce_different_hashes(self):
        line1 = build_valid_record(user_credit_ref="REF0000000001")
        line2 = build_valid_record(user_credit_ref="REF0000000002")

        hash1 = compute_record_hash(line1)
        hash2 = compute_record_hash(line2)

        assert hash1 != hash2
