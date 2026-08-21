"""
Celery Application instance configuration.
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "apbs_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.file_worker"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=settings.WORKER_COUNT,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
)
