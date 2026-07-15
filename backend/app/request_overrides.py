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
    """Resolve HTTP proxies for outbound requests.

    Contract (requests 2.34+ ``proxies`` parameter):
    - No local override module: return ``default`` by identity (``None`` or ``dict``).
    - Local override returns ``None``: return ``None``.
    - Local override returns a ``dict``: return that same object (identity preserved).
    - Local override returns a non-dict ``Mapping``: return a new plain ``dict`` copy.
    - Local override returns any other type: raise ``TypeError``.

    The optional local seam remains ``app.request_overrides_local.resolve_proxies``.
    """
    local_resolver = _load_resolver()
    if local_resolver is None:
        return default

    resolved = local_resolver(url, default)
    if resolved is None:
        return None
    if isinstance(resolved, dict):
        return resolved
    if isinstance(resolved, Mapping):
        return dict(resolved)
    raise TypeError(
        "app.request_overrides_local.resolve_proxies must return "
        "Mapping[str, str] | None"
    )
