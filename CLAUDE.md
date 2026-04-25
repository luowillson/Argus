# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with this repository.

> For a full architecture and file-map reference, see **CODEBASE.md**.
> For the user-facing startup guide, see **README.md**.

---

## What this repo is

**Veros** — a full-stack web app that fetches OpenReview peer reviews, computes a deterministic Veros Score (0–10), and runs an LLM step to produce TL;DRs, read-vs-skim guidance, and reviewer quotes.

Stack: Next.js 15 (App Router, TypeScript, Tailwind v4) · FastAPI + SQLModel + Alembic · Postgres 16 + pgvector + pg_trgm · Redis + Celery · Gemini / Z.AI (OpenAI-compatible LLM interface) · sentence-transformers (SBERT).

---

## Critical gotchas — read before editing

### Never run Python commands from repo root
The repo root contains a stray `app.py` file from a different environment. Always `cd api` before running `uv run ...`, otherwise Python imports `app` from the wrong place.

```bash
# correct
cd api && uv run uvicorn app.main:app --reload

# wrong — will fail with "ModuleNotFoundError: No module named 'fastapi'"
uv run uvicorn app.main:app --reload
```

### SQLModel composite / custom primary keys
When a field uses `sa_column=Column(..., primary_key=True)`, do **not** also set `Field(primary_key=True)`. It causes a `RuntimeError`. See `db/models.py` for examples.

### Tailwind v4 — tokens live in CSS, not tailwind.config.ts
All color and font tokens are in `web/src/app/globals.css` inside an `@theme {}` block. There is no `tailwind.config.ts` for custom values. Use `--color-burgundy`, `--color-paper`, etc. as Tailwind utilities.

### Next.js 15 — params/searchParams are Promises
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

```bash
# 1. Infrastructure
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

`api/app/deps.py` `get_current_user()` always returns `CurrentUser(id="demo-user")`. All routers use `CurrentUserDep`. To add real auth, replace only this function.

---

## Legacy files (do not delete, do not wire into the app)

- `openreview_reviews.py` — standalone CLI, used as a reference for OpenReview API behavior
- `Designs/` — static JSX mockups, visual reference only. The HTMLs reference a missing `veros-shared.jsx` and will throw on open.
