"""Commerce helpers: wallet balance parse and plans cache load."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_wallet_balance(data: Any) -> float:
    """Return max amount from WalletBalances list payload, else 0."""
    if isinstance(data, list) and data:
        return max(
            float(item.get("amount", 0)) for item in data if "amount" in item
        )
    return 0.0


def load_plans_from_cache(
    cache_file: Path,
    *,
    brand: str | None = None,
) -> dict[str, Any] | None:
    """Load plans JSON from disk; log and return None on parse failure.

    Missing file returns None without logging (caller decides next step).
    """
    if not cache_file.exists():
        return None
    try:
        loaded = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(
            "plans cache parse failed brand=%s path=%s",
            brand,
            cache_file,
            exc_info=True,
        )
        return None
    if isinstance(loaded, dict):
        return loaded
    return None
