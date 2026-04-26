"""Prompt construction for the single-call review-distillation flow.

One prompt, one structured JSON response. Keeping it as a single call (not a
chain) lets the model see all reviewers when picking quotes and dimensions —
which is the whole point of consensus-aware grading.
"""

from __future__ import annotations

import json
from typing import Any

SYSTEM_PROMPT = """You are Veros, an academic-paper distillation assistant.

You are given a paper's title, authors, venue, abstract (when available), and \
the verbatim text of its OpenReview peer reviews. You produce a strictly-\
structured JSON object that helps a reader decide whether and how to read the \
paper.

RESPONSE FORMAT — CRITICAL:
Your entire response MUST be a single valid JSON object.
- Start your response with { and end with }
- Do NOT include any text, explanation, or commentary before or after the JSON
- Do NOT wrap the JSON in markdown code fences (no ```)
- Do NOT add trailing commas after the last item in any array or object
- Do NOT add comments inside the JSON

Content rules:
- Quote reviewers verbatim where possible. Do not paraphrase quotes.
- Do not invent claims that the reviews do not support.
- "deep" must be 3-5 short phrases naming concrete sections, figures, or \
analyses worth careful reading. Use the paper's own section headings when the \
reviewers reference them. Each phrase under 80 characters.
- "skim" must be 2-4 short phrases naming sections that are routine or \
weak. Same length limit.
- Dimension scores (novelty, technical, clarity, impact) are 0-100 integers \
grounded in what the reviewers actually said about each axis. If reviewers \
disagree, lean toward the median view.
- "reviewer_voices" must include EVERY reviewer you were given, in order, \
using the exact handle from the input. The "quote" field is one verbatim \
sentence (<= 220 characters) from that reviewer that best captures their \
overall stance. Pick from strengths/weaknesses/summary/review fields only.
Never use the recommendation or rating string itself as the quote.
- "label" must be exactly one of: "Strong Accept", "Accept", "Weak Accept", \
"Borderline", "Reject". Map the reviewer's recommendation/rating to the \
closest of these.
"""


def _format_review_block(idx: int, review: dict[str, Any]) -> str:
    handle = review.get("handle", f"r{idx}")
    rating = review.get("rating")
    confidence = review.get("confidence")
    rating_str = f"{rating}/10" if rating is not None else "rating: unknown"
    conf_str = f"{confidence}/5" if confidence is not None else "conf: unknown"

    sections: list[str] = [f"## Reviewer {handle} — {rating_str} · {conf_str}"]
    content = review.get("content", {}) or {}
    for key in ("summary", "strengths", "weaknesses", "questions", "review",
                "soundness", "presentation", "contribution", "recommendation"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            sections.append(f"### {key}\n{value.strip()}")
    return "\n\n".join(sections)


OUTPUT_SCHEMA_HINT = json.dumps(
    {
        "tldr": "string, 2-3 sentences, plain prose, no hedging",
        "deep": ["string", "string", "..."],
        "skim": ["string", "..."],
        "dimensions": {
            "novelty": 0,
            "technical": 0,
            "clarity": 0,
            "impact": 0,
        },
        "reviewer_voices": [
            {
                "handle": "<verbatim from input>",
                "rating": 0,
                "label": "Strong Accept|Accept|Weak Accept|Borderline|Reject",
                "quote": "verbatim sentence from this reviewer, <= 220 chars",
            }
        ],
        "consensus_note": "one short clause",
    },
    indent=2,
)


def build_user_prompt(
    *,
    title: str,
    authors: list[str],
    venue: str | None,
    abstract: str | None,
    reviews: list[dict[str, Any]],
) -> str:
    review_blocks = [_format_review_block(i, r) for i, r in enumerate(reviews, start=1)]
    parts = [
        "# PAPER",
        f"Title: {title}",
        f"Authors: {', '.join(authors) if authors else 'Unknown'}",
        f"Venue: {venue or 'Unknown'}",
        "",
    ]
    if abstract:
        parts.extend(["# ABSTRACT", abstract.strip(), ""])
    parts.extend(["# REVIEWS", *review_blocks, ""])
    parts.extend(
        [
            "# OUTPUT_SCHEMA",
            "Return one JSON object matching this shape exactly (no other text):",
            OUTPUT_SCHEMA_HINT,
            "",
            "Remember: respond with ONLY the JSON object — no markdown, no explanation.",
        ]
    )
    return "\n".join(parts)
