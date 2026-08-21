"""
Centralized application configuration using pydantic-settings.
Supports loading environment variables from .env files.
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    # ── Server Configuration ────────────────────────────────────────
    PORT: int = 8080
    HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # ── APBS Record Format ──────────────────────────────────────────
    APBS_RECORD_LENGTH: int = 177
    NON_CREDIT_TRANSACTION_CODES: List[str] = ["33"]

    # ── Batch Limits ────────────────────────────────────────────────
    MAX_FILES_PER_BATCH: int = 100
    MAX_BATCH_SIZE_GB: int = 3

    # ── Storage ─────────────────────────────────────────────────────
    STORAGE_BASE_DIR: Path = Path("storage")

    # ── Worker Pool (Celery + Redis) ────────────────────────────────
    WORKER_COUNT: int = 4
    CHUNK_SIZE: int = 8192  # streaming read buffer
    PROCESSING_BUFFER_SIZE: int = 5000  # record buffer for processing & formatting
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    CELERY_TASK_ALWAYS_EAGER: bool = False

    # ── Database & Bulk Importer (SQL: PostgreSQL, MySQL, SQLite) ──
    # Example PostgreSQL: postgresql://user:password@localhost:5432/apbs_db
    # Example MySQL:      mysql+pymysql://user:password@localhost:3306/apbs_db
    # Example SQLite:     sqlite:///./storage/apbs_database.db
    DATABASE_URL: str = "sqlite:///./storage/apbs_database.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    IMPORT_CHUNK_SIZE: int = 5000

    # ── Output ──────────────────────────────────────────────────────
    OUTPUT_DELIMITER: str = "|"

    # ── Security ────────────────────────────────────────────────────
    JWT_SECRET: str = "APBS_SUPER_SECRET_PRODUCTION_KEY_177_CHARS"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours
    RETENTION_DAYS_INPUT: int = 30

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )


# Singleton instance used throughout the application
settings = Settings()
