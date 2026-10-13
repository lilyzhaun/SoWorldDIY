import json

import anyio
from pytest import MonkeyPatch

from app import main
from app.metrics import REGISTRY
from app.rate_limit import RateLimiter
from app.request_limits import MAX_REQUEST_BYTES, RequestBodyLimitMiddleware
from tests.contract_support import _install_fake_store, invoke
from tests.test_rate_limit import FakeRateRedis


def test_unmatched_routes_and_methods_have_bounded_labels(monkeypatch: MonkeyPatch):
    _install_fake_store(monkeypatch)
    for i in range(25):
        assert invoke(f"/random-path-{i}", method=f"CUSTOM{i}").status == 404
    samples = [s for metric in REGISTRY.collect() for s in metric.samples]
    labels = {(s.labels.get("method"), s.labels.get("route")) for s in samples}
    assert ("OTHER", "unmatched") in labels
    assert not any(route and route.startswith("/random-path-") for _, route in labels)


def test_invalid_auth_does_not_lock_login_or_otp(monkeypatch: MonkeyPatch):
    store = _install_fake_store(monkeypatch)
    ctx = store.create({"csrf_token": "tok"})
    redis = FakeRateRedis()
    limiter = RateLimiter(redis)
    monkeypatch.setattr(main, "rate_limiter", limiter)
    monkeypatch.setattr(
        main, "verify_auth_code", lambda code, consume: (False, "无效鉴权码")
    )
    for _ in range(5):
        assert (
            invoke(
                "/login",
                method="POST",
                headers={
                    "content-type": "application/x-www-form-urlencoded",
                    "cookie": f"session={ctx.sid}",
                    "x-csrf-token": "tok",
                },
                # A valid CSRF session does not authorize a gateway-code failure
                # to consume another user's login-failure quota.
                body=b"identifier=victim@example.invalid",
            ).status
            == 400
        )
    for _ in range(3):
        assert (
            invoke(
                "/api/send-otp",
                method="POST",
                body=b'{"identifier":"victim@example.invalid"}',
            ).status
            == 400
        )
    assert limiter.peek_login_fail_identifier("victim@example.invalid").allowed
    assert limiter.send_otp_identifier("victim@example.invalid").allowed


def test_blocked_otp_ip_cannot_consume_other_account_quota():
    from app.rate_limit import RateLimitConfig

    redis = FakeRateRedis()
    limiter = RateLimiter(redis, RateLimitConfig(send_otp_ip_limit=1))
    assert limiter.send_otp(ip="audit", identifier="first").allowed
    assert not limiter.send_otp(ip="audit", identifier="victim").allowed
    assert not any("victim" in key for key in redis.data)
    assert len([key for key in redis.data if ":id:" in key]) == 1


def test_body_limit_handles_lengths_and_chunked_bodies():
    async def probe(headers, chunks):
        called = False
        messages = []

        async def app(scope, receive, send):
            nonlocal called
            called = True

        async def receive():
            return chunks.pop(0)

        async def send(message):
            messages.append(message)

        await RequestBodyLimitMiddleware(app)(
            {"type": "http", "method": "POST", "headers": headers}, receive, send
        )
        return called, messages

    called, messages = anyio.run(
        probe, [(b"content-length", str(MAX_REQUEST_BYTES + 1).encode())], []
    )
    assert not called and messages[0]["status"] == 413
    called, messages = anyio.run(
        probe,
        [],
        [
            {
                "type": "http.request",
                "body": b"x" * MAX_REQUEST_BYTES,
                "more_body": True,
            },
            {"type": "http.request", "body": b"x", "more_body": False},
        ],
    )
    assert not called and json.loads(messages[1]["body"])["code"] == "request_too_large"
