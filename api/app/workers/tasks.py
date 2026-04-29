from __future__ import annotations

import logging
from types import SimpleNamespace

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
    from app.services.ingest_failures import (  # noqa: PLC0415
        clear_ingest_failure,
        get_ingest_failure,
        mark_ingest_failed,
    )

    logger.info("ingest_paper_task: starting forum=%r retry=%d", forum_id, self.request.retries)

    engine = get_engine()
    with Session(engine) as db:
        if get_ingest_failure(db, forum_id) is not None:
            logger.info(
                "ingest_paper_task: forum %r previously failed, skipping",
                forum_id,
            )
            return {"paper_id": forum_id, "status": "failed"}

        try:
            result = ingest_paper(db, forum_id)
        except Exception as exc:
            exc_str = str(exc)
            attempts = self.request.retries + 1
            # OpenReview 404 / NotFoundError is permanent — don't retry.
            if "NotFoundError" in exc_str or '"status": 404' in exc_str:
                mark_ingest_failed(db, forum_id, attempts=attempts, error=exc_str)
                logger.error(
                    "ingest_paper_task: forum %r not found on OpenReview, abandoning",
                    forum_id,
                )
                raise  # fail the task without scheduling retries
            if self.request.retries >= self.max_retries:
                mark_ingest_failed(db, forum_id, attempts=attempts, error=exc_str)
                logger.exception(
                    "ingest_paper_task exhausted retries for %s after %d attempts",
                    forum_id,
                    attempts,
                )
                raise
            logger.exception(
                "ingest_paper_task: unexpected error for forum=%r (retry %d/%d)",
                forum_id,
                self.request.retries,
                self.max_retries,
            )
            raise self.retry(exc=exc) from exc
        clear_ingest_failure(db, forum_id)

    logger.info(
        "ingest_paper_task: done forum=%r reviews=%s score=%s analyze=%s",
        forum_id,
        result.get("review_count"),
        result.get("score"),
        result.get("analyze_status"),
    )
    # Chain embedding step after successful ingest (best-effort; failures don't block).
    embed_paper_task.delay(forum_id)
    enrich_citations_task.delay(forum_id)
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


@celery_app.task(
    name="veros.enrich_citations",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
)
def enrich_citations_task(self, paper_id: str) -> dict[str, object]:  # type: ignore[override]
    from app.services.citations import enrich_paper_citations

    logger.info("enrich_citations_task: starting paper=%r retry=%d", paper_id, self.request.retries)

    engine = get_engine()
    with Session(engine) as db:
        try:
            result = enrich_paper_citations(db, paper_id)
        except Exception as exc:
            logger.exception(
                "enrich_citations_task: failed paper=%r (retry %d/%d)",
                paper_id,
                self.request.retries,
                self.max_retries,
            )
            raise self.retry(exc=exc) from exc

    logger.info(
        "enrich_citations_task: done paper=%r refs=%s provider=%s",
        paper_id,
        result.get("reference_count"),
        result.get("provider"),
    )
    return result


@celery_app.task(
    name="veros.enrich_learning_pathway",
    bind=True,
    max_retries=1,
    default_retry_delay=120,
)
def enrich_learning_pathway_task(self, pathway_id: str) -> dict[str, object]:  # type: ignore[override]
    from app.db.models import LearningPathway
    from app.services.ingest import ingest_paper
    from app.services.pathways import (
        find_openreview_candidates_for_stage,
        generate_pathway_from_paper,
        generate_pathway_from_topic,
        get_stage_items_for_enrichment,
    )

    engine = get_engine()
    discovered: list[str] = []
    ingested: list[str] = []
    with Session(engine) as db:
        pathway = db.get(LearningPathway, pathway_id)
        if pathway is None:
            logger.warning("enrich_learning_pathway_task: pathway %s not found", pathway_id)
            return {"pathway_id": pathway_id, "status": "missing"}

        pathway.status = "enriching"
        db.add(pathway)
        db.commit()

        stage_items = [
            item
            for item in get_stage_items_for_enrichment(db, pathway_id)
            if item.match_quality in {"weak", "missing"}
        ]
        existing_ids = {
            item.paper_id for item in get_stage_items_for_enrichment(db, pathway_id) if item.paper_id
        }

        for item in stage_items:
            candidates = find_openreview_candidates_for_stage(
                stage=SimpleNamespace(
                    stage=item.stage,
                    purpose=item.why_this_paper,
                    search_query=item.search_query or item.stage,
                    anchor_concepts=list(item.anchor_concepts or []),
                ),
                seed_label=pathway.query_text or pathway.title,
                exclude_ids=existing_ids.union(discovered),
                limit=3,
            )
            for forum_id in candidates:
                discovered.append(forum_id)
                try:
                    ingest_paper(db, forum_id)
                    ingested.append(forum_id)
                    existing_ids.add(forum_id)
                except Exception:
                    logger.exception(
                        "enrich_learning_pathway_task: ingest failed for discovered forum %s",
                        forum_id,
                    )
                    continue

        pathway = db.get(LearningPathway, pathway_id)
        assert pathway is not None
        pathway.status = "enriched"
        notes = dict(pathway.enrichment_notes or {})
        notes.update(
            {
                "discovered_forum_ids": discovered,
                "ingested_forum_ids": ingested,
            }
        )
        pathway.enrichment_notes = notes
        db.add(pathway)
        db.commit()

        if pathway.seed_paper_id:
            refreshed = generate_pathway_from_paper(
                db,
                paper_id=pathway.seed_paper_id,
                user_id=pathway.user_id,
                force=True,
                enqueue_enrichment=False,
            )
        else:
            refreshed = generate_pathway_from_topic(
                db,
                topic=pathway.query_text or "",
                user_id=pathway.user_id,
                force=True,
                enqueue_enrichment=False,
            )

    return {
        "pathway_id": pathway_id,
        "status": "completed",
        "discovered_count": len(discovered),
        "ingested_count": len(ingested),
        "refreshed_pathway_id": refreshed.id,
    }
