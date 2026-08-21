"""
SQLAlchemy database setup and session management for SQL databases
(PostgreSQL, MySQL, SQLite, etc.).
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

db_url = settings.DATABASE_URL


def _ensure_database() -> None:
    """Ensure MySQL database exists before opening connection pool."""
    if db_url.startswith("mysql"):
        try:
            import pymysql
            u = make_url(db_url)
            db_name = u.database
            if db_name:
                conn = pymysql.connect(
                    host=u.host or "localhost",
                    user=u.username or "root",
                    password=u.password or "",
                    port=u.port or 3306,
                )
                try:
                    with conn.cursor() as cur:
                        cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name} CHARACTER SET utf8mb4;")
                    conn.commit()
                finally:
                    conn.close()
        except Exception as e:
            print(f"[DB INIT] Notice during auto database creation: {e}")


# SQLite specific directory creation & connection args
if db_url.startswith("sqlite"):
    path = db_url.replace("sqlite:///", "")
    if "/" in path or "\\" in path:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    _ensure_database()
    # PostgreSQL / MySQL / SQL Server connection with pooling
    engine = create_engine(
        db_url,
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,
        echo=False,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency for yielding database sessions in FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    _ensure_database()
    import app.models.db_models  # noqa: F401
    Base.metadata.create_all(bind=engine)
