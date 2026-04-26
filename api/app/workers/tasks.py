from __future__ import annotations

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session

from app.db.session import get_engine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="veros.ingest_paper",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def ingest_paper_task(self, forum_id: str) -> dict:  # type: ignore[override]
    # Late import avoids circular import (celery_app ← tasks ← services ← celery_app).
    from app.services.ingest import ingest_paper  # noqa: PLC0415

    logger.info("ingest_paper_task: starting forum=%r retry=%d", forum_id, self.request.retries)

    engine = get_engine()
    with Session(engine) as db:
        try:
            result = ingest_paper(db, forum_id)
        except Exception as exc:
            exc_str = str(exc)
            # OpenReview 404 / NotFoundError is permanent — don't retry.
            if "NotFoundError" in exc_str or '"status": 404' in exc_str:
                logger.error(
                    "ingest_paper_task: forum %r not found on OpenReview, abandoning",
                    forum_id,
                )
                raise  # fail the task without scheduling retries
            logger.exception(
                "ingest_paper_task: unexpected error for forum=%r (retry %d/%d)",
                forum_id,
                self.request.retries,
                self.max_retries,
            )
            raise self.retry(exc=exc) from exc

    logger.info(
        "ingest_paper_task: done forum=%r reviews=%s score=%s analyze=%s",
        forum_id,
        result.get("review_count"),
        result.get("score"),
        result.get("analyze_status"),
    )
    # Chain embedding step after successful ingest (best-effort; failures don't block).
    embed_paper_task.delay(forum_id)
    return result


@celery_app.task(
    name="veros.embed_paper",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def embed_paper_task(self, paper_id: str) -> None:  # type: ignore[override]
    from app.config import get_settings
    from app.db.models import AIInsight, Paper, PaperEmbedding
    from app.services.embeddings.factory import get_embedding_provider

    logger.info("embed_paper_task: starting paper=%r retry=%d", paper_id, self.request.retries)

    engine = get_engine()
    with Session(engine) as db:
        paper = db.get(Paper, paper_id)
        if paper is None:
            logger.warning("embed_paper_task: paper %r not found, skipping", paper_id)
            return

        insight = db.get(AIInsight, paper_id)
        # Prefer tldr (concise and informative); fall back to abstract.
        text = f"{paper.title}\n{insight.tldr if insight else paper.abstract or ''}"

        try:
            provider = get_embedding_provider()
            embedding = provider.encode([text])[0]
        except Exception as exc:
            logger.exception(
                "embed_paper_task: encoding failed paper=%r (retry %d/%d)",
                paper_id,
                self.request.retries,
                self.max_retries,
            )
            raise self.retry(exc=exc) from exc

        settings = get_settings()
        stmt = pg_insert(PaperEmbedding).values(
            paper_id=paper_id,
            embedding=embedding,
            source="title_tldr",
            model=settings.embedding_model,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[PaperEmbedding.__table__.c.paper_id],
            set_={
                "embedding": stmt.excluded.embedding,
                "source": stmt.excluded.source,
                "model": stmt.excluded.model,
            },
        )
        db.exec(stmt)
        db.commit()

    logger.info("embed_paper_task: done paper=%r", paper_id)
