from app.main import create_app


def test_create_app_registers_core_routes() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}

    assert app.title == "Veros API"
    assert "/api/v1/health" in paths
    assert "/api/v1/search" in paths
    assert "/api/v1/papers/{paper_id}" in paths
    assert "/api/v1/saved" in paths
