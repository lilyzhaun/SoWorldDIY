"""Example local request override — copy to ``request_overrides_local.py``.

Reads the CMN-specific proxy from ``CMN_PROXY_URL`` (set in ``backend/.env``).
When the variable is empty or unset, the default proxy mapping passes through
unchanged. This file is tracked; the real local copy is gitignored.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

_CMN_PATH = "/mnms/holdAvailableNumbersFor15m/"


def resolve_proxies(
    url: str, default: Mapping[str, str] | None
) -> Mapping[str, str] | None:
    if _CMN_PATH not in url:
        return default

    proxy_url = os.environ.get("CMN_PROXY_URL", "").strip()
    if not proxy_url:
        return default

    return {"http": proxy_url, "https": proxy_url}
