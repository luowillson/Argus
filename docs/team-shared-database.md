# Shared Supabase database (team setup)

Point **everyone** at the same Supabase Postgres for app data. **Local Docker Postgres is for optional experiments only**, not the main shared dataset.

## Checklist (each developer)

1. **Pull latest**
   ```bash
   git checkout main
   git pull
   ```

2. **`api/.env`** (copy from team lead; **never commit** `api/.env`):
   - `DATABASE_URL=postgresql+psycopg://...pooler.supabase.com:5432/postgres?sslmode=require`  
     Use the **Supabase connection string** (URL-encode special characters in the password).
   - `REDIS_URL=redis://localhost:6379/0`  
     Redis stays **local** for Celery.
   - `DEMO_USER_ID=<your-unique-name>`  
   - `DEMO_USER_EMAIL=<your-unique-name>@veros.local`  
     **Use a unique `DEMO_USER_ID` per person** or saved papers will collide.

3. **Start Redis only** (not full `infra-up` if you are not using local Postgres for data):
   ```bash
   make redis-up
   ```
   On Windows without `make`:
   ```bash
   docker compose up -d redis
   ```

4. **Migrations**
   ```bash
   make db-migrate
   ```
   Or from `api/`:
   ```bash
   cd api && uv run alembic upgrade head
   ```

5. **Run the app** (three terminals or equivalent):
   ```bash
   make api-dev
   make worker
   make web-dev
   ```

## Optional: local Postgres + merge to shared

If you have local data to preserve, ask the team for the `merge_db_to_shared.py` workflow (when present in the repo). Typical pattern:

- Start local Postgres: `docker compose up -d postgres`
- Run merge script with `--dry-run` first, then for real, with `--rewrite-saved-user-id` set to your `DEMO_USER_ID`.

## Team notes

- **`ai_insights` / `paper_embeddings`** may be empty on bulk imports; text search and scores can still work; backfill LLM/embedding jobs may be run separately.
- If the shared password is rotated, update **`DATABASE_URL`** only in each developer’s `api/.env` (not in git).
