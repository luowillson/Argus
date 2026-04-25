# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository overview

Argus is an early-stage exploration of a product (referred to in the design files as **Veros**) that surfaces and distills OpenReview peer reviews. The repo currently contains two unrelated tracks:

- `openreview_reviews.py` — a standalone CLI for fetching the official reviews of a single OpenReview paper.
- `Designs/` — static React mockups of the proposed product UI, served as plain HTML pages with in-browser Babel.

There is no shared build system, package manager, test suite, or linter wired up. README.md is intentionally empty.

## openreview_reviews.py

CLI that wraps `openreview-py` and prints reviews as JSON or Markdown.

```bash
python -m pip install openreview-py
python openreview_reviews.py "https://openreview.net/forum?id=<id>"
python openreview_reviews.py <forum_id> --format markdown --output reviews.md
python openreview_reviews.py <forum_id> --username you@example.com         # auth-gated venues
python openreview_reviews.py <forum_id> --api-version v1 --username ...    # legacy venues
```

Notes for editing:
- Supports both OpenReview API v2 (`api2.openreview.net`, default) and v1 (`api.openreview.net`). The two SDKs return different note shapes — v2 wraps content fields as `{"value": ...}`, which `normalize_content` flattens. Preserve that branch when changing field handling.
- "Official review" detection is heuristic: an invitation regex (`REVIEW_INVITATION_PATTERN`) **plus** a content-field fallback (`review/summary/strengths/weaknesses/rating`). Both paths exist because some venues use non-standard invitation names — don't drop one without checking real venues.
- `reviews.md` is gitignored as a generated output.

## Designs/

Three-screen mockups (Landing / Search / Paper) in two stylistic directions:

- `design-1.html` + `veros-academic2.jsx` → "Academic2" direction (serif, calm, arxiv-flavored).
- `design-2.html` + `veros-dashboard2.jsx` → "Dashboard2" direction.

How they run: open the `.html` file directly in a browser. React 18, ReactDOM, and `@babel/standalone` are loaded from unpkg, and the JSX files are loaded as `<script type="text/babel" src="...">` and compiled in the browser. No bundler.

Component-export convention: each JSX file attaches its screens to `window` (e.g. `window.LandingAcademic2`, `SearchAcademic2`, `PaperAcademic2`) so the preview shell in the HTML can switch between them via a tab bar. New screens must follow this `window.*` pattern to be picked up.

**Missing dependency:** Both HTMLs `<script src="veros-shared.jsx">` a shared file that is not committed. It is expected to define `VerosMark` and `VIcon` (referenced throughout the JSX). Opening the pages today will throw until that file is added or the references are inlined.

Because Babel-in-browser silently swallows compile errors into the console, verify visual changes by actually loading the page — not just by reading the diff.
