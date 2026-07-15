"""Protected Prometheus metrics (no PII labels).

Labels are limited to method, route template, and status class. Never label
account_id, SID, identifier, phone, auth code, brand, query string, raw path,
or upstream bodies.
"""

from __future__ import annotations

import re
import resource
import secrets
import time
from collections.abc import Callable
from typing import Final

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Match
from starlette.types import ASGIApp

REGISTRY: Final[CollectorRegistry] = CollectorRegistry(auto_describe=True)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "HTTP requests",
    ["method", "route", "status_class"],
    registry=REGISTRY,
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency seconds",
    ["method", "route"],
    registry=REGISTRY,
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
ACTIVE_REQUESTS = Gauge(
    "http_requests_in_progress",
    "In-flight HTTP requests",
    registry=REGISTRY,
)
REDIS_READY = Gauge(
    "app_redis_ready",
    "1 if Redis ping succeeds else 0",
    registry=REGISTRY,
)
RATE_LIMIT_DECISIONS = Counter(
    "app_rate_limit_decisions_total",
    "Rate-limit decisions",
    ["endpoint", "result"],
    registry=REGISTRY,
)
UPSTREAM_OUTCOMES = Counter(
    "app_upstream_outcomes_total",
    "Upstream call outcomes by class",
    ["operation", "outcome_class"],
    registry=REGISTRY,
)
PROCESS_RSS = Gauge(
    "process_resident_memory_bytes",
    "Resident memory size in bytes",
    registry=REGISTRY,
)
PROCESS_CPU = Gauge(
    "process_cpu_seconds_total",
    "Total user and system CPU time spent in seconds",
    registry=REGISTRY,
)
PROCESS_START = Gauge(
    "process_start_time_seconds",
    "Start time of the process since unix epoch in seconds",
    registry=REGISTRY,
)
PROCESS_START.set(time.time())

_METRICS_PATH: Final[str] = "/metrics"
_UUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
_HEX_RE = re.compile(r"\b[0-9a-fA-F]{16,}\b")
_EMAIL_RE = re.compile(r"[^/]+@[^/]+")
_DIGITS_RE = re.compile(r"\b\d{6,}\b")


def normalize_route_template(path: str) -> str:
    """Collapse raw path segments into a low-cardinality template (no PII)."""
    if not path:
        return "unknown"
    parts: list[str] = []
    for segment in path.split("/"):
        if segment == "":
            parts.append(segment)
            continue
        if _UUID_RE.fullmatch(segment) or _HEX_RE.fullmatch(segment):
            parts.append(":id")
        elif _EMAIL_RE.fullmatch(segment) or "@" in segment:
            parts.append(":id")
        elif _DIGITS_RE.fullmatch(segment):
            parts.append(":id")
        else:
            parts.append(segment)
    template = "/".join(parts) if parts else path
    return template[:120] if len(template) > 120 else template


def route_template_from_request(request: Request) -> str:
    """Prefer Starlette matched route path template; fall back to normalized path."""
    route = request.scope.get("route")
    path_format = getattr(route, "path", None) or getattr(route, "path_format", None)
    if isinstance(path_format, str) and path_format:
        return path_format
    app = request.scope.get("app")
    if app is not None and hasattr(app, "router"):
        for r in app.router.routes:
            match, _ = r.matches(request.scope)
            if match == Match.FULL:
                p = getattr(r, "path", None)
                if isinstance(p, str) and p:
                    return p
    return normalize_route_template(request.url.path)


def status_class(status_code: int) -> str:
    if status_code < 200:
        return "1xx"
    if status_code < 300:
        return "2xx"
    if status_code < 400:
        return "3xx"
    if status_code < 500:
        return "4xx"
    return "5xx"


def observe_rate_limit(
    endpoint: str, *, allowed: bool, redis_error: bool = False
) -> None:
    if redis_error:
        result = "redis_error"
    elif allowed:
        result = "allowed"
    else:
        result = "limited"
    RATE_LIMIT_DECISIONS.labels(endpoint=endpoint, result=result).inc()


def observe_upstream(operation: str, outcome_class: str) -> None:
    UPSTREAM_OUTCOMES.labels(operation=operation, outcome_class=outcome_class).inc()


def set_redis_ready(ok: bool) -> None:
    REDIS_READY.set(1 if ok else 0)


def _refresh_process_metrics() -> None:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # Linux reports ru_maxrss in kilobytes.
    PROCESS_RSS.set(float(usage.ru_maxrss) * 1024.0)
    PROCESS_CPU.set(float(usage.ru_utime + usage.ru_stime))


def render_metrics() -> tuple[bytes, str]:
    _refresh_process_metrics()
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def authorize_metrics(provided: str | None, expected: str) -> str:
    """Return ok/missing/forbidden for metrics access (constant-time secret)."""
    if not expected:
        return "missing"
    if provided is None or not str(provided).strip():
        return "missing"
    if secrets.compare_digest(str(provided), expected):
        return "ok"
    return "forbidden"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Record request metrics; skip self-observation of /metrics."""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        if path == _METRICS_PATH:
            return await call_next(request)

        method = request.method.upper()
        route = route_template_from_request(request)
        ACTIVE_REQUESTS.inc()
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = int(response.status_code)
            return response
        finally:
            elapsed = time.perf_counter() - start
            ACTIVE_REQUESTS.dec()
            sc = status_class(status)
            REQUEST_COUNT.labels(method=method, route=route, status_class=sc).inc()
            REQUEST_LATENCY.labels(method=method, route=route).observe(elapsed)
