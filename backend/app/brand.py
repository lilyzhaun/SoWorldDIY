"""Canonical sub-brand allowlist and plans-cache path containment."""

from __future__ import annotations

from pathlib import Path
from typing import Final, NewType

INVALID_BRAND_CODE: Final[str] = "invalid_brand"

# Ordered allowlist — single source of truth for plan brands.
SUPPORTED_BRANDS: Final[tuple[str, ...]] = ("THREE", "SOSIM", "HAHA", "TRADER")

Brand = NewType("Brand", str)


class InvalidBrandError(ValueError):
    """Raised when a brand is not an exact canonical allowlist member."""

    def __init__(self, raw: str | None = None) -> None:
        self.raw = raw
        self.code = INVALID_BRAND_CODE
        super().__init__(INVALID_BRAND_CODE)


def parse_brand(raw: str | None) -> Brand:
    """Accept only exact uppercase membership in ``SUPPORTED_BRANDS``.

    Does not strip, case-fold, or otherwise normalize input. Unknown values,
    lowercase/mixed-case variants, and path-like strings all raise
    ``InvalidBrandError``.
    """
    if raw is None or raw not in SUPPORTED_BRANDS:
        raise InvalidBrandError(raw)
    return Brand(raw)


def ensure_within_cache_dir(path: Path, cache_dir: Path) -> Path:
    """Resolve ``path`` with ``strict=False`` and require cache-root containment."""
    root = cache_dir.resolve(strict=False)
    target = path.resolve(strict=False)
    if not target.is_relative_to(root):
        raise InvalidBrandError(str(path))
    return target


def plans_cache_path(cache_dir: Path, brand: str | Brand) -> Path:
    """Build ``plans_{brand}.json`` under ``cache_dir`` after brand + containment checks."""
    canonical = parse_brand(str(brand))
    candidate = cache_dir / f"plans_{canonical}.json"
    ensure_within_cache_dir(candidate, cache_dir)
    return candidate
