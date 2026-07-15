from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Required before app.config / runtime import. Tests always use non-Secure cookies.
os.environ["COOKIE_SECURE"] = "false"
os.environ.setdefault("METRICS_SECRET", "test-metrics-secret-not-for-prod")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _default_allow_rate_limiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep contract tests isolated from live Redis rate-limit buckets."""
    from app import main
    from app.rate_limit import RateLimitDecision, RateLimiter

    class _AllowAll(RateLimiter):
        def __init__(self) -> None:
            pass

        def check_user_ip(self, ip: str) -> RateLimitDecision:
            return RateLimitDecision(allowed=True)

        def send_otp(self, *, ip: str, identifier: str) -> RateLimitDecision:
            return RateLimitDecision(allowed=True)

        def login_ip(self, ip: str) -> RateLimitDecision:
            return RateLimitDecision(allowed=True)

        def peek_login_fail_identifier(self, identifier: str) -> RateLimitDecision:
            return RateLimitDecision(allowed=True)

        def record_login_failure(self, identifier: str) -> RateLimitDecision:
            return RateLimitDecision(allowed=True)

        def clear_login_fail_identifier(self, identifier: str) -> None:
            return None

    monkeypatch.setattr(main, "rate_limiter", _AllowAll())
