from celery import Celery

from app.config import get_settings


def make_celery() -> Celery:
    settings = get_settings()
    return Celery(
        "veros",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.workers.tasks"],
    )


celery_app = make_celery()
