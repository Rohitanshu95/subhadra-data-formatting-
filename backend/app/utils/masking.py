"""
PII Masking Layer for Aadhaar and Bank Account Protection.

Ensures sensitive personal identifiers are masked before display
in previews or output to logs.
"""

from __future__ import annotations

import re
from typing import Any, Dict


def mask_aadhaar(aadhaar: str) -> str:
    """
    Mask an Aadhaar number, revealing only the last 4 characters.

    Example:
        '123456789012345' -> '***********2345'
        '123456789012'    -> '********9012'
    """
    if not aadhaar:
        return aadhaar

    stripped = aadhaar.strip()
    if len(stripped) <= 4:
        return "*" * len(stripped)

    masked_prefix = "*" * (len(stripped) - 4)
    visible_suffix = stripped[-4:]
    return masked_prefix + visible_suffix


def mask_account_number(account_num: str) -> str:
    """
    Mask a bank account number, revealing only the last 4 characters.

    Example:
        '12345678901234567890' -> '****************7890'
    """
    if not account_num:
        return account_num

    stripped = account_num.strip()
    if len(stripped) <= 4:
        return "*" * len(stripped)

    masked_prefix = "*" * (len(stripped) - 4)
    visible_suffix = stripped[-4:]
    return masked_prefix + visible_suffix


def mask_record_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a shallow copy of a record dict with PII fields masked.
    """
    masked = dict(record)

    if "beneficiary_aadhaar_number" in masked:
        masked["beneficiary_aadhaar_number"] = mask_aadhaar(str(masked["beneficiary_aadhaar_number"]))

    if "destination_bank_account_number" in masked:
        masked["destination_bank_account_number"] = mask_account_number(str(masked["destination_bank_account_number"]))

    return masked


def mask_log_message(message: str) -> str:
    """
    Mask numeric patterns that look like 12-16 digit Aadhaar or account numbers.
    """
    # Replace 12 to 18 continuous digits with masked version
    return re.sub(
        r'\b\d{12,18}\b',
        lambda m: "*" * (len(m.group(0)) - 4) + m.group(0)[-4:],
        message
    )
