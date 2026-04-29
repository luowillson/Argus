from __future__ import annotations

import logging
import re
from io import BytesIO
from urllib.parse import parse_qs, urlparse

import httpx
from pypdf import PdfReader

logger = logging.getLogger(__name__)

_YEAR_END_RE = re.compile(r"(?<=[.?!])\s+(?=[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'’-]+(?:\s|,))")
_PAGE_HEADER_RE = re.compile(r"Published as a conference paper at .+", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def extract_openreview_reference_texts(
    *,
    paper_id: str,
    openreview_url: str | None,
    max_references: int,
    timeout: float,
) -> list[str]:
    pdf_url = _openreview_pdf_url(paper_id, openreview_url)
    if pdf_url is None:
        return []
    try:
        response = httpx.get(pdf_url, follow_redirects=True, timeout=timeout)
        response.raise_for_status()
        reader = PdfReader(BytesIO(response.content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        logger.info("PDF reference extraction failed for %s", paper_id, exc_info=True)
        return []

    references_text = _references_section(text)
    if not references_text:
        return []
    return _split_reference_entries(references_text, max_references)


def _openreview_pdf_url(paper_id: str, openreview_url: str | None) -> str | None:
    if openreview_url:
        parsed = urlparse(openreview_url)
        forum_id = parse_qs(parsed.query).get("id", [None])[0]
        if forum_id:
            return f"https://openreview.net/pdf?id={forum_id}"
    if paper_id:
        return f"https://openreview.net/pdf?id={paper_id}"
    return None


def _references_section(text: str) -> str:
    matches = list(re.finditer(r"(?im)^references\s*$", text))
    if not matches:
        return ""
    section = text[matches[-1].end() :]
    appendix = re.search(r"(?im)^(appendix|supplementary material)\b", section)
    if appendix:
        section = section[: appendix.start()]
    return section


def _split_reference_entries(section: str, max_references: int) -> list[str]:
    cleaned = _PAGE_HEADER_RE.sub(" ", section)
    cleaned = cleaned.replace("-\n", "")
    cleaned = cleaned.replace("\n", " ")
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s+\d{1,3}\s+(?=[A-Z][A-Za-zÀ-ÖØ-öø-ÿ.'’-]+(?:\s|,))", " ", cleaned)
    chunks = _YEAR_END_RE.split(cleaned)
    entries: list[str] = []
    seen: set[str] = set()
    current = ""
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        current = f"{current} {chunk}".strip() if current else chunk
        if _looks_complete_reference(current):
            normalized = _WHITESPACE_RE.sub(" ", current).strip()
            key = normalized.lower()
            if key not in seen and 40 <= len(normalized) <= 800:
                seen.add(key)
                entries.append(normalized)
                if len(entries) >= max_references:
                    break
            current = ""
    return entries


def _looks_complete_reference(value: str) -> bool:
    return bool(re.search(r"\b(19|20)\d{2}[a-z]?[. ]*$", value))
