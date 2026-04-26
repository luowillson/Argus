import logging
import sys

from celery import Celery
from celery.signals import task_failure, task_prerun, task_success

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
    # prefork pool is unreliable on macOS and Windows with ML deps (torch/sentence-transformers).
    # solo pool runs tasks in the worker process directly — no subprocess forking.
    if sys.platform in ("darwin", "win32"):
        app.conf.worker_pool = "solo"
        app.conf.worker_concurrency = 1
        logger.info(
            "Configured Celery worker pool=solo on %s for ML task stability",
            sys.platform,
        )
    return app


celery_app = make_celery()


# ---------------------------------------------------------------------------
# Debug signal handlers — log every task start / success / failure so worker
# activity is visible even when --loglevel=info suppresses task internals.
# ---------------------------------------------------------------------------

@task_prerun.connect
def on_task_prerun(task_id: str, task, args, kwargs, **_kw) -> None:  # type: ignore[type-arg]
    logger.info(
        "[worker] STARTING task=%s id=%s args=%s",
        task.name,
        task_id,
        args,
    )


@task_success.connect
def on_task_success(sender, result, **_kw) -> None:  # type: ignore[type-arg]
    logger.info(
        "[worker] SUCCESS task=%s",
        sender.name,
    )


@task_failure.connect
def on_task_failure(task_id: str, exception, traceback, sender, **_kw) -> None:  # type: ignore[type-arg]
    logger.error(
        "[worker] FAILED task=%s id=%s error=%s: %s",
        sender.name,
        task_id,
        type(exception).__name__,
        exception,
    )
