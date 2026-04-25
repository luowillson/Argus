# Veros

Veros surfaces and distills OpenReview peer reviews. Paste any OpenReview forum URL, get a deterministic **Veros Score (0–10)** plus AI-generated insights: a TL;DR, "read deeply" vs "skim or skip" sections, and verbatim reviewer voices.

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | any recent | [docker.com](https://www.docker.com/products/docker-desktop/) |
| Node.js + pnpm | Node 20+, pnpm 9+ | `npm i -g pnpm` |
| Python | 3.12–3.13 | via `uv` below |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

---

## Quick start

### 1. Start Postgres + Redis

```bash
docker compose up -d
```

Postgres is exposed on `localhost:5432`, Redis on `localhost:6379`. Data persists in a Docker volume (`pgdata`).

### 2. Set up the API

```bash
cd api
cp .env.example .env    # fill in API keys (see Environment variables below)
uv sync                 # create venv and install all Python deps
uv run alembic upgrade head   # create tables + pgvector/pg_trgm extensions
```

Start the API server (hot-reload):

```bash
uv run uvicorn app.main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

### 3. Start the Celery worker (background jobs)

Open a second terminal in `api/`:

```bash
uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

The worker handles ingest, LLM analysis, and embedding tasks triggered when you visit an unknown paper URL.

> On macOS, the worker is configured to use Celery's `solo` pool automatically.
> This avoids `SIGABRT` crashes from native ML dependencies such as
> `sentence-transformers` / `torch` inside prefork worker processes.

### 4. Start the web app

```bash
cd web
pnpm install
pnpm dev
# → http://localhost:3000
```

---

## Ingesting your first paper

The easiest way: visit a paper page directly using a real OpenReview forum ID. For example, this ICLR 2024 paper on sparse autoencoders:

```
http://localhost:3000/papers/F76bwRSLeK
```

If the paper isn't in the database the API returns 202, the Celery worker fetches reviews from OpenReview, scores the paper, runs LLM analysis, and the page transitions from skeleton → full view automatically (polls every 2 s).

> **Note:** the forum ID must be a real OpenReview paper ID. Fake IDs will fail immediately (OpenReview returns 404) — this is expected and the task won't retry.

**Using the search box:** paste any OpenReview forum URL or forum ID into the landing page search. If the paper is already indexed it appears in results; if not, go to `/papers/<id>` to trigger ingestion.

**Via curl (synchronous, no worker needed):**

```bash
curl -X POST http://localhost:8000/api/v1/papers/F76bwRSLeK/ingest
```

This runs ingest + score + LLM analysis inline in the request thread (~20–60 s depending on OpenReview and LLM latency).

---

## Environment variables (`api/.env`)

```
DATABASE_URL=postgresql+psycopg://veros:veros@localhost:5432/veros
REDIS_URL=redis://localhost:6379/0

# LLM provider — "gemini" (free tier) or "zai" (Z.AI pay-as-you-go)
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your key from aistudio.google.com>
GEMINI_MODEL=gemini-2.5-flash

# Z.AI (optional alternative)
ZAI_API_KEY=<your Z.AI key>
ZAI_BASE_URL=https://api.z.ai/api/paas/v4/
ZAI_MODEL=glm-5.1

# OpenReview credentials — only needed for auth-gated venues
OPENREVIEW_USERNAME=
OPENREVIEW_PASSWORD=

EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
```

`web/.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

---

## All API endpoints

Base: `http://localhost:8000/api/v1`

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check |
| GET | `/stats` | Paper + review counts (for landing page) |
| GET | `/search?q=&limit=&offset=` | Text + semantic search |
| GET | `/papers/{id}` | Full paper detail; 202 + enqueue if not ingested |
| GET | `/papers/{id}/status` | `{ingest, analysis}` status |
| POST | `/papers/{id}/ingest` | Synchronous ingest (no worker needed) |
| POST | `/papers/{id}/analyze` | Re-run LLM analysis |
| GET | `/saved` | Demo user's reading list |
| POST | `/saved` | Save a paper `{paper_id}` |
| DELETE | `/saved/{id}` | Unsave a paper |

Interactive docs at `http://localhost:8000/docs`.

---

## Switching LLM providers

Edit `api/.env`:

```
LLM_PROVIDER=gemini   # uses GEMINI_API_KEY + GEMINI_MODEL
LLM_PROVIDER=zai      # uses ZAI_API_KEY + ZAI_MODEL
```

Both use an OpenAI-compatible HTTP interface. Adding a new provider: implement one method in `api/app/services/llm/provider.py` and register it in `factory.py`.

---

## Pages

| URL | Description |
|---|---|
| `/` | Landing — search box + live stats |
| `/search?q=` | Results grid (Score / Grade / Paper / Venue / Metrics / Verdict) |
| `/papers/{id}` | Full paper view with score, dimensions, TL;DR, read/skim grid, reviewer voices |
| `/saved` | Reading list |

---

## Re-embedding already-ingested papers

After a fresh ingest the embedding task is queued automatically. To manually embed a paper that was ingested before the worker was running:

```bash
cd api
uv run celery -A app.workers.celery_app:celery_app call \
  veros.embed_paper --args='["F76bwRSLeK"]'
```
