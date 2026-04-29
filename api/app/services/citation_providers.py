from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

_DOI_PREFIX_RE = re.compile(r"^(https?://(dx\.)?doi\.org/|doi:)", re.IGNORECASE)
_ARXIV_PREFIX_RE = re.compile(r"^(arxiv:|https?://arxiv\.org/(abs|pdf)/)", re.IGNORECASE)


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    doi = _DOI_PREFIX_RE.sub("", value.strip()).strip()
    return doi.lower() or None


def normalize_arxiv(value: str | None) -> str | None:
    if not value:
        return None
    arxiv_id = _ARXIV_PREFIX_RE.sub("", value.strip()).strip()
    arxiv_id = arxiv_id.removesuffix(".pdf")
    return arxiv_id.lower() or None


@dataclass(frozen=True)
class ExternalPaper:
    title: str
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    abstract: str | None = None
    citations: int | None = None
    references_count: int | None = None
    provider: str = ""
    provider_url: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CitationFetchResult:
    seed: ExternalPaper
    references: list[ExternalPaper]


class CitationProviderError(RuntimeError):
    pass


class SemanticScholarProvider:
    base_url = "https://api.semanticscholar.org/graph/v1"

    _PAPER_FIELDS = ",".join(
        [
            "paperId",
            "corpusId",
            "title",
            "authors",
            "year",
            "venue",
            "abstract",
            "citationCount",
            "referenceCount",
            "externalIds",
            "url",
        ]
    )
    _REFERENCE_FIELDS = ",".join(
        [
            "citedPaper.paperId",
            "citedPaper.corpusId",
            "citedPaper.title",
            "citedPaper.authors",
            "citedPaper.year",
            "citedPaper.venue",
            "citedPaper.abstract",
            "citedPaper.citationCount",
            "citedPaper.referenceCount",
            "citedPaper.externalIds",
            "citedPaper.url",
        ]
    )
    _SEARCH_FIELDS = ",".join(
        [
            "paperId",
            "corpusId",
            "title",
            "authors",
            "year",
            "venue",
            "abstract",
            "citationCount",
            "referenceCount",
            "externalIds",
            "url",
        ]
    )

    def __init__(
        self,
        *,
        api_key: str = "",
        timeout: float = 12.0,
        rate_limiter: Callable[[], None] | None = None,
    ) -> None:
        headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.Client(timeout=timeout, headers=headers)
        self._rate_limiter = rate_limiter

    def fetch(
        self,
        *,
        title: str,
        authors: list[str],
        year: int | None,
        doi: str | None,
        arxiv_id: str | None,
        max_references: int,
    ) -> CitationFetchResult | None:
        paper = self._resolve_paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            arxiv_id=arxiv_id,
        )
        if paper is None:
            return None

        # Always use the dedicated /references endpoint instead of inline
        # references from the paper lookup.  The /paper/{id} response silently
        # truncates the inline references list (often to <10 items), so papers
        # with 100+ references would appear to have only a handful.
        paper_id_str = str(paper.get("paperId") or "")
        references = self._fetch_references(paper_id_str, max_references)
        external_seed = self._to_external_paper(paper)
        refs = [
            self._to_external_paper(ref)
            for ref in references[:max_references]
            if isinstance(ref, dict) and ref.get("title")
        ]
        return CitationFetchResult(seed=external_seed, references=refs)

    def _resolve_paper(
        self,
        *,
        title: str,
        authors: list[str],
        year: int | None,
        doi: str | None,
        arxiv_id: str | None,
    ) -> dict[str, Any] | None:
        ids = []
        if doi:
            ids.append(f"DOI:{doi}")
        if arxiv_id:
            ids.append(f"ARXIV:{arxiv_id}")

        for paper_id in ids:
            data = self._get_json(
                f"{self.base_url}/paper/{paper_id}",
                params={"fields": self._PAPER_FIELDS},
                allow_404=True,
            )
            if data:
                return data

        data = self._get_json(
            f"{self.base_url}/paper/search",
            params={"query": title, "limit": 5, "fields": self._SEARCH_FIELDS},
            allow_404=True,
        )
        candidates = data.get("data", []) if isinstance(data, dict) else []
        best = _best_title_author_match(title, authors, year, candidates)
        if best is None:
            return None
        paper_id = best.get("paperId")
        if not paper_id:
            return best
        detailed = self._get_json(
            f"{self.base_url}/paper/{paper_id}",
            params={"fields": self._PAPER_FIELDS},
            allow_404=True,
        )
        return detailed or best

    def _fetch_references(self, paper_id: str, limit: int) -> list[dict[str, Any]]:
        if not paper_id or paper_id == "None":
            return []
        data = self._get_json(
            f"{self.base_url}/paper/{paper_id}/references",
            params={"fields": self._REFERENCE_FIELDS, "limit": limit},
            allow_404=True,
        )
        rows = (data.get("data") or []) if isinstance(data, dict) else []
        out: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("citedPaper"), dict):
                out.append(row["citedPaper"])
        return out

    def resolve_reference_text(self, reference_text: str) -> ExternalPaper | None:
        query = _reference_title_candidate(reference_text) or " ".join(reference_text.split())
        if len(query) < 30:
            return None
        data = self._get_json(
            f"{self.base_url}/paper/search",
            params={"query": query[:300], "limit": 5, "fields": self._SEARCH_FIELDS},
            allow_404=True,
        )
        candidates = (data.get("data") or []) if isinstance(data, dict) else []
        best = _best_reference_match(query, candidates)
        if best is None:
            return None
        return self._to_external_paper(best)

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, object],
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        try:
            if self._rate_limiter is not None:
                self._rate_limiter()
            res = self._client.get(url, params=params)
            if allow_404 and res.status_code == 404:
                return None
            res.raise_for_status()
            data = res.json()
            return data if isinstance(data, dict) else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise CitationProviderError("Semantic Scholar rate limit") from exc
            logger.info("Semantic Scholar lookup failed: %s", exc)
            return None
        except Exception as exc:
            logger.info("Semantic Scholar lookup failed: %s", exc)
            return None

    @staticmethod
    def _to_external_paper(data: dict[str, Any]) -> ExternalPaper:
        external_ids = _semantic_external_ids(data)
        return ExternalPaper(
            title=str(data.get("title") or "").strip(),
            authors=_author_names(data.get("authors")),
            year=_as_int(data.get("year")),
            venue=_as_nonempty_str(data.get("venue")),
            abstract=_as_nonempty_str(data.get("abstract")),
            citations=_as_int(data.get("citationCount")),
            references_count=_as_int(data.get("referenceCount")),
            provider="semantic_scholar",
            provider_url=_as_nonempty_str(data.get("url")),
            external_ids=external_ids,
        )


