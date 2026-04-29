from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

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
            "references.paperId",
            "references.corpusId",
            "references.title",
            "references.authors",
            "references.year",
            "references.venue",
            "references.abstract",
            "references.citationCount",
            "references.referenceCount",
            "references.externalIds",
            "references.url",
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

    def __init__(self, *, api_key: str = "", timeout: float = 12.0) -> None:
        headers = {"x-api-key": api_key} if api_key else {}
        self._client = httpx.Client(timeout=timeout, headers=headers)

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

        references = paper.get("references")
        if not isinstance(references, list):
            references = self._fetch_references(str(paper.get("paperId")), max_references)
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
        rows = data.get("data", []) if isinstance(data, dict) else []
        out: list[dict[str, Any]] = []
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("citedPaper"), dict):
                out.append(row["citedPaper"])
        return out

    def _get_json(
        self,
        url: str,
        *,
        params: dict[str, object],
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        try:
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


class OpenAlexProvider:
    base_url = "https://api.openalex.org"

    _WORK_FIELDS = ",".join(
        [
            "id",
            "doi",
            "display_name",
            "publication_year",
            "cited_by_count",
            "referenced_works_count",
            "referenced_works",
            "authorships",
            "primary_location",
            "abstract_inverted_index",
            "ids",
        ]
    )

    def __init__(
        self,
        *,
        api_key: str = "",
        mailto: str = "",
        timeout: float = 12.0,
    ) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._api_key = api_key
        self._mailto = mailto

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
        refs = []
        for ref_id in (paper.get("referenced_works") or [])[:max_references]:
            if not isinstance(ref_id, str):
                continue
            ref = self._get_work(ref_id)
            if ref is not None:
                refs.append(self._to_external_paper(ref))
        return CitationFetchResult(seed=self._to_external_paper(paper), references=refs)

    def _resolve_paper(
        self,
        *,
        title: str,
        authors: list[str],
        year: int | None,
        doi: str | None,
        arxiv_id: str | None,
    ) -> dict[str, Any] | None:
        if doi:
            work = self._get_work(f"doi:{doi}")
            if work is not None:
                return work
        if arxiv_id:
            work = self._get_work(f"arxiv:{arxiv_id}")
            if work is not None:
                return work
        data = self._get_json(
            f"{self.base_url}/works",
            params={"search": title, "per_page": 5, "select": self._WORK_FIELDS},
        )
        candidates = data.get("results", []) if isinstance(data, dict) else []
        return _best_title_author_match(title, authors, year, candidates)

    def _get_work(self, work_id: str) -> dict[str, Any] | None:
        normalized_id = work_id.removeprefix("https://openalex.org/")
        return self._get_json(
            f"{self.base_url}/works/{quote(normalized_id, safe=':')}",
            params={"select": self._WORK_FIELDS},
        )

    def _get_json(self, url: str, *, params: dict[str, object]) -> dict[str, Any] | None:
        full_params = dict(params)
        if self._api_key:
            full_params["api_key"] = self._api_key
        if self._mailto:
            full_params["mailto"] = self._mailto
        try:
            res = self._client.get(url, params=full_params)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            data = res.json()
            return data if isinstance(data, dict) else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise CitationProviderError("OpenAlex rate limit") from exc
            logger.info("OpenAlex lookup failed: %s", exc)
            return None
        except Exception as exc:
            logger.info("OpenAlex lookup failed: %s", exc)
            return None

    @staticmethod
    def _to_external_paper(data: dict[str, Any]) -> ExternalPaper:
        ids = dict(data.get("ids") or {})
        if data.get("doi"):
            ids["doi"] = data["doi"]
        if data.get("id"):
            ids["openalex"] = data["id"]
        location = data.get("primary_location") or {}
        provider_url = location.get("landing_page_url") if isinstance(location, dict) else None
        return ExternalPaper(
            title=str(data.get("display_name") or data.get("title") or "").strip(),
            authors=_openalex_author_names(data.get("authorships")),
            year=_as_int(data.get("publication_year")),
            venue=_openalex_venue(data.get("primary_location")),
            abstract=_abstract_from_inverted_index(data.get("abstract_inverted_index")),
            citations=_as_int(data.get("cited_by_count")),
            references_count=_as_int(data.get("referenced_works_count")),
            provider="openalex",
            provider_url=_as_nonempty_str(provider_url),
            external_ids=_openalex_external_ids(ids),
        )


class CrossrefProvider:
    base_url = "https://api.crossref.org"

    def __init__(self, *, mailto: str = "", timeout: float = 12.0) -> None:
        self._client = httpx.Client(timeout=timeout)
        self._mailto = mailto

    def lookup_doi(self, doi: str) -> ExternalPaper | None:
        params = {"mailto": self._mailto} if self._mailto else {}
        try:
            res = self._client.get(f"{self.base_url}/works/{doi}", params=params)
            if res.status_code == 404:
                return None
            res.raise_for_status()
            body = res.json()
            message = body.get("message") if isinstance(body, dict) else None
            if not isinstance(message, dict):
                return None
            title = _first(message.get("title"))
            if not title:
                return None
            year = _crossref_year(message)
            return ExternalPaper(
                title=title,
                authors=_crossref_authors(message.get("author")),
                year=year,
                venue=_first(message.get("container-title")),
                abstract=_as_nonempty_str(message.get("abstract")),
                citations=_as_int(message.get("is-referenced-by-count")),
                references_count=_as_int(message.get("references-count")),
                provider="crossref",
                provider_url=_as_nonempty_str(message.get("URL")),
                external_ids={"doi": doi},
            )
        except Exception as exc:
            logger.info("Crossref lookup failed: %s", exc)
            return None


def make_default_providers() -> tuple[SemanticScholarProvider, OpenAlexProvider, CrossrefProvider]:
    settings = get_settings()
    return (
        SemanticScholarProvider(
            api_key=settings.semantic_scholar_api_key,
            timeout=settings.citation_http_timeout,
        ),
        OpenAlexProvider(
            api_key=settings.openalex_api_key,
            mailto=settings.crossref_mailto,
            timeout=settings.citation_http_timeout,
        ),
        CrossrefProvider(
            mailto=settings.crossref_mailto,
            timeout=settings.citation_http_timeout,
        ),
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


def _openalex_external_ids(raw: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ("openalex", "doi", "pmid", "pmcid"):
        if raw.get(key):
            out[key] = str(raw[key])
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
        elif key == "openalex":
            out["openalex"] = value.removeprefix("https://openalex.org/")
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


def _openalex_author_names(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if not isinstance(item, dict):
            continue
        author = item.get("author")
        if isinstance(author, dict) and author.get("display_name"):
            names.append(str(author["display_name"]))
        elif item.get("raw_author_name"):
            names.append(str(item["raw_author_name"]))
    return names


def _openalex_venue(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    source = value.get("source")
    if isinstance(source, dict) and source.get("display_name"):
        return str(source["display_name"])
    return None


def _abstract_from_inverted_index(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    positions: list[tuple[int, str]] = []
    for word, raw_positions in value.items():
        if not isinstance(raw_positions, list):
            continue
        for pos in raw_positions:
            if isinstance(pos, int):
                positions.append((pos, str(word)))
    if not positions:
        return None
    return " ".join(word for _, word in sorted(positions))


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
        candidate_title = str(item.get("title") or item.get("display_name") or "")
        if not candidate_title:
            continue
        title_score = _jaccard(normalized_title, _fingerprint(candidate_title))
        candidate_year = _as_int(item.get("year") or item.get("publication_year"))
        year_score = 0.1 if year and candidate_year and abs(year - candidate_year) <= 1 else 0.0
        candidate_authors = _author_names(item.get("authors")) or _openalex_author_names(
            item.get("authorships")
        )
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


def _first(value: object) -> str | None:
    if isinstance(value, list) and value:
        return _as_nonempty_str(value[0])
    return _as_nonempty_str(value)


def _crossref_authors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    names = []
    for item in value:
        if not isinstance(item, dict):
            continue
        given = str(item.get("given") or "").strip()
        family = str(item.get("family") or "").strip()
        name = " ".join(part for part in (given, family) if part)
        if name:
            names.append(name)
    return names


def _crossref_year(message: dict[str, Any]) -> int | None:
    for key in ("published-print", "published-online", "published", "issued"):
        raw = message.get(key)
        if not isinstance(raw, dict):
            continue
        date_parts = raw.get("date-parts")
        if (
            isinstance(date_parts, list)
            and date_parts
            and isinstance(date_parts[0], list)
            and date_parts[0]
        ):
            return _as_int(date_parts[0][0])
    return None
