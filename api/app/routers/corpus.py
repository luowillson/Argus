from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.deps import DbSession
from app.db.session import get_engine
from app.services.static_corpus import (
    build_static_corpus_changes_payload,
    build_static_corpus_payload,
    get_static_corpus_version,
)

router = APIRouter(prefix="/corpus", tags=["corpus"])

_CACHE_TTL = timedelta(hours=6)
_VERSION_CACHE_TTL = timedelta(seconds=30)
_EVENT_CHECK_INTERVAL_SECONDS = 10
_cached_payload: dict[str, object] | None = None
_cached_at: datetime | None = None
_cached_version: dict[str, object] | None = None
_cached_version_at: datetime | None = None


def _get_cached_version(db: DbSession, now: datetime) -> dict[str, object]:
    global _cached_version, _cached_version_at

    if (
        _cached_version is not None
        and _cached_version_at is not None
        and now - _cached_version_at < _VERSION_CACHE_TTL
    ):
        return _cached_version

    _cached_version = get_static_corpus_version(db)
    _cached_version_at = now
    return _cached_version


@router.get("/version", response_model=dict)
def get_paper_corpus_version(db: DbSession) -> dict[str, object]:
    """Return a small fingerprint clients can poll before refreshing corpus data."""
    return _get_cached_version(db, datetime.now(UTC))


@router.get("/changes", response_model=dict)
def get_paper_corpus_changes(
    db: DbSession,
    since: datetime = Query(..., description="Last corpus cursor seen by the client."),
) -> dict[str, object]:
    """Return only papers that changed after the client's corpus cursor."""
    return build_static_corpus_changes_payload(db, since)


@router.get("/papers", response_model=dict)
def get_paper_corpus(db: DbSession) -> dict[str, object]:
    """Return the full display-ready paper corpus for client-side search.

    The first request after process start performs a bulk DB read. Subsequent
    requests reuse the in-process payload so normal users do not each trigger
    database reads.
    """
    global _cached_at, _cached_payload

    now = datetime.now(UTC)
    version = _get_cached_version(db, now)
    if (
        _cached_payload is not None
        and _cached_at is not None
        and now - _cached_at < _CACHE_TTL
        and _cached_payload.get("corpus_version") == version.get("corpus_version")
    ):
        return _cached_payload

    _cached_payload = build_static_corpus_payload(db)
    _cached_at = now
    return _cached_payload


@router.get("/events")
async def get_paper_corpus_events(request: Request) -> StreamingResponse:
    """Stream corpus-version changes so browsers do not need per-client polling."""

    async def event_stream():
        last_sent: str | None = None
        while not await request.is_disconnected():
            try:
                with Session(get_engine()) as db:
                    version = _get_cached_version(db, datetime.now(UTC))
                current = str(version.get("corpus_version", ""))
                if current and current != last_sent:
                    last_sent = current
                    yield (
                        "event: corpus-version\n"
                        f"data: {json.dumps(version, separators=(',', ':'))}\n\n"
                    )
            except Exception:
                yield "event: corpus-error\ndata: {}\n\n"

            await asyncio.sleep(_EVENT_CHECK_INTERVAL_SECONDS)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
