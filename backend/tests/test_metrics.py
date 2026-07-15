"""Tests for protected Prometheus metrics and route normalization."""

from __future__ import annotations

from app.metrics import (
    REQUEST_COUNT,
    authorize_metrics,
    normalize_route_template,
    observe_rate_limit,
    render_metrics,
    status_class,
)


def test_authorize_metrics_missing_wrong_ok() -> None:
    secret = "metrics-test-secret"
    assert authorize_metrics(None, secret) == "missing"
    assert authorize_metrics("", secret) == "missing"
    assert authorize_metrics("wrong", secret) == "forbidden"
    assert authorize_metrics(secret, secret) == "ok"


def test_normalize_route_template_strips_pii_like_segments() -> None:
    assert normalize_route_template("/main/user@example.com") == "/main/:id"
    assert normalize_route_template("/api/profile") == "/api/profile"
    long_hex = "a" * 32
    assert normalize_route_template(f"/x/{long_hex}") == "/x/:id"


def test_status_class_buckets() -> None:
    assert status_class(200) == "2xx"
    assert status_class(404) == "4xx"
    assert status_class(503) == "5xx"


def test_render_metrics_includes_http_and_rate_limit_series() -> None:
    REQUEST_COUNT.labels(method="GET", route="/_health", status_class="2xx").inc()
    observe_rate_limit("check_user", allowed=False, redis_error=False)
    body, content_type = render_metrics()
    text = body.decode("utf-8")
    assert "text/plain" in content_type or "openmetrics" in content_type
    assert "http_requests_total" in text
    assert 'route="/_health"' in text or 'route="/_health"' in text
    assert "app_rate_limit_decisions_total" in text
    assert "check_user" in text
    # Sentinel PII must never appear as metric labels
    assert "user@example.com" not in text
    assert "auth_code" not in text.lower() or "auth_code" not in text
