"""
Audit Trail Logging Service.

Records operational milestones (creation, verification, SQL import, download)
into the database logs table with masked log descriptions.
"""

from __future__ import annotations

from app.core.database import SessionLocal
from app.models.db_models import DBLog
from app.utils.masking import mask_log_message


def record_log(
    level: str,
    message: str,
    batch_id: Optional[str] = None,
    file_id: Optional[str] = None,
) -> None:
    """
    Safely record a structured log entry to the database across APPLICATION, BATCH, FILE, ERROR tiers.
    """
    try:
        db = SessionLocal()
        try:
            safe_message = mask_log_message(message)
            log_entry = DBLog(
                batch_id=batch_id,
                file_id=file_id,
                level=level.upper(),
                message=safe_message,
            )
            db.add(log_entry)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        print(f"[AUDIT LOG WARN] Could not write log: {e}")


def log_audit_event(
    action: str,
    batch_id: str,
    message: str,
    db: Session,
    file_id: Optional[str] = None,
    level: str = "INFO",
) -> DBLog:
    """
    Record an audit trail event with PII masking applied to the message.
    """
    safe_message = mask_log_message(f"[{action}] {message}")
    log_entry = DBLog(
        batch_id=batch_id,
        file_id=file_id,
        level=level,
        message=safe_message,
    )
    db.add(log_entry)
    db.commit()
    return log_entry

