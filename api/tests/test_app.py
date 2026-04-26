from app.main import create_app
from app.services.search import _browse_candidate_ids


def test_create_app_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert app.title == "Veros API"
    assert "/api/v1/health" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/papers/{paper_id}" in paths
    assert "/api/v1/saved" in paths


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
