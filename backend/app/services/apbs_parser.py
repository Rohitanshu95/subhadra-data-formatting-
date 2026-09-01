"""
APBS 177-Character Fixed-Width Record Parser.

This is the single source of truth for the 17-field schema.
Every field's offset, width, type, and required flag is defined
in FIELD_SCHEMA — no ad-hoc substring() calls anywhere else.

Usage:
    from app.services.apbs_parser import parse_line, validate_fields, is_non_credit_line

    parsed = parse_line(raw_line)
    errors = validate_fields(parsed)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


# ── Field type constants ────────────────────────────────────────────
FIELD_TYPE_NUM = "NUM"
FIELD_TYPE_ALPNUM = "ALPNUM"


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """Immutable definition for a single field in the 177-char record."""

    index: int          # 1-based field number
    name: str           # human-readable field name
    offset: int         # 0-based start position
    width: int          # character width
    field_type: str     # NUM or ALPNUM
    required: bool      # whether the field is mandatory


# ── 17-Field Schema (offsets sum to 177) ────────────────────────────
# Offsets:  0+2=2, 2+9=11, 11+2=13, 13+3=16, 16+15=31, 31+40=71,
#          71+9=80, 80+7=87, 87+20=107, 107+13=120, 120+13=133,
#         133+10=143, 143+10=153, 153+1=154, 154+1=155, 155+2=157,
#         157+20=177  ✓

FIELD_SCHEMA: tuple[FieldDefinition, ...] = (
    FieldDefinition(1,  "apbs_transaction_code",       0,   2,  FIELD_TYPE_NUM,    True),
    FieldDefinition(2,  "destination_bank_iin",         2,   9,  FIELD_TYPE_ALPNUM, True),
    FieldDefinition(3,  "destination_account_type",     11,  2,  FIELD_TYPE_NUM,    False),
    FieldDefinition(4,  "ledger_folio_number",          13,  3,  FIELD_TYPE_ALPNUM, False),
    FieldDefinition(5,  "beneficiary_aadhaar_number",   16,  15, FIELD_TYPE_NUM,    True),
    FieldDefinition(6,  "beneficiary_name",             31,  40, FIELD_TYPE_ALPNUM, False),
    FieldDefinition(7,  "sponsor_bank_iin",             71,  9,  FIELD_TYPE_NUM,    True),
    FieldDefinition(8,  "user_number",                  80,  7,  FIELD_TYPE_ALPNUM, True),
    FieldDefinition(9,  "user_name_narration",          87,  20, FIELD_TYPE_ALPNUM, False),
    FieldDefinition(10, "user_credit_reference",        107, 13, FIELD_TYPE_ALPNUM, True),
    FieldDefinition(11, "amount",                       120, 13, FIELD_TYPE_NUM,    True),
    FieldDefinition(12, "item_sequence_number",         133, 10, FIELD_TYPE_NUM,    True),
    FieldDefinition(13, "checksum",                     143, 10, FIELD_TYPE_NUM,    True),
    FieldDefinition(14, "success_flag",                 153, 1,  FIELD_TYPE_NUM,    True),
    FieldDefinition(15, "filler",                       154, 1,  FIELD_TYPE_ALPNUM, False),
    FieldDefinition(16, "reason_code",                  155, 2,  FIELD_TYPE_NUM,    True),
    FieldDefinition(17, "destination_bank_account_number", 157, 20, FIELD_TYPE_ALPNUM, False),
)

# Pre-compute a name→definition lookup for convenience
FIELD_MAP: dict[str, FieldDefinition] = {f.name: f for f in FIELD_SCHEMA}

# Pre-compute the total expected width as a self-check
_TOTAL_WIDTH = sum(f.width for f in FIELD_SCHEMA)
assert _TOTAL_WIDTH == 177, f"Schema width {_TOTAL_WIDTH} != 177"


# ── Non-credit line detection ───────────────────────────────────────

def is_non_credit_line(line: str) -> bool:
    """
    Return True if the line is a header/trailer record that should
    be skipped (not treated as a parse error).

    Non-credit lines are identified by their transaction code (first 2 chars).
    Transaction code '33' indicates header/trailer records.
    """
    if len(line) < 2:
        return False
    transaction_code = line[:2].strip()
    return transaction_code in settings.NON_CREDIT_TRANSACTION_CODES


def is_heading_or_header_line(line: str, record_number: int = 1) -> bool:
    """
    Identify if a record is a heading/header row that should be skipped.

    In the 177-character fixed-width format with no newlines:
    - Record 1 (characters 1-177) is the heading row and must be skipped.
    - It typically has transaction code '33' or contains non-numeric data
      in numeric fields (e.g., field labels instead of values).

    Args:
        line: The record string (should be 177 characters).
        record_number: The 1-based record number (default 1 = heading row).

    Returns:
        True if this record is a heading row and should be skipped.
    """
    # Record 1 is always the heading row in fixed-width continuous format
    if record_number == 1:
        return True

    # Also check for transaction code '33' as secondary confirmation
    if len(line) >= 2:
        transaction_code = line[:2].strip()
        return transaction_code in settings.NON_CREDIT_TRANSACTION_CODES

    return False


# ── Line parser ─────────────────────────────────────────────────────

@dataclass
class ParsedRecord:
    """Container for a successfully parsed 177-char record."""

    fields: dict[str, str]         # field_name → raw string value
    raw_line: str                  # original 177-char line (preserved)

    def get(self, field_name: str, default: Optional[str] = None) -> Optional[str]:
        """Get a field value by name."""
        return self.fields.get(field_name, default)

    @property
    def transaction_code(self) -> str:
        return self.fields.get("apbs_transaction_code", "")

    @property
    def success_flag(self) -> str:
        return self.fields.get("success_flag", "")

    @property
    def amount_paise(self) -> int:
        """Return amount as integer paise. Returns 0 if not parseable."""
        raw = self.fields.get("amount", "0").strip()
        try:
            return int(raw)
        except ValueError:
            return 0

    @property
    def amount_rupees(self) -> float:
        """Return amount converted from paise to rupees."""
        return self.amount_paise / 100.0


def parse_line(line: str) -> ParsedRecord:
    """
    Parse a 177-character fixed-width line into a ParsedRecord.

    This function does NOT validate lengths or field types — it
    simply slices by offset/width.  Call validate_fields() on the
    result for full validation.

    Args:
        line: The raw 177-character string (whitespace-stripped of
              trailing newline, but not leading/trailing content).

    Returns:
        ParsedRecord with all 17 fields extracted.
    """
    fields: dict[str, str] = {}
    for field_def in FIELD_SCHEMA:
        start = field_def.offset
        end = start + field_def.width
        fields[field_def.name] = line[start:end]

    return ParsedRecord(fields=fields, raw_line=line)


# ── Field validation ────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ValidationError:
    """A single field-level validation failure."""

    field_name: str
    field_index: int
    error_type: str      # e.g. "REQUIRED_FIELD_EMPTY", "INVALID_NUMERIC"
    detail: str
    raw_value: str


def validate_fields(record: ParsedRecord) -> list[ValidationError]:
    """
    Validate every field in a ParsedRecord against the schema.

    Checks:
    - Required fields must not be blank/whitespace-only.
    - NUM fields must contain only digits (after stripping).
    - ALPNUM fields must contain only alphanumeric chars + spaces
      (after stripping).

    Returns:
        A list of ValidationError objects. Empty list = record is valid.
    """
    errors: list[ValidationError] = []

    for field_def in FIELD_SCHEMA:
        raw_value = record.fields.get(field_def.name, "")
        stripped = raw_value.strip()

        # ── Required check ──────────────────────────────────────
        if field_def.required and not stripped:
            errors.append(ValidationError(
                field_name=field_def.name,
                field_index=field_def.index,
                error_type="REQUIRED_FIELD_EMPTY",
                detail=f"Field '{field_def.name}' (#{field_def.index}) is required but empty",
                raw_value=raw_value,
            ))
            continue  # skip type check if empty

        # ── Type check (only if non-empty) ──────────────────────
        if stripped:
            if field_def.field_type == FIELD_TYPE_NUM:
                if not stripped.isdigit():
                    errors.append(ValidationError(
                        field_name=field_def.name,
                        field_index=field_def.index,
                        error_type="INVALID_NUMERIC",
                        detail=f"Field '{field_def.name}' (#{field_def.index}) must be numeric, got '{stripped}'",
                        raw_value=raw_value,
                    ))
            elif field_def.field_type == FIELD_TYPE_ALPNUM:
                # Allow alphanumeric + spaces + common punctuation in names
                # Common characters in Indian names: W/O (Wife Of), D/O (Daughter Of), S/O (Son Of)
                # Also allow: comma, apostrophe, parentheses, colon for common name patterns
                if not all(c.isalnum() or c in (" ", ".", "-", "/", "_", ",", "'", "(", ")", ":") for c in stripped):
                    errors.append(ValidationError(
                        field_name=field_def.name,
                        field_index=field_def.index,
                        error_type="INVALID_ALPHANUMERIC",
                        detail=f"Field '{field_def.name}' (#{field_def.index}) contains invalid characters: '{stripped}'",
                        raw_value=raw_value,
                    ))

    return errors
