def test_app_routes_available(monkeypatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app.main import app

    routes = {route.path for route in app.routes}
    assert "/_health" in routes
    assert "/_ready" in routes
    assert "/api/purchase" in routes
