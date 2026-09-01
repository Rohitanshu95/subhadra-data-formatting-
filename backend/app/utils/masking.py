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


def mask_apbs_record(raw_line: str) -> str:
    """
    Mask PII fields in a 177-character APBS record.

    PII Fields masked:
    - beneficiary_aadhaar_number (chars 16-31)
    - beneficiary_name (chars 31-71)
    - destination_bank_account_number (chars 157-177)

    Args:
        raw_line: The 177-character raw APBS record

    Returns:
        The same record with PII fields masked
    """
    if len(raw_line) < 177:
        # For incomplete records, just mask any digit patterns
        return mask_log_message(raw_line)

    # Convert to list for easier manipulation
    chars = list(raw_line)

    # Mask beneficiary_aadhaar_number (offset 16, width 15)
    # Extract, mask, and replace
    aadhaar_start, aadhaar_end = 16, 31
    aadhaar = ''.join(chars[aadhaar_start:aadhaar_end])
    masked_aadhaar = mask_aadhaar(aadhaar)
    for i, c in enumerate(masked_aadhaar):
        if i < len(chars) - aadhaar_start:
            chars[aadhaar_start + i] = c

    # Mask beneficiary_name (offset 31, width 40)
    # Replace with placeholder to protect full name
    name_start, name_end = 31, 71
    masked_name = "[BENEFICIARY_NAME_MASKED]".ljust(name_end - name_start)[:name_end - name_start]
    for i, c in enumerate(masked_name):
        if i < len(chars) - name_start:
            chars[name_start + i] = c

    # Mask destination_bank_account_number (offset 157, width 20)
    account_start, account_end = 157, 177
    account = ''.join(chars[account_start:account_end])
    masked_account = mask_account_number(account)
    for i, c in enumerate(masked_account):
        if i < len(chars) - account_start:
            chars[account_start + i] = c

    return ''.join(chars)
