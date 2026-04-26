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
    assert "/api/v1/saved" in paths
    assert "/api/v1/search/lookup" in paths


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
