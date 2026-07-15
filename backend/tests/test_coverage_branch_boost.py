"""Focused tests to lift branch coverage above 70% for ratchet baseline."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.brand import (
    SUPPORTED_BRANDS,
    InvalidBrandError,
    ensure_within_cache_dir,
    parse_brand,
    plans_cache_path,
)
from app.services import get_brand_by_sub_id
from app.session_store import SessionContext
from app.upstream_urls import simworld_url


def test_simworld_url_and_parse_brand() -> None:
    url = simworld_url("THREE", "user", "login")
    assert "user" in url and "login" in url
    assert parse_brand("THREE") in SUPPORTED_BRANDS
    assert parse_brand("SOSIM") in SUPPORTED_BRANDS
    with pytest.raises(InvalidBrandError):
        parse_brand("NOT_A_BRAND")
    with pytest.raises(InvalidBrandError):
        parse_brand("three")  # case-sensitive


def test_plans_cache_path_containment(tmp_path: Path) -> None:
    base = tmp_path / "plans_cache"
    base.mkdir()
    path = plans_cache_path(base, "THREE")
    assert ensure_within_cache_dir(path, base) == path
    outside = tmp_path / "other.json"
    with pytest.raises(InvalidBrandError):
        ensure_within_cache_dir(outside, base)


def test_get_brand_by_sub_id_paths() -> None:
    ctx = SessionContext(
        sid="s",
        data={
            "accounts": {
                "a@b.com": {"sub_brand": "SOSIM", "subscriptionId": "sub1"},
            }
        },
    )
    assert get_brand_by_sub_id(ctx, None, "a@b.com") == "SOSIM"
    assert isinstance(get_brand_by_sub_id(ctx, None, "missing@x.com"), str)
    assert isinstance(get_brand_by_sub_id(ctx, "sub1", "a@b.com"), str)
