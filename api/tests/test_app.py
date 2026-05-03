from app.main import create_app
from app.services.search import (
    _browse_candidate_ids,
    classify_intent,
    looks_like_title,
    top_title_similarity,
)


def test_create_app_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert app.title == "Veros API"
    assert "/api/v1/health" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/papers/{paper_id}" in paths
    assert "/api/v1/papers/batch" in paths
    assert "/api/v1/papers/{paper_id}/citations" in paths
    assert "/api/v1/papers/{paper_id}/citations/enrich" in paths
    assert "/api/v1/saved" in paths
    assert "/api/v1/saved/{paper_id}" in paths
    assert "/api/v1/search/lookup" in paths
    assert "/api/v1/search/page" in paths
    assert "/api/v1/landing/graph" in paths
    assert "/api/v1/rankings/papers/citations" in paths


def test_calculate_pagerank_uses_citation_direction() -> None:
    from app.services.graph_metrics import calculate_pagerank

    result = calculate_pagerank(
        [("paper-a", "paper-b"), ("paper-a", "paper-c"), ("paper-b", "paper-c")],
        tolerance=1e-10,
    )

    assert result.converged
    assert result.edge_count == 3
    assert result.in_degree == {"paper-a": 0, "paper-b": 1, "paper-c": 2}
    assert result.out_degree == {"paper-a": 2, "paper-b": 1, "paper-c": 0}
    assert abs(sum(result.ranks.values()) - 1.0) < 1e-9
    assert result.ranks["paper-c"] > result.ranks["paper-b"] > result.ranks["paper-a"]


class _FakeRows:
    def fetchall(self) -> list[tuple[str]]:
        return [("paper-high",), ("paper-next",)]


class _FakeSession:
    def __init__(self) -> None:
        self.sql = ""
        self.params: dict[str, int] = {}

    def execute(self, statement: object, params: dict[str, int]) -> _FakeRows:
        self.sql = str(statement)
        self.params = params
        return _FakeRows()


def test_browse_candidates_rank_by_score_before_pagination() -> None:
    db = _FakeSession()

    ids = _browse_candidate_ids(db, limit=25, offset=50)  # type: ignore[arg-type]

    assert ids == ["paper-high", "paper-next"]
    assert "LEFT JOIN veros_scores" in db.sql
    assert "s.score DESC NULLS LAST" in db.sql
    assert "LIMIT :lim OFFSET :off" in db.sql
    assert db.params == {"lim": 25, "off": 50}


class _FakeFirst:
    def __init__(self, value: object) -> None:
        self._value = (value,)

    def first(self) -> tuple[object]:
        return self._value


class _StubSimilaritySession:
    """Returns a fixed similarity value from .execute(...).first()."""

    def __init__(self, similarity: float) -> None:
        self._similarity = similarity

    def execute(self, statement: object, params: dict[str, object]) -> _FakeFirst:
        return _FakeFirst(self._similarity)


def test_top_title_similarity_empty_query_returns_zero() -> None:
    db = _StubSimilaritySession(0.9)
    assert top_title_similarity(db, "  ") == 0.0  # type: ignore[arg-type]


def test_top_title_similarity_returns_max() -> None:
    db = _StubSimilaritySession(0.42)
    assert top_title_similarity(db, "transformer") == 0.42  # type: ignore[arg-type]


def test_classify_intent_topic_for_short_keyword() -> None:
    db = _StubSimilaritySession(0.1)
    info = classify_intent(db, "transformer")  # type: ignore[arg-type]
    assert info["mode"] == "topic"
    assert info["top_sim"] == 0.1


def test_lookup_can_skip_result_payload(monkeypatch) -> None:
    from app.routers import search as search_router

    monkeypatch.setattr(
        search_router,
        "classify_intent",
        lambda db, q: {"mode": "topic", "top_sim": 0.1},
    )

    def fail_search(*args, **kwargs):
        raise AssertionError("search_papers should not run for lightweight lookup")

    monkeypatch.setattr(search_router, "search_papers", fail_search)

    response = search_router.lookup(
        search_router.LookupRequest(q="transformer"),
        object(),  # type: ignore[arg-type]
        include_results=False,
    )

    assert response.intent == "topic"
    assert response.paper_id is None
    assert response.results == []


