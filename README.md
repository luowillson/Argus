# Argus

Argus fetches OpenReview paper reviews, normalizes venue-specific scores, and
stores reusable score summaries for use by a future web backend.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## CLI Usage

Fetch full reviews:

```bash
python openreview_reviews.py <paper_id> --format markdown --output reviews.md
```

Search by paper title within a conference:

```bash
python openreview_reviews.py \
  --title "Optimal Mistake Bounds for Transductive Online Learning" \
  --conference "NeurIPS.cc/2025/Conference" \
  --scores-only
```

Add venue scoring scales:

```bash
python openreview_reviews.py \
  --add-score-scales NeurIPS.cc/2025/Conference \
  rating=6 quality=4 clarity=4 significance=4 originality=4
```

Backfill the local score cache from generated Markdown files:

```bash
python openreview_reviews.py --cache-parsed-scores reviews.md reviews2.md
```

Parse every accepted NeurIPS 2025 paper and its reviews into JSONL:

```bash
python scripts/parse_neurips_2025_accepted.py
```

The bulk parser sleeps `0.5` seconds between paper requests by default to reduce
rate-limit risk. For a more conservative run:

```bash
python scripts/parse_neurips_2025_accepted.py --delay 1.0
```

Test the bulk parser on a small sample first:

```bash
python scripts/parse_neurips_2025_accepted.py --limit 5
```

## Backend Integration

The reusable service API lives in `argus_openreview.service`:

```python
from argus_openreview.service import get_score_summary

payload = get_score_summary(
    title="Optimal Mistake Bounds for Transductive Online Learning",
    conference="NeurIPS.cc/2025/Conference",
    use_cache=True,
)
```

The returned payload is JSON-safe and can be sent directly from a Flask,
FastAPI, or other backend route to a frontend.