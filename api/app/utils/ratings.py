"""Parse OpenReview rating/confidence fields.

Reviewers fill these in different shapes per venue:
  rating:     8 | "8" | "8: accept, good paper" | "8.0"
  confidence: 4 | "4" | "4: The reviewer is confident but not absolutely certain..."
"""

from __future__ import annotations

import re
from typing import Any

_LEADING_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def parse_numeric(value: Any) -> float | None:
    """Best-effort extraction of the leading numeric token from a rating-like field."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    match = _LEADING_NUMBER.search(value)
    return float(match.group(0)) if match else None


def parse_recommendation(value: Any) -> str | None:
    """Extract the recommendation label after a numeric prefix, if present.

    "8: accept, good paper" -> "accept, good paper"
    "Accept (Oral)"         -> "Accept (Oral)"
    8                       -> None
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    after_colon = text.split(":", 1)
    if len(after_colon) == 2 and _LEADING_NUMBER.fullmatch(after_colon[0].strip()):
        return after_colon[1].strip() or None
    return text