def test_lookup_includes_result_payload_by_default(monkeypatch) -> None:
    from app.routers import search as search_router

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        search_router,
        "classify_intent",
        lambda db, q: {"mode": "topic", "top_sim": 0.1},
    )
    monkeypatch.setattr(
        search_router,
        "search_papers",
        lambda db, q, mode: calls.append((q, mode)) or [],
    )

    response = search_router.lookup(
        search_router.LookupRequest(q="transformer"),
        object(),  # type: ignore[arg-type]
    )

    assert response.intent == "topic"
    assert response.results == []
    assert calls == [("transformer", "topic")]


def test_classify_intent_specific_for_high_similarity() -> None:
    db = _StubSimilaritySession(0.9)
    info = classify_intent(db, "transformer")  # type: ignore[arg-type]
    assert info["mode"] == "specific"
    assert info["top_sim"] == 0.9


def test_classify_intent_specific_for_long_query_even_when_db_cold() -> None:
    """A 5-word title should classify as specific even with no in-DB matches."""
    db = _StubSimilaritySession(0.0)
    info = classify_intent(db, "Attention Is All You Need")  # type: ignore[arg-type]
    assert info["mode"] == "specific"


def test_looks_like_title_heuristic() -> None:
    # Topic-shaped queries.
    assert not looks_like_title("transformer")
    assert not looks_like_title("sparse autoencoders")
    assert not looks_like_title("diffusion models tutorial")
    # Title-shaped queries.
    assert looks_like_title("Attention Is All You Need")
    assert looks_like_title("Denoising Diffusion Probabilistic Models")
    assert looks_like_title("attention is all you need")  # 5+ words even lowercase


def test_openreview_title_similarity_helper() -> None:
    from app.services.openreview_search import _title_similarity

    assert _title_similarity("Attention is All You Need", "Attention Is All You Need") == 1.0
    assert _title_similarity("transformer paper", "Attention Is All You Need") < 0.5


def test_citation_provider_normalizes_external_ids() -> None:
    from app.services.citation_providers import SemanticScholarProvider

    paper = SemanticScholarProvider._to_external_paper(
        {
            "paperId": "abc123",
            "corpusId": 987,
            "title": "Reference Paper",
            "authors": [{"name": "A. Researcher"}],
            "year": 2024,
            "citationCount": 12,
            "referenceCount": 3,
            "externalIds": {
                "DOI": "https://doi.org/10.123/Example",
                "ArXiv": "arXiv:2401.00001",
            },
        }
    )

    assert paper.external_ids == {
        "semantic_scholar": "abc123",
        "corpus_id": "987",
        "doi": "10.123/example",
        "arxiv": "2401.00001",
    }
    assert paper.authors == ["A. Researcher"]
    assert paper.citations == 12


def test_semantic_scholar_references_allows_null_data() -> None:
    from app.services.citation_providers import SemanticScholarProvider

    provider = SemanticScholarProvider()
    provider._get_json = lambda *args, **kwargs: {"data": None}  # type: ignore[method-assign]

    assert provider._fetch_references("paper-id", 5) == []


def test_pdf_reference_split_removes_page_number_boundaries() -> None:
    from app.services.citation_pdf import _split_reference_entries

    section = (
        "Alice Example. First useful paper. arXiv preprint arXiv:2401.1, "
        "2024. 10 Bob Example. Second useful paper. In Conference, 2023."
    )

    entries = _split_reference_entries(section, 5)

    assert len(entries) == 2
    assert entries[0].startswith("Alice Example")
    assert entries[1].startswith("Bob Example")


