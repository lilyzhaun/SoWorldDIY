from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import Protocol, cast


class _ResolveProxiesFn(Protocol):
    def __call__(
        self,
        url: str,
        default: dict[str, str] | None,
    ) -> Mapping[str, str] | None: ...


def _load_resolver() -> _ResolveProxiesFn | None:
    try:
        local_overrides = importlib.import_module(
            ".request_overrides_local", __package__
        )
    except ModuleNotFoundError as exc:
        if exc.name != f"{__package__}.request_overrides_local":
            raise
        return None

    resolve_proxies = getattr(local_overrides, "resolve_proxies", None)
    if not callable(resolve_proxies):
        raise TypeError(
            "app.request_overrides_local must expose callable resolve_proxies(url, default)"
        )

    return cast(_ResolveProxiesFn, resolve_proxies)


def resolve_proxies(url: str, default: dict[str, str] | None) -> dict[str, str] | None:
    """Return a requests-compatible proxy mapping (or None).

    Runtime values are unchanged: the optional local override is consulted when
    present; otherwise ``default`` is returned as-is. Non-dict mappings from a
    local override are copied into a plain ``dict`` for requests 2.34+.
    """
    local_resolver = _load_resolver()
    if local_resolver is None:
        return default

    resolved = local_resolver(url, default)
    if resolved is None:
        return None
    if isinstance(resolved, dict):
        return resolved
    return dict(resolved)
