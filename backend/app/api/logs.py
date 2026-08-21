"""
API routes for System & Audit Logs.
Provides 4-tier log filtering (APPLICATION, BATCH, FILE, ERROR) and pagination.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.db_models import DBLog

router = APIRouter(prefix="/api/logs", tags=["logs"])


class LogItemSchema(BaseModel):
    id: int
    batch_id: Optional[str] = None
    file_id: Optional[str] = None
    level: str
    message: str
    timestamp: str

    model_config = {"from_attributes": True}


class PaginatedLogsResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    items: List[LogItemSchema]


@router.get("", response_model=PaginatedLogsResponse)
async def list_logs(
    batch_id: Optional[str] = Query(None, description="Filter by batch ID"),
    file_id: Optional[str] = Query(None, description="Filter by file name"),
    level: Optional[str] = Query(None, description="Log tier: APPLICATION, BATCH, FILE, ERROR, or INFO/WARN"),
    search: Optional[str] = Query(None, description="Search text in log message"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    db: Session = Depends(get_db),
):
    """
    Retrieve paginated audit and system logs with multi-tier filtering.
    """
    query = db.query(DBLog)

    if batch_id:
        query = query.filter(DBLog.batch_id == batch_id)

    if file_id:
        query = query.filter(DBLog.file_id == file_id)

    if level and level.upper() != "ALL":
        lvl = level.upper()
        if lvl == "APPLICATION":
            query = query.filter((DBLog.batch_id == None) | (DBLog.level == "APPLICATION"))
        elif lvl == "BATCH":
            query = query.filter(DBLog.batch_id != None, DBLog.file_id == None)
        elif lvl == "FILE":
            query = query.filter(DBLog.file_id != None)
        elif lvl == "ERROR":
            query = query.filter(DBLog.level.in_(["ERROR", "CRITICAL", "FAILED"]))
        else:
            query = query.filter(DBLog.level == lvl)

    if search:
        search_term = f"%{search}%"
        query = query.filter(DBLog.message.ilike(search_term))

    total = query.count()
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size

    logs = query.order_by(desc(DBLog.timestamp)).offset(offset).limit(page_size).all()

    items = [
        LogItemSchema(
            id=log.id,
            batch_id=log.batch_id,
            file_id=log.file_id,
            level=log.level,
            message=log.message,
            timestamp=log.timestamp.isoformat() if log.timestamp else "",
        )
        for log in logs
    ]

    return PaginatedLogsResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
    )
