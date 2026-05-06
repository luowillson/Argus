# Migration runbook: Supabase → self-hosted Postgres on GCP

This is a step-by-step walkthrough for moving the shared database off
Supabase's 500 MB free tier onto a self-hosted Postgres server running on a
free Google Cloud VM. It assumes you've never set up a cloud VM before.

**Time estimate:** 1.5–2.5 hours total, broken into independent stages you
can pause between.

**Cost:** $0 if you stay within the GCP Always Free quotas described below.
The Google Developer Program credits ($10/month) are a safety net, not the
primary funding.

---

## Big picture

You'll do these things in order:

1. Create a Google Cloud account/project and a free VM (a small Linux server
   running in Google's data centers)
2. Set up Tailscale (a private network so only your team can reach the VM)
3. Install PostgreSQL on the VM
4. Copy the data from Supabase to the VM
5. Set up nightly backups
6. Tell your teammates how to point their app at the new database

Each section ends with a "✅ How to know this worked" check. If any check
fails, stop and fix it before moving on.

---

## Prerequisites

You need:
- A Google account (the one with Google AI Pro / Developer Program credits)
- A credit card (Google holds it on file but won't charge unless you
  exceed free quotas — we'll set a cap to prevent that)
- The current **Supabase database URL**. Get it from
  <https://supabase.com/dashboard> → your project → **Project Settings** (gear
  icon, bottom-left) → **Database** → **Connection string** → **URI** tab.
  Copy the value; it looks like
  `postgresql://postgres:PASSWORD@db.xxx.supabase.co:5432/postgres`. **Save
  this somewhere safe — you'll need it later.**
- A password manager or note app to store credentials (you'll generate a few)

You do **not** need:
- The `gcloud` CLI installed locally — we'll use the browser-based SSH
- The `pg_dump` tool installed locally — we'll run it from the VM

---

## Part 1 — Create the GCP VM

### 1.1 Sign in to Google Cloud

1. Open <https://console.cloud.google.com/> in your browser.
2. Sign in with the Google account that has the Developer Program credits.
3. If this is your first time, Google will ask you to accept the Terms of
   Service and pick a country. Accept and continue.
4. If prompted to **start a free trial**, you can — it adds $300 in extra
   credits valid for 90 days. Optional. The Always Free quotas we use don't
   require it.

### 1.2 Create a project

A "project" is GCP's unit of organization — every resource (VM, bucket,
firewall rule) lives inside one project.

1. At the top of the page, click the project picker (it shows the current
   project name, or says "Select a project" if you have none).
2. In the dialog that opens, click **NEW PROJECT** (top-right).
3. **Project name**: `argus-db` (or whatever you want).
4. **Organization**: leave as "No organization" if that's the only option.
5. Click **CREATE**. Wait ~10 seconds for it to provision.
6. When the bell icon shows a green check, click the project picker again
   and select `argus-db`. The header should now show that project name.

### 1.3 Set a billing budget cap

This is the single most important step for not getting surprise charges.

1. In the search bar at the top, type **Billing** and click the result.
2. If asked to link a billing account, do so. If you don't have one, click
   **MANAGE BILLING ACCOUNTS** → **CREATE ACCOUNT** and follow the prompts to
   add a credit card. (Google will hold $0 or $1 to verify; not a charge.)
3. Once linked, in the left sidebar click **Budgets & alerts**.
4. Click **CREATE BUDGET** at the top.
5. **Name**: `argus-db cap`
6. **Time range**: Monthly
7. **Projects**: select `argus-db`
8. **Services**: leave "All services"
9. Click **NEXT**.
10. **Target amount**: `5` (USD). This is your hard alert threshold — well
    below the $10 in monthly credits.
11. **Threshold rules**: leave the defaults (50%, 90%, 100%).
12. Check **Email alerts to billing admins and users**.
13. Click **FINISH**.

✅ **How to know this worked:** the Budgets page lists `argus-db cap` with
amount $5.

### 1.4 Enable the Compute Engine API

Most GCP services have to be "enabled" on a project before you can use them.

1. In the search bar, type **Compute Engine API** and click the result.
2. Click the blue **ENABLE** button. Wait ~30 seconds.

✅ **How to know this worked:** the page now says "API Enabled" and shows a
**MANAGE** button instead of **ENABLE**.

### 1.5 Create the VM

1. In the search bar, type **VM instances** and click the result (under
   Compute Engine).
2. Click **CREATE INSTANCE** at the top.
3. Fill in the form **carefully** — these settings are what keep it free:

   | Field | Value | Why |
   |---|---|---|
   | **Name** | `argus-db-vm` | |
   | **Region** | `us-central1 (Iowa)` | Always Free regions: us-central1, us-west1, us-east1 (NOT us-east4 or northern Virginia) |
   | **Zone** | `us-central1-a` | any of the a/b/c zones is fine |
   | **Machine configuration** → **Series** | `E2` | |
   | **Machine type** | `e2-micro` (under "Shared-core") | This is the Always Free machine |

4. Scroll to **Boot disk**, click **CHANGE**:
   - **Operating system**: Ubuntu
   - **Version**: Ubuntu 24.04 LTS (x86/64, **not** ARM)
   - **Boot disk type**: `Standard persistent disk` (NOT SSD — SSD costs
     money)
   - **Size**: `30` GB
   - Click **SELECT**

5. Scroll down. Under **Firewall**, **leave both checkboxes unchecked**
   (Allow HTTP / HTTPS). We do not want public traffic.

6. Expand **Advanced options** → **Identity and API access**. Under
   **Access scopes**, select **"Allow full access to all Cloud APIs"**.
   This lets the VM upload backups to Cloud Storage later. Skipping this
   step means Step 5 (backups) will fail with a 403, and fixing it
   requires stopping and restarting the VM.

7. Click **CREATE** at the bottom. Wait ~30 seconds for the green check
   next to your VM name.

✅ **How to know this worked:** in **VM instances**, `argus-db-vm` shows a
green check, with an "External IP" assigned (we won't use it, but its
presence means the VM is up).

### 1.6 SSH into the VM

1. On the **VM instances** page, find `argus-db-vm`.
2. In its row, under the **Connect** column, click **SSH**.
3. A new browser window pops open with a black terminal — this is a Linux
   shell running on the VM.
4. Run `whoami` to confirm. You should see your Google username.

✅ **How to know this worked:** you have a working terminal in the browser.
Keep this tab open — we'll use it for all the VM commands below.

> **Tip:** if the SSH window dies due to inactivity, just click the SSH
> button again. A new window opens with a fresh shell.

---

## Part 2 — Set up Tailscale

Tailscale gives you a private network where only your devices can talk to
each other. The VM's Postgres will be reachable only on this private
network — never on the public internet.

### 2.1 Create a Tailscale account

1. Open <https://login.tailscale.com/start> in a new browser tab.
2. Click **Sign in with Google** (use your same Google account, or a
   different one — it doesn't have to match GCP).
3. After signing in, you land on the Tailscale admin console. The URL is
   roughly `https://login.tailscale.com/admin/machines`.

✅ **How to know this worked:** you're on the admin console showing an
empty "Machines" list.

### 2.2 Install Tailscale on the VM

In the SSH terminal (the browser tab from step 1.6), run:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

The second command prints a long URL like
`https://login.tailscale.com/a/abcd1234`. **Copy that URL into a new browser
tab** and click **Connect**. This authenticates the VM with your Tailscale
account.

Back in the SSH terminal, the command should return to the prompt within a
few seconds.

Run:

```bash
tailscale ip -4
```

This prints the VM's Tailscale IP, something like `100.64.12.34`. **Copy
this IP somewhere safe** — your teammates will need it. This is the only
address you should ever use to connect to Postgres.

✅ **How to know this worked:** in the Tailscale admin console
(<https://login.tailscale.com/admin/machines>), you see `argus-db-vm`
listed with the same `100.x.y.z` IP.

### 2.3 Install Tailscale on your Mac (the migrator's machine)

You need Tailscale on your laptop to be able to reach the VM later for
testing.

1. Go to <https://tailscale.com/download/macos>.
2. Click **Download Tailscale**, open the `.pkg` file, follow the installer.
3. After install, click the Tailscale icon in your menu bar → **Log in**.
4. Sign in with the same Google account you used in step 2.1.

✅ **How to know this worked:** in your Mac terminal, run:

```bash
tailscale ip -4
```

This prints your Mac's `100.x.y.z` address. Then run:

```bash
ping <vm-tailscale-ip>
```

(replace with the VM's IP from step 2.2). You should see ping replies
within a few hundred milliseconds. Press `Ctrl+C` to stop.

If pings fail: in the Tailscale menu bar icon, make sure the toggle is
**On**. Both your Mac and the VM should show as connected in the admin
console.

### 2.4 Invite teammates to the tailnet

You can do this now or later. Free Tailscale supports up to 3 users.

1. In the admin console, click **Users** in the left sidebar.
2. Click **Invite users**.
3. Enter each teammate's email and click send.
4. They receive an email, click the link, sign in with Google, and install
   Tailscale on their machine (same as 2.3).

Once they're on the tailnet, their machine can reach the VM at the same
`100.x.y.z` IP.

---

## Part 3 — Install PostgreSQL on the VM

All commands in this part run in the VM's SSH terminal.

### 3.1 Install Postgres 16 + extensions

```bash
sudo apt update
sudo apt install -y postgresql-16 postgresql-16-pgvector postgresql-contrib
```

This installs:
- PostgreSQL 16 (the database engine)
- `pgvector` (for embedding similarity search)
- `pg_trgm` (for fuzzy text search — comes with `postgresql-contrib`)

The install takes 1–2 minutes.

✅ **How to know this worked:**

```bash
sudo systemctl status postgresql
```

You should see `Active: active (exited)`. Press `q` to exit the status view.

```bash
sudo -u postgres psql -c "SELECT version();"
```

Should print something like `PostgreSQL 16.x ...`.

### 3.2 Generate a strong database password

In the VM terminal:

```bash
openssl rand -base64 32
```

This prints a random 32-byte password like `pK3jR/2tN+...=`. **Copy this and
save it in your password manager** — this is the password for the `veros`
database user. You'll give it to teammates later.

> **Important:** the URL-encoded form of the password matters when it ends
> up in a `DATABASE_URL`. Avoid passwords with `@`, `:`, `/`, `?`, or `#`
> or you'll need to URL-encode them. The `openssl rand -base64` output can
> contain `+` and `/` — if it does, regenerate until you get one without
> them, or just use:
>
> ```bash
> openssl rand -hex 24
> ```
>
> which produces only `[0-9a-f]` characters and is always URL-safe.

### 3.3 Create the database and user

Replace `YOUR_GENERATED_PASSWORD` below with what you generated in 3.2.

```bash
sudo -u postgres psql <<EOF
CREATE USER veros WITH PASSWORD 'YOUR_GENERATED_PASSWORD';
CREATE DATABASE veros OWNER veros;
\c veros
CREATE EXTENSION vector;
CREATE EXTENSION pg_trgm;
EOF
```

✅ **How to know this worked:**

```bash
sudo -u postgres psql -d veros -c "\dx"
```

The output table should list `vector` and `pg_trgm` (along with the default
`plpgsql`).

### 3.4 Configure Postgres to listen on Tailscale only

We need Postgres to accept connections from the Tailscale network.

```bash
sudo nano /etc/postgresql/16/main/postgresql.conf
```

This opens the config in the `nano` editor. Use **Ctrl+W** to search.

1. Press **Ctrl+W**, type `listen_addresses`, press **Enter**.
2. Find the line that looks like `#listen_addresses = 'localhost'`. Change
   it to:
   ```
   listen_addresses = '*'
   ```
   (Remove the `#` at the front so it's no longer commented out.)

3. Press **Ctrl+W**, type `shared_buffers`, press **Enter**. Set:
   ```
   shared_buffers = 256MB
   ```

4. Use **Ctrl+W** to also find and set these (each on its own line — add
   them at the bottom of the file if they don't exist or are commented out,
   uncomment if they are):
   ```
   work_mem = 8MB
   maintenance_work_mem = 128MB
   effective_cache_size = 768MB
   ```

5. Press **Ctrl+O**, then **Enter**, to save. Press **Ctrl+X** to exit.

Now edit the access-control file:

```bash
sudo nano /etc/postgresql/16/main/pg_hba.conf
```

Scroll to the bottom (hold the down arrow). Add this line at the very end:

```
host    all             veros           100.64.0.0/10           scram-sha-256
```

The `100.64.0.0/10` range is what Tailscale uses for all device IPs.

Save and exit (Ctrl+O, Enter, Ctrl+X).

Restart Postgres so the changes take effect:

```bash
sudo systemctl restart postgresql
sudo systemctl status postgresql
```

Status should still show `active`. Press `q` to exit.

✅ **How to know this worked — test from your Mac terminal** (not the VM
terminal):

```bash
psql "postgresql://veros:YOUR_PASSWORD@<vm-tailscale-ip>:5432/veros" -c "SELECT 1;"
```

If you get back `?column? \n--- \n 1`, it worked. If you get "could not
connect", check:
- Tailscale is connected on your Mac (menu bar icon)
- You typed the right Tailscale IP
- The password matches what you set in 3.3
- You ran `sudo systemctl restart postgresql` after editing configs

> **No `psql` on your Mac?** Install it: `brew install libpq` then add it
> to PATH: `echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >>
> ~/.zshrc && source ~/.zshrc`. (Apple Silicon path; Intel Macs use
> `/usr/local/opt/libpq/bin`.)

---

## Part 4 — Migrate the data from Supabase

We'll do this from inside the VM so you don't need any database tools on
your Mac.

### 4.1 Save the Supabase connection string on the VM

In the VM SSH terminal:

```bash
export SUPABASE_URL="paste-your-supabase-uri-here"
```

(The full string from Prerequisites — `postgresql://postgres:...@db.xxx...`.)

> This variable only lives for the current shell session. That's fine — we
> only need it for the dump.

### 4.2 Dump the Supabase database

```bash
pg_dump --no-owner --no-privileges --format=custom \
  --file=/tmp/veros-supabase.dump "$SUPABASE_URL"
```

This connects to Supabase and writes a binary dump file to the VM's `/tmp`
directory. Expect it to take 1–10 minutes depending on data size. There
should be no errors. NOTICE lines are OK.

`--no-owner` and `--no-privileges` strip Supabase-specific permissions that
don't exist on your VM.

✅ **How to know this worked:**

```bash
ls -lh /tmp/veros-supabase.dump
```

Should show a file with a non-zero size (probably between 100 MB and 500
MB).

### 4.3 Restore the dump into the VM's Postgres

```bash
pg_restore --no-owner --no-privileges \
  --dbname="postgresql://veros:YOUR_PASSWORD@127.0.0.1:5432/veros" \
  /tmp/veros-supabase.dump
```

This replays the dump into the empty `veros` database. Takes 2–15 minutes.

You'll see NOTICE messages like `extension "vector" already exists, skipping`
— those are expected and safe.

If you see ERROR lines, stop and read them. Common causes:
- Wrong password → fix the URL
- pgvector or pg_trgm not installed → revisit step 3.1
- Disk full → unlikely with 30 GB but check `df -h /`

### 4.4 Verify the restore

Compare row counts between Supabase and the VM:

```bash
# row count in the VM
psql "postgresql://veros:YOUR_PASSWORD@127.0.0.1:5432/veros" \
  -c "SELECT 'papers' AS t, COUNT(*) FROM papers
      UNION ALL SELECT 'reviews', COUNT(*) FROM reviews
      UNION ALL SELECT 'paper_embeddings', COUNT(*) FROM paper_embeddings
      UNION ALL SELECT 'ai_insights', COUNT(*) FROM ai_insights;"

# row count in Supabase
psql "$SUPABASE_URL" \
  -c "SELECT 'papers' AS t, COUNT(*) FROM papers
      UNION ALL SELECT 'reviews', COUNT(*) FROM reviews
      UNION ALL SELECT 'paper_embeddings', COUNT(*) FROM paper_embeddings
      UNION ALL SELECT 'ai_insights', COUNT(*) FROM ai_insights;"
```

The two outputs must match exactly. If any row count differs, do not
proceed — either rerun the dump/restore or stop and investigate.

### 4.5 Confirm the Alembic migration state matches

This is what makes sure your app code's expected schema version matches
what's in the VM database.

On your Mac (not the VM), in the project directory:

```bash
cd /Users/jonathanxue/GitHub/Argus/api
DATABASE_URL="postgresql+psycopg://veros:YOUR_PASSWORD@<vm-tailscale-ip>:5432/veros" \
  uv run alembic current
```

Then run the same against Supabase:

```bash
DATABASE_URL="$SUPABASE_URL_AS_PSYCOPG" uv run alembic current
```

(Use the same Supabase URL but with `postgresql+psycopg://` instead of
`postgresql://` at the start.)

Both commands must print the same revision ID (something like
`b3ad8e7b8a1d (head)`).

---

## Part 5 — Set up nightly backups

We're now responsible for backups; Supabase did them automatically before.

### 5.1 Create a Cloud Storage bucket

1. In the GCP Console search bar, type **Buckets** and click the result
   (under Cloud Storage).
2. Click **CREATE** at the top.
3. **Name**: `argus-db-backups-<your-initials>` (bucket names must be
   globally unique across all of GCP, so pick something distinctive).
4. **Location type**: `Region`. **Region**: `us-central1` (same as the VM,
   to stay in Always Free egress quota).
5. **Storage class**: `Standard`.
6. **Access control**: leave defaults (Uniform, prevent public access).
7. Click **CREATE**.
8. If prompted "This bucket will be public", say no and confirm prevention
   of public access.

### 5.2 Set a 30-day deletion lifecycle rule

1. From the bucket's page, click **LIFECYCLE** in the top tabs.
2. Click **ADD A RULE**.
3. **Action**: Delete object.
4. **Condition**: **Age** = `30` days.
5. Click **CREATE**.

### 5.3 Give the VM permission to write to the bucket

1. In your bucket's page, click the **PERMISSIONS** tab.
2. Click **GRANT ACCESS**.
3. **New principals**: paste the VM's default service account. To find it:
   - Open a new tab to <https://console.cloud.google.com/iam-admin/serviceaccounts>
   - Make sure project `argus-db` is selected at the top.
   - Look for the one named "Compute Engine default service account".
   - Copy its email (looks like `123456789-compute@developer.gserviceaccount.com`).
4. Back in the bucket permissions: paste that email as the principal.
5. **Role**: `Storage Object Admin`.
6. Click **SAVE**.

### 5.4 Install gcloud CLI on the VM (for the `gsutil` command)

The `google-cloud-cli` package isn't in Ubuntu's default apt repos. Use
snap, which is preinstalled on Ubuntu 24.04 GCE images:

```bash
sudo snap install google-cloud-cli --classic
```

Test it:

```bash
gcloud storage ls
```

Should list your `argus-db-backups-*` bucket. If it complains about
authentication, run `gcloud auth application-default login` and follow
prompts (rare on a GCE VM — usually it just works because the VM uses its
service account automatically).

> **Why `gcloud storage` and not `gsutil`?** `gsutil` is the older Cloud
> Storage CLI; Google now recommends `gcloud storage` for new scripts. The
> two commands look almost identical (`cp`, `ls`, `mb`, `iam`, etc.), but
> `gsutil` has known quirks with cached credentials on GCE VMs that produce
> spurious "403 Provided scope(s) are not authorized" errors even when IAM
> and OAuth scopes are correct. Stick with `gcloud storage` to avoid that.

> **If snap is unavailable**, you can add Google's apt repo instead:
> ```bash
> echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
> curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
> sudo apt update && sudo apt install -y google-cloud-cli
> ```

### 5.5 Create the backup script

```bash
sudo nano /usr/local/bin/veros-backup.sh
```

Paste:

```bash
#!/bin/bash
set -euo pipefail

BUCKET="gs://argus-db-backups-YOUR-INITIALS"
DATE=$(date +%F)
LOCAL_DIR=/var/backups
LOCAL_FILE="$LOCAL_DIR/veros-$DATE.dump.gz"

mkdir -p "$LOCAL_DIR"

echo "[$(date -Is)] Starting pg_dump..."
sudo -u postgres pg_dump -Fc veros | gzip > "$LOCAL_FILE"
echo "[$(date -Is)] Dump complete: $(du -h "$LOCAL_FILE" | cut -f1)"

echo "[$(date -Is)] Uploading to $BUCKET..."
gcloud storage cp "$LOCAL_FILE" "$BUCKET/"
echo "[$(date -Is)] Upload complete."

echo "[$(date -Is)] Trimming local backups older than 7 days..."
find "$LOCAL_DIR" -name "veros-*.dump.gz" -mtime +7 -delete
echo "[$(date -Is)] Done."
```

Replace `YOUR-INITIALS` with whatever you used in 5.1. Save and exit (Ctrl+O,
Enter, Ctrl+X).

> **Heads up on e2-micro performance**: the first run takes 5–15 minutes for
> a ~500 MB database because the shared vCPU exhausts its burst credits and
> throttles to baseline. Subsequent runs are similar. This is fine for a
> nightly cron — it just feels slow when you watch it interactively.

Make it executable:

```bash
sudo chmod +x /usr/local/bin/veros-backup.sh
```

Test it once:

```bash
sudo /usr/local/bin/veros-backup.sh
```

✅ **How to know this worked:**

```bash
gsutil ls gs://argus-db-backups-YOUR-INITIALS/
```

Should list a `veros-YYYY-MM-DD.dump.gz` file.

### 5.6 Schedule it to run nightly

```bash
sudo crontab -e
```

If asked to choose an editor, pick `nano` (option 1).

Add this line at the bottom:

```
0 4 * * * /usr/local/bin/veros-backup.sh >> /var/log/veros-backup.log 2>&1
```

This runs the script every day at 04:00 UTC and logs output. Save and exit.

✅ **How to know this worked:**

```bash
sudo crontab -l
```

Should print the line you just added.

---

## Part 6 — Update your local app to use the new database

This is what makes your local dev environment hit the VM instead of
Supabase.

1. On your Mac, open `/Users/jonathanxue/GitHub/Argus/api/.env` in your
   editor.
2. Find the `DATABASE_URL=` line. Replace it with:
   ```
   DATABASE_URL=postgresql+psycopg://veros:YOUR_PASSWORD@<vm-tailscale-ip>:5432/veros
   ```
   No `?sslmode=require` — Tailscale handles encryption end-to-end.
3. Save the file. **Do not commit it** — `.env` files are in `.gitignore`.
4. Make sure Tailscale is running on your Mac (menu bar icon shows green).
5. Restart the API and worker:
   ```bash
   cd /Users/jonathanxue/GitHub/Argus/api
   uv run uvicorn app.main:app --reload
   ```
   In another terminal:
   ```bash
   cd /Users/jonathanxue/GitHub/Argus/api
   uv run celery -A app.workers.celery_app:celery_app worker --loglevel=info
   ```
6. Open the web app (`cd web && pnpm dev`, then visit
   <http://localhost:3000>). Load a paper page. Save a paper. Search for
   something. If it all works, you're migrated.

---

## Part 7 — Tell your teammates

Share over your private secrets channel (1Password, Signal, whatever you
use):

1. The VM's Tailscale IP (the `100.x.y.z` from step 2.2)
2. The `veros` database password (from step 3.2)
3. A Tailscale tailnet invite (sent from the admin console — step 2.4)

Tell them:

> Hey, we migrated the shared DB off Supabase. To use it:
>
> 1. Install Tailscale: <https://tailscale.com/download> — sign in with
>    your invited Google account.
> 2. Pull the `migrate/gcp-postgres` branch (or `main` once merged).
> 3. In `api/.env`, change `DATABASE_URL` to:
>    ```
>    postgresql+psycopg://veros:THE_PASSWORD@THE_TAILSCALE_IP:5432/veros
>    ```
> 4. Keep your existing `DEMO_USER_ID` / `DEMO_USER_EMAIL` so your saved
>    papers stay yours.
> 5. Restart the API and worker. Smoke test by loading a paper page.
>
> No code changes needed.

---

## Part 8 — After 1 week of stability

Once everyone has been on the new DB for ~1 week with no issues, **pause**
the Supabase project (don't delete) as a rollback safety net:

1. Go to <https://supabase.com/dashboard> → your project.
2. **Project Settings** → **General** → scroll to **Pause project**.
3. Click pause. The data stays for 90 days; you can restore anytime in that
   window.

After 90 days you can decide whether to delete it entirely.

---

## Rollback

If something goes wrong with the VM database mid-migration:

1. In your `api/.env`, switch `DATABASE_URL` back to the Supabase URL.
2. Restart your API + worker.
3. Tell teammates to do the same.

Your VM and its data are unaffected — you can fix the issue and try again.

---

## Troubleshooting

**`psql: connection refused` from Mac to VM Tailscale IP**
- Tailscale running on Mac? (menu bar icon)
- VM shows as connected in Tailscale admin console?
- Postgres restarted after editing configs? (`sudo systemctl restart postgresql`)
- `pg_hba.conf` line spelled exactly with `100.64.0.0/10`?

**`pg_dump: server version mismatch`**
- Supabase runs Postgres 15; your VM has 16. `pg_dump` 16 dumping from 15
  is fine. The other direction would fail.
- If you see this from a different `pg_dump` (like an old one on your Mac),
  use the VM's `pg_dump` — that's why we ran the dump from the VM.

**Disk full during restore**
- `df -h /` to check. With 30 GB and a typical Supabase free-tier dump (a
  few hundred MB), this shouldn't happen. If you see it, you may have used
  SSD by mistake (more expensive, smaller free quota) or another large
  process is consuming disk.

**VM looks unreachable hours after working**
- Ephemeral public IPs can change after a stop/start. The Tailscale IP is
  stable — always use it, never the public IP.
- If even Tailscale can't reach it, log in via the GCP Console SSH (browser
  SSH bypasses Tailscale).

**Backup script fails with "permission denied" on GCS**
- The VM's default service account doesn't have `Storage Object Admin` on
  the bucket. Re-do step 5.3.

**Backup upload fails with "403 Provided scope(s) are not authorized"**
- The VM's OAuth access scopes don't include Cloud Storage write. Stop
  the VM, edit it, set **Access scopes** → **"Allow full access to all
  Cloud APIs"**, restart. Tailscale IP stays the same so no `.env`
  changes are needed afterward.

**You need to start over from scratch**
- Delete the VM (`VM instances` → checkbox → DELETE) and start from 1.5.
  The bucket and project can stay.