def test_landing_graph_falls_back_when_no_rows() -> None:
    from app.services.landing_graph import build_landing_graph

    class _EmptySession:
        def execute(self, statement: object, params: dict[str, int]):
            sql = str(statement)

            class _CountRow:
                def scalar_one(self):
                    return 500

            class _Rows:
                def mappings(self):
                    return self

                def first(self):
                    return None

                def __iter__(self):
                    return iter(())

            if "COUNT(*) FROM paper_embeddings" in sql:
                return _CountRow()
            return _Rows()

    graph = build_landing_graph(_EmptySession())  # type: ignore[arg-type]

    assert graph.nodes == []
    assert graph.edges == []


def test_landing_graph_parses_string_embeddings() -> None:
    from app.services.landing_graph import build_landing_graph

    class _Session:
        def execute(self, statement: object, params: dict[str, int]):
            sql = str(statement)

            class _CountRow:
                def scalar_one(self):
                    return 500

            class _SeedRows:
                def mappings(self):
                    return self

                def first(self):
                    return {"paper_id": "p1", "title": "Paper One", "venue": "ICLR"}

            class _ClusterRows:
                def mappings(self):
                    return self

                def __iter__(self):
                    return iter(
                        [
                            {
                                "id": "p1",
                                "title": "Paper One",
                                "venue": "ICLR",
                                "score": 8.4,
                                "verdict": "Accept",
                                "embedding": "[1,0,0]",
                            },
                            {
                                "id": "p2",
                                "title": "Paper Two",
                                "venue": "ICLR",
                                "score": 8.1,
                                "verdict": "Weak Accept",
                                "embedding": "[0.9,0.1,0]",
                            },
                        ]
                    )

            if "COUNT(*) FROM paper_embeddings" in sql:
                return _CountRow()
            if "eligible_seed" in sql:
                return _SeedRows()
            return _ClusterRows()

    graph = build_landing_graph(_Session())  # type: ignore[arg-type]

    assert graph.topic_paper_id == "p1"
    assert graph.topic_title == "Paper One"
    assert [node.id for node in graph.nodes] == ["p1", "p2"]
    assert graph.edges
    assert graph.edges[0].source == "p1"
    assert graph.edges[0].target == "p2"


def test_landing_graph_connects_topic_cluster() -> None:
    from app.services.landing_graph import build_landing_graph

    cluster_rows = [
        {
            "id": "seed",
            "title": "Seed Paper",
            "venue": "ICLR",
            "score": 9.0,
            "verdict": "Strong Accept",
            "embedding": "[1,0,0]",
        },
        {
            "id": "n1",
            "title": "Neighbor 1",
            "venue": "ICLR",
            "score": 8.7,
            "verdict": "Accept",
            "embedding": "[0.95,0.05,0]",
        },
        {
            "id": "n2",
            "title": "Neighbor 2",
            "venue": "ICLR",
            "score": 8.2,
            "verdict": "Weak Accept",
            "embedding": "[0.93,0.07,0]",
        },
        {
            "id": "n3",
            "title": "Neighbor 3",
            "venue": "ICLR",
            "score": 7.8,
            "verdict": "Borderline",
            "embedding": "[0.9,0.08,0.02]",
        },
    ]

    class _Session:
        def execute(self, statement: object, params: dict[str, int]):
            sql = str(statement)

            class _CountRow:
                def scalar_one(self):
                    return 500

            class _SeedRows:
                def mappings(self):
                    return self

                def first(self):
                    return {"paper_id": "seed", "title": "Seed Paper", "venue": "ICLR"}

            class _ClusterRows:
                def mappings(self):
                    return self

                def __iter__(self):
                    return iter(cluster_rows)

            if "COUNT(*) FROM paper_embeddings" in sql:
                return _CountRow()
            if "eligible_seed" in sql:
                return _SeedRows()
            return _ClusterRows()

    graph = build_landing_graph(_Session())  # type: ignore[arg-type]

    touched = {graph.topic_paper_id}
    for edge in graph.edges:
        touched.add(edge.source)
        touched.add(edge.target)
    assert touched == {"seed", "n1", "n2", "n3"}
    assert len(graph.edges) >= len(graph.nodes) - 1
