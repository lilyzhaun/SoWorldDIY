from __future__ import annotations

from collections.abc import Mapping


def resolve_proxies(
    url: str, default: Mapping[str, str] | None
) -> Mapping[str, str] | None:
    try:
        from .request_overrides_local import resolve_proxies as local_resolver
    except ImportError:
        return default

    return local_resolver(url, default)
