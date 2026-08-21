"""
Tests for PII Masking Utilities.
"""

import pytest
from app.utils.masking import (
    mask_aadhaar,
    mask_account_number,
    mask_log_message,
    mask_record_dict,
)


class TestPIIMasking:
    def test_mask_aadhaar_15_digits(self):
        raw = "123456789012345"
        masked = mask_aadhaar(raw)
        assert masked == "***********2345"
        assert len(masked) == 15
        assert masked.endswith("2345")

    def test_mask_aadhaar_12_digits(self):
        raw = "123456789012"
        masked = mask_aadhaar(raw)
        assert masked == "********9012"

    def test_mask_account_number(self):
        raw = "12345678901234567890"
        masked = mask_account_number(raw)
        assert masked == "****************7890"
        assert masked.endswith("7890")

    def test_mask_record_dict(self):
        record = {
            "apbs_transaction_code": "77",
            "beneficiary_aadhaar_number": "123456789012345",
            "destination_bank_account_number": "98765432109876543210",
            "beneficiary_name": "ROHIT KUMAR",
        }
        masked = mask_record_dict(record)
        assert masked["beneficiary_aadhaar_number"] == "***********2345"
        assert masked["destination_bank_account_number"] == "****************3210"
        assert masked["beneficiary_name"] == "ROHIT KUMAR"

    def test_mask_log_message(self):
        raw_msg = "Failed processing record with Aadhaar 123456789012345 and Account 9876543210987654"
        safe_msg = mask_log_message(raw_msg)
        assert "123456789012345" not in safe_msg
        assert "9876543210987654" not in safe_msg
        assert "2345" in safe_msg
        assert "7654" in safe_msg
