"""
SQLAlchemy ORM models for APBS system database.

Tables:
- batches
- files
- transactions (UNIQUE record_hash constraint)
- duplicates_log
- logs
"""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DBBatch(Base):
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_uuid = Column(String(64), unique=True, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="CREATED")
    total_files = Column(Integer, default=0)
    total_size = Column(BigInteger, default=0)
    total_records = Column(Integer, default=0)
    valid_records = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    duplicate_records = Column(Integer, default=0)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    files = relationship("DBFile", back_populates="batch", cascade="all, delete-orphan")


class DBFile(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    sanitized_filename = Column(String(255), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    size = Column(BigInteger, default=0)
    status = Column(String(32), nullable=False, default="UPLOADING")
    record_count = Column(Integer, default=0)
    valid_records = Column(Integer, default=0)
    invalid_records = Column(Integer, default=0)
    duplicate_records = Column(Integer, default=0)
    input_path = Column(String(512), default="")
    output_path = Column(String(512), default="")
    error_path = Column(String(512), default="")
    created_at = Column(DateTime, default=utc_now, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    batch = relationship("DBBatch", back_populates="files")


class DBTransaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_hash = Column(String(64), unique=True, nullable=False, index=True)
    batch_id = Column(String(64), nullable=False, index=True)
    file_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    # 17 APBS Fields
    apbs_transaction_code = Column(String(2), nullable=False)
    destination_bank_iin = Column(String(9), nullable=False)
    destination_account_type = Column(String(2), default="")
    ledger_folio_number = Column(String(3), default="")
    beneficiary_aadhaar_number = Column(String(15), nullable=False)
    beneficiary_name = Column(String(40), default="")
    sponsor_bank_iin = Column(String(9), nullable=False)
    user_number = Column(String(7), nullable=False)
    user_name_narration = Column(String(20), default="")
    user_credit_reference = Column(String(13), nullable=False)
    amount = Column(String(13), nullable=False)
    item_sequence_number = Column(String(10), nullable=False)
    checksum = Column(String(10), nullable=False)
    success_flag = Column(String(1), nullable=False)
    filler = Column(String(1), default="")
    reason_code = Column(String(2), nullable=False)
    destination_bank_account_number = Column(String(20), default="")


class DBDuplicateLog(Base):
    __tablename__ = "duplicates_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    record_hash = Column(String(64), nullable=False, index=True)
    attempted_batch_id = Column(String(64), nullable=False, index=True)
    attempted_file_id = Column(String(255), nullable=False)
    original_transaction_id = Column(Integer, nullable=True)
    reason = Column(String(255), default="EXACT_RECORD_DUPLICATE")
    detected_at = Column(DateTime, default=utc_now, nullable=False)


class DBLog(Base):
    __tablename__ = "logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), nullable=True, index=True)
    file_id = Column(String(255), nullable=True)
    level = Column(String(16), nullable=False, default="INFO")
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=utc_now, nullable=False)
