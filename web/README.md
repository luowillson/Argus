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

The frontend does not connect to Postgres directly. To share ingested papers
with the team, point the FastAPI backend's `api/.env` `DATABASE_URL` at the
shared pgvector Postgres database, then run `make db-migrate` from the repo root.

## Routes

| Route | Purpose |
|---|---|
| `/` | Landing page with OpenReview search input and live stats |
| `/search?q=` | Results grid, sorted by Veros score |
| `/papers/[id]` | Paper detail page; queues ingest when the API returns `202` |
| `/saved` | Demo user's saved reading list |

## Source Map

| Path | Role |
|---|---|
| `src/app/layout.tsx` | Root layout, providers, fonts, toaster |
| `src/app/page.tsx` | Landing page |
| `src/app/search/page.tsx` | Server-rendered search results with API/mock fallback |
| `src/app/papers/[id]/page.tsx` | Paper detail page with queued-ingest handling |
| `src/app/saved/page.tsx` | Saved papers page |
| `src/lib/api.ts` | Fetch functions and Zod DTO schemas |
| `src/lib/adapt.ts` | API DTO to frontend `Paper` adapter; null/default handling lives here |
| `src/lib/types.ts` | Frontend domain types |
| `src/lib/mock-papers.ts` | Offline fallback data |
| `src/components/paper/PaperPending.tsx` | Client polling while ingest/analysis is running |
| `src/components/paper/PaperView.tsx` | Shared paper render tree |

## Development Notes

- `params` and `searchParams` are Promises in this Next version; await them in server pages.
- API contract changes should start in `src/lib/api.ts`, then flow through `src/lib/adapt.ts`.
- Components should receive adapted `Paper` values rather than raw DTOs.
- `aiReady` controls pending states for dimension tiles and the TL;DR/insight UI.
- Server pages fall back to `VEROS_PAPERS` when the API is unreachable, so the UI remains browseable during backend work.
- Fonts are loaded in `src/app/layout.tsx`: Newsreader, Inter, and IBM Plex Mono.

## Commands

```bash
pnpm dev
pnpm build
pnpm lint
pnpm start
```
