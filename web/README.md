# Veros Web

Next.js frontend for Veros, the OpenReview paper scoring and review distillation app.

## Stack

- Next.js `16.2.4` App Router
- React `19.2.4`
- TypeScript 5
- Tailwind CSS v4 tokens in `src/app/globals.css`
- TanStack Query for client polling/mutations
- Zod schemas in `src/lib/api.ts`
- Radix Dialog/Tooltip and `sonner` toasts

## Run Locally

```bash
pnpm install
pnpm dev
```

The app runs at `http://localhost:3000`.

Set the API base URL in `.env.local`:

```text
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
```

The frontend does not connect to Postgres directly. It prefers a static
browser-loaded paper corpus for normal reads. Generate that corpus from the API
project before deploying or whenever the shared database changes:

```bash
cd ../api
uv run python scripts/export_static_corpus.py
```

This writes `web/public/data/papers.json`. The browser loads that file once and
performs search, sorting, saved-list hydration, and paper-detail lookup locally.
If the file is missing during local development or a deploy, the UI asks the API
for `GET /api/v1/corpus/papers`; the API bulk-generates the same payload and
caches it in process. Bundled demo papers are only the final fallback when both
the static file and API are unavailable.

To refresh ingested papers with the team, point the FastAPI backend's
`api/.env` `DATABASE_URL` at the shared pgvector Postgres database, run
`make db-migrate` from the repo root, then regenerate the static corpus.

To fetch a batch of papers from OpenReview, write a local JSONL file first:

```bash
cd ../api
uv run python scripts/fetch_openreview_venue_jsonl.py \
  --venue ICLR.cc/2025/Conference \
  --decision accepted \
  --limit 5 \
  --output ../data/iclr_2025_accepted_reviews.jsonl
```

Remove `--limit 5` for the full venue. The fetch step does not touch Postgres
and is resumable: rerun the same command and rows already in the JSONL file are
skipped. Then import the local file into Postgres:

```bash
uv run python scripts/import_openreview_jsonl.py \
  --source ../data/iclr_2025_accepted_reviews.jsonl
```

After importing, rerun `uv run python scripts/export_static_corpus.py` so the
web app's local search JSON includes the new papers.

## Routes

| Route | Purpose |
|---|---|
| `/` | Landing page with OpenReview search input and live stats |
| `/search?q=` | Results grid, searched and sorted in the browser |
| `/papers/[id]` | Paper detail page; local corpus first, API fallback for uncached papers |
| `/saved` | Browser-local saved reading list |

## Source Map

| Path | Role |
|---|---|
| `src/app/layout.tsx` | Root layout, providers, fonts, toaster |
| `src/app/page.tsx` | Landing page |
| `src/app/search/page.tsx` | Search shell with bundled fallback results |
| `src/app/papers/[id]/page.tsx` | Paper detail shell that hydrates from the local corpus |
| `src/app/saved/page.tsx` | Saved papers page |
| `src/lib/api.ts` | Fetch functions and Zod DTO schemas |
| `src/lib/adapt.ts` | API DTO to frontend `Paper` adapter; null/default handling lives here |
| `src/lib/localPapers.ts` | Static corpus loading, browser-side search, and sorting |
| `src/lib/types.ts` | Frontend domain types |
| `src/lib/mock-papers.ts` | Offline fallback data |
| `src/components/paper/PaperPending.tsx` | Client polling while ingest/analysis is running |
| `src/components/paper/PaperView.tsx` | Shared paper render tree |

## Development Notes

- `params` and `searchParams` are Promises in this Next version; await them in server pages.
- API contract changes should start in `src/lib/api.ts`, then flow through `src/lib/adapt.ts`.
- Components should receive adapted `Paper` values rather than raw DTOs.
- `aiReady` controls pending states for dimension tiles and the TL;DR/insight UI.
- The local corpus lives at `public/data/papers.json`; regenerate it after meaningful database imports or analysis changes.
- Fonts are loaded in `src/app/layout.tsx`: Newsreader, Inter, and IBM Plex Mono.

## Commands

```bash
pnpm dev
pnpm build
pnpm lint
pnpm start
```
