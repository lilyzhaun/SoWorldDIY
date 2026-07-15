"""Resolve client IP with optional trusted reverse-proxy forwarding."""

from __future__ import annotations

from collections.abc import Iterable
from ipaddress import ip_address
from typing import Final

DEFAULT_TRUSTED_PROXY_IPS: Final[frozenset[str]] = frozenset(
    {"127.0.0.1", "::1", "localhost"}
)


def parse_trusted_proxy_ips(raw: str | None) -> frozenset[str]:
    """Parse comma-separated trusted proxy list; empty/None → loopback defaults."""
    if raw is None or not str(raw).strip():
        return DEFAULT_TRUSTED_PROXY_IPS
    items = {part.strip() for part in str(raw).split(",") if part.strip()}
    return frozenset(items) if items else DEFAULT_TRUSTED_PROXY_IPS


def _normalize_ip(value: str) -> str:
    text = value.strip()
    if not text:
        return ""
    # Strip IPv6 brackets and optional port on host:port for IPv4.
    if text.startswith("[") and "]" in text:
        text = text[1 : text.index("]")]
    elif text.count(":") == 1 and "." in text:
        # IPv4:port
        text = text.rsplit(":", 1)[0]
    try:
        return str(ip_address(text))
    except ValueError:
        return text


def resolve_client_ip(
    *,
    peer: str | None,
    x_forwarded_for: str | None,
    trusted_proxies: Iterable[str] = DEFAULT_TRUSTED_PROXY_IPS,
) -> str:
    """Return client IP.

    Trust ``X-Forwarded-For`` only when the direct peer is in *trusted_proxies*.
    Uses the left-most (original client) address from the header when trusted.
    """
    peer_ip = _normalize_ip(peer or "") or "0.0.0.0"
    trusted = {_normalize_ip(p) for p in trusted_proxies}
    if peer_ip not in trusted:
        return peer_ip
    if not x_forwarded_for or not str(x_forwarded_for).strip():
        return peer_ip
    first = str(x_forwarded_for).split(",", 1)[0]
    forwarded = _normalize_ip(first)
    return forwarded or peer_ip
