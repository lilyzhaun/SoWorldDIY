from __future__ import annotations

from collections.abc import MutableMapping


def resolve_proxies(
    url: str, default: MutableMapping[str, str] | None
) -> MutableMapping[str, str] | None:
    """Return a requests-compatible mutable proxy mapping (or None).

    Runtime values are unchanged: the optional local override is consulted when
    present; otherwise ``default`` is returned as-is.
    """
    try:
        from .request_overrides_local import resolve_proxies as local_resolver
    except ImportError:
        return default

    resolved = local_resolver(url, default)
    if resolved is None:
        return None
    if isinstance(resolved, MutableMapping):
        return resolved
    return dict(resolved)
