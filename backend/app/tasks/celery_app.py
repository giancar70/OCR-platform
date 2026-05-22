from celery import Celery
from celery.signals import worker_process_init

from app.config import settings


@worker_process_init.connect
def _init_worker(**_kwargs):
    from app.core.logging import setup_logging
    setup_logging()


celery_app = Celery(
    "ocr_worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.ocr"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={"app.tasks.ocr.process_document": {"queue": "ocr"}},
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)
