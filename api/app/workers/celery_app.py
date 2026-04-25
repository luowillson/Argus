import logging
import sys

from celery import Celery

from app.config import get_settings

logger = logging.getLogger(__name__)


def make_celery() -> Celery:
    settings = get_settings()
    app = Celery(
        "veros",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )
    if sys.platform == "darwin":
        # sentence-transformers / torch can abort inside Celery's prefork workers
        # on macOS. Using the solo pool avoids subprocess forking entirely.
        app.conf.worker_pool = "solo"
        app.conf.worker_concurrency = 1
        logger.info("Configured Celery worker pool=solo on macOS for ML task stability")
    return app


celery_app = make_celery()
