# Veros Web

Next.js frontend for Veros, the OpenReview paper scoring and review distillation app.

## Stack

- Next.js `16.2.4` App Router
- React `19.2.4`
- TypeScript 5
- Tailwind CSS v4 tokens in `src/app/globals.css`
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

The frontend does not connect to Postgres directly. It reads papers, search
results, rankings, stats, and saved-paper state through the API. There is no
browser-loaded paper corpus or bundled mock fallback.

To refresh ingested papers with the team, point the FastAPI backend's
`api/.env` `DATABASE_URL` at the shared pgvector Postgres database, run
`make db-migrate` from the repo root, then use the API-backed pages normally.

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

This bulk-uploads papers and reviews, skips existing papers by default, and does
not compute scores unless you pass `--score`.

## Routes

| Route | Purpose |
|---|---|
| `/` | Landing page with OpenReview search input and live stats |
| `/search?q=` | API-backed results grid |
| `/papers/[id]` | Paper detail page with pending/failed/ready states |
| `/saved` | API-backed saved reading list |

## Source Map

| Path | Role |
|---|---|
| `src/app/layout.tsx` | Root layout, fonts, toaster |
| `src/app/page.tsx` | Landing page |
| `src/app/search/page.tsx` | Search shell backed by `/search/page` |
| `src/app/papers/[id]/page.tsx` | Paper detail route |
| `src/app/saved/page.tsx` | Saved papers page |
| `src/lib/api.ts` | Fetch functions and Zod DTO schemas |
| `src/lib/adapt.ts` | API DTO to frontend `Paper` adapter; null/default handling lives here |
| `src/lib/types.ts` | Frontend domain types |
| `src/components/paper/PaperPending.tsx` | Client polling while ingest/analysis is running |
| `src/components/paper/PaperView.tsx` | Shared paper render tree |

## Development Notes

- `params` and `searchParams` are Promises in this Next version; await them in server pages.
- API contract changes should start in `src/lib/api.ts`, then flow through `src/lib/adapt.ts`.
- Components should receive adapted `Paper` values rather than raw DTOs.
- `aiReady` controls pending states for dimension tiles and the TL;DR/insight UI.
- Fonts are loaded in `src/app/layout.tsx`: Newsreader, Inter, and IBM Plex Mono.

## Commands

```bash
pnpm dev
pnpm build
pnpm lint
pnpm start
```