def make_default_provider(
    rate_limiter: Callable[[], None] | None = None,
) -> SemanticScholarProvider:
    settings = get_settings()
    return SemanticScholarProvider(
        api_key=settings.semantic_scholar_api_key,
        timeout=settings.citation_http_timeout,
        rate_limiter=rate_limiter,
    )


def _semantic_external_ids(data: dict[str, Any]) -> dict[str, str]:
    raw = data.get("externalIds") or {}
    out: dict[str, str] = {}
    if data.get("paperId"):
        out["semantic_scholar"] = str(data["paperId"])
    if data.get("corpusId"):
        out["corpus_id"] = str(data["corpusId"])
    if isinstance(raw, dict):
        if raw.get("DOI"):
            out["doi"] = str(raw["DOI"])
        if raw.get("ArXiv"):
            out["arxiv"] = str(raw["ArXiv"])
        if raw.get("CorpusId") and "corpus_id" not in out:
            out["corpus_id"] = str(raw["CorpusId"])
    return _normalize_external_ids(out)


def _normalize_external_ids(ids: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in ids.items():
        if key == "doi":
            normalized = normalize_doi(value)
            if normalized:
                out["doi"] = normalized
        elif key == "arxiv":
            normalized = normalize_arxiv(value)
            if normalized:
                out["arxiv"] = normalized
        else:
            out[key] = value
    return out


def _author_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def _best_title_author_match(
    title: str,
    authors: list[str],
    year: int | None,
    candidates: object,
) -> dict[str, Any] | None:
    if not isinstance(candidates, list):
        return None
    normalized_title = _fingerprint(title)
    author_tokens = {_last_name(name) for name in authors if _last_name(name)}
    best: tuple[float, dict[str, Any]] | None = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        candidate_title = str(item.get("title") or "")
        if not candidate_title:
            continue
        title_score = _jaccard(normalized_title, _fingerprint(candidate_title))
        candidate_year = _as_int(item.get("year"))
        year_score = 0.1 if year and candidate_year and abs(year - candidate_year) <= 1 else 0.0
        candidate_authors = _author_names(item.get("authors"))
        candidate_author_tokens = {_last_name(name) for name in candidate_authors if _last_name(name)}
        author_score = 0.0
        if author_tokens and candidate_author_tokens:
            author_score = 0.2 * _jaccard(author_tokens, candidate_author_tokens)
        score = title_score + year_score + author_score
        if best is None or score > best[0]:
            best = (score, item)
    if best is None or best[0] < 0.72:
        return None
    return best[1]


def _best_reference_match(reference_text: str, candidates: object) -> dict[str, Any] | None:
    if not isinstance(candidates, list):
        return None
    reference_tokens = _fingerprint(reference_text)
    best: tuple[float, dict[str, Any]] | None = None
    for item in candidates:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "")
        title_tokens = _fingerprint(title)
        if len(title_tokens) < 3:
            continue
        overlap = len(title_tokens.intersection(reference_tokens)) / len(title_tokens)
        jaccard = _jaccard(title_tokens, reference_tokens)
        score = overlap + jaccard
        if best is None or score > best[0]:
            best = (score, item)
    if best is None or best[0] < 0.78:
        return None
    return best[1]


def _reference_title_candidate(reference_text: str) -> str | None:
    text = " ".join(reference_text.split())
    parts = [part.strip() for part in text.split(". ") if part.strip()]
    if len(parts) < 2:
        return None
    for part in parts[1:4]:
        lowered = part.lower()
        if len(part) < 20:
            continue
        if lowered.startswith(("in ", "arxiv", "proceedings", "journal", "ieee", "acm")):
            continue
        if re.search(r"\b(19|20)\d{2}\b", part):
            continue
        return part
    return None


def _fingerprint(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a.intersection(b)) / len(a.union(b))


def _last_name(name: str) -> str:
    parts = re.findall(r"[a-zA-Z]+", name.lower())
    return parts[-1] if parts else ""


def _as_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_nonempty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
