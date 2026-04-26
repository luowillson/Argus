# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

> For a full architecture and file-map reference, see **CODEBASE.md**.
> For the user-facing startup guide, see **README.md**.

---

## What this repo is

**Veros** — a full-stack web app that fetches OpenReview peer reviews, computes a deterministic Veros Score (0–10), and runs an LLM step to produce TL;DRs, read-vs-skim guidance, and reviewer quotes.

Stack: Next.js 16.2 (App Router, React 19, TypeScript, Tailwind v4) · FastAPI + SQLModel + Alembic · Postgres 16 + pgvector + pg_trgm · Redis + Celery · Z.AI / Gemini (OpenAI-compatible LLM interface) · sentence-transformers (SBERT).

---

## Critical gotchas — read before editing

### Run API Python commands from `api/`
The FastAPI package and `pyproject.toml` live under `api/`. Run `uv run ...` commands from that directory so imports resolve against `api/app`.

```bash
# correct
cd api && uv run uvicorn app.main:app --reload

# wrong — no API project is configured at the repo root
uv run uvicorn app.main:app --reload
```

### SQLModel composite / custom primary keys
When a field uses `sa_column=Column(..., primary_key=True)`, do **not** also set `Field(primary_key=True)`. It causes a `RuntimeError`. See `db/models.py` for examples.

### Tailwind v4 — tokens live in CSS, not tailwind.config.ts
All color and font tokens are in `web/src/app/globals.css` inside an `@theme {}` block. There is no `tailwind.config.ts` for custom values. Use `--color-burgundy`, `--color-paper`, etc. as Tailwind utilities.

### Next.js 16 App Router — params/searchParams are Promises
```tsx
// correct
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
}
```

### Raw SQL required for pgvector
SQLModel's `exec()` doesn't understand the `<=>` cosine operator. Use:
```python
db.execute(sa_text("SELECT paper_id FROM paper_embeddings ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :n"), {"vec": vec_str, "n": limit})
```

### Celery tasks use late imports
Service functions are imported inside the task body (not at module level) to avoid circular imports. Don't move them to the top.

### LLM max_output_tokens must be ≥ 4000
Setting it lower (e.g. 1500) causes Gemini to truncate mid-JSON. Don't reduce it.

---

## Running everything locally

For normal team development, prefer the shared Postgres URL in `api/.env` so
ingested papers, scores, insights, and embeddings are visible to everyone. Keep
Redis local unless the team has explicitly provisioned a shared queue. Use a
personal `DEMO_USER_ID` / `DEMO_USER_EMAIL` so saved papers stay separate.

```bash
# 1. Infrastructure
# Shared DB mode: Redis only needs to be local.
docker compose up -d redis

# Isolated local DB mode:
docker compose up -d

# 2. API (hot-reload)
cd api
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 3. Celery worker (second terminal, also in api/)
uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info

# 4. Web (third terminal)
cd web && pnpm dev
```

Root helpers exist for the common commands: `make redis-up`, `make infra-up`,
`make db-migrate`, `make api-dev`, `make worker`, and `make web-dev`.

---

## Key files to know

| File | Role |
|---|---|
| `api/app/services/veros_score.py` | Pure formula: weights, sd, quality, consensus, acceptance, volume bonus |
| `api/app/services/scoring.py` | Loads DB rows → calls formula → upserts `veros_scores` |
| `api/app/services/ingest.py` | Orchestrates fetch → upsert → score → analyze |
| `api/app/services/analyze.py` | LLM call → JSON parse → validate → upsert `ai_insights` |
| `api/app/services/paper_view.py` | Assembles `PaperDetail` from Paper + VerosScore + AIInsight + Reviews |
| `api/app/services/search.py` | ILIKE union pgvector cosine, sorted by score |
| `api/app/services/llm/factory.py` | `make_llm_provider()` — reads `LLM_PROVIDER` env var |
| `api/app/services/llm/prompts.py` | `SYSTEM_PROMPT`, `build_user_prompt()` |
| `api/app/workers/tasks.py` | `ingest_paper_task`, `embed_paper_task` |
| `web/src/lib/api.ts` | All fetch functions + Zod schemas — single source of truth for API contract |
| `web/src/lib/adapt.ts` | `adaptPaperDetail()`, `adaptPaperOut()` — DTO → frontend `Paper` type |
| `web/src/components/paper/PaperView.tsx` | Shared render tree (used by server page + PaperPending client) |
| `web/src/components/paper/PaperPending.tsx` | Client polling component (polls /status, shows skeleton) |

---

## Auth stub

`api/app/deps.py` `get_current_user()` returns `CurrentUser` from `DEMO_USER_ID` and `DEMO_USER_EMAIL` settings, defaulting to `demo-user` / `demo@veros.local`. All routers use `CurrentUserDep`. To add real auth, replace only this function.

When using the shared database, set these env vars per developer so the
`saved_papers` table remains personal even though the paper cache is shared.

---

## Standalone/reference files

- `openreview_reviews.py` — standalone CLI for OpenReview review fetching and score summaries; not wired into the FastAPI app
- `scoring/` — reusable local scoring implementation used by the standalone OpenReview tooling
- `paper_scores.json`, `score_scales.json`, `data/` — local scoring caches/outputs
- `reviews2.md` — generated sample review export
- `Designs/` — static JSX mockups, visual reference only. The HTMLs reference a missing `veros-shared.jsx` and will throw on open.
