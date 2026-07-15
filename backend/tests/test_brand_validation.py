"""Brand allowlist, cache containment, and upstream URL brand guards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from pytest import MonkeyPatch

from app import main
from app.brand import (
    INVALID_BRAND_CODE,
    SUPPORTED_BRANDS,
    InvalidBrandError,
    parse_brand,
    plans_cache_path,
)
from app.services import fetch_and_save_plans_background
from app.services_commerce import load_plans_from_cache
from app.upstream_urls import (
    SIMWORLD_API_BASE,
    THREE_ACCOUNT_BASE,
    simworld_url,
    three_offer_url,
)
from tests.contract_support import authed_request, run_endpoint


def test_parse_brand_accepts_only_canonical_uppercase() -> None:
    for brand in SUPPORTED_BRANDS:
        assert parse_brand(brand) == brand


@pytest.mark.parametrize(
    "raw",
    [
        "three",
        "Three",
        "sosim",
        "HaHa",
        "trader",
        "NOPE",
        "FOUR",
        "../../etc/passwd",
        "THREE/../X",
        "../",
        "",
        "THREE ",
        " THREE",
    ],
)
def test_parse_brand_rejects_non_canonical_and_unknown(raw: str) -> None:
    with pytest.raises(InvalidBrandError) as exc_info:
        parse_brand(raw)
    assert exc_info.value.code == INVALID_BRAND_CODE


def test_plans_cache_path_stays_inside_root(tmp_path: Path) -> None:
    for brand in SUPPORTED_BRANDS:
        path = plans_cache_path(tmp_path, parse_brand(brand))
        assert path.parent == tmp_path.resolve(strict=False) or path.is_relative_to(
            tmp_path.resolve(strict=False)
        )
        assert path.name == f"plans_{brand}.json"
        assert path.resolve(strict=False).is_relative_to(tmp_path.resolve(strict=False))


@pytest.mark.parametrize(
    "raw",
    ["../../etc/passwd", "THREE/../X", "three", "UNKNOWN"],
)
def test_plans_cache_path_rejects_invalid_brand(tmp_path: Path, raw: str) -> None:
    with pytest.raises(InvalidBrandError):
        plans_cache_path(tmp_path, raw)


def test_load_plans_from_cache_rejects_path_outside_root(tmp_path: Path) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    outside = tmp_path / "escape.json"
    outside.write_text(
        json.dumps({"status": "success", "plans": [{"offerId": "leak"}]}),
        encoding="utf-8",
    )
    with pytest.raises(InvalidBrandError) as exc_info:
        load_plans_from_cache(outside, cache_root=cache_root, brand="THREE")
    assert exc_info.value.code == INVALID_BRAND_CODE
    assert outside.exists()


def test_load_plans_from_cache_ok_with_contained_path(tmp_path: Path) -> None:
    payload = {"status": "success", "plans": [{"offerId": "X"}]}
    good = tmp_path / "plans_THREE.json"
    good.write_text(json.dumps(payload), encoding="utf-8")
    assert load_plans_from_cache(good, cache_root=tmp_path, brand="THREE") == payload
    assert load_plans_from_cache(tmp_path / "missing.json", cache_root=tmp_path) is None


def test_fetch_and_save_plans_background_rejects_traversal(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[str] = []

    class _Session:
        def __enter__(self) -> _Session:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def cookies(self) -> None:
            return None

        def get(self, url: str, **_: Any) -> Any:
            calls.append(url)
            raise AssertionError(f"outbound must not run: {url}")

    class _SessionWithCookies(_Session):
        def __init__(self) -> None:
            self.cookies: dict[str, str] = {}

        def get(self, url: str, **_: Any) -> Any:
            calls.append(url)
            raise AssertionError(f"outbound must not run: {url}")

    monkeypatch.setattr("app.services.PLANS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services._deps",
        lambda: type(
            "D",
            (),
            {
                "plans_refreshing": set(),
                "get_isolated_session": lambda: _SessionWithCookies(),
            },
        )(),
    )

    fetch_and_save_plans_background("../../etc/passwd", {"k": "v"}, "ua")
    fetch_and_save_plans_background("THREE/../X", {"k": "v"}, "ua")
    fetch_and_save_plans_background("three", {"k": "v"}, "ua")

    assert calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "raw",
    ["../../etc/passwd", "THREE/../X", "three", "NOPE", "%2e%2e%2f"],
)
def test_upstream_url_builders_reject_invalid_brand(raw: str) -> None:
    with pytest.raises(InvalidBrandError):
        simworld_url(raw, "offer/getPlanOffers/")
    with pytest.raises(InvalidBrandError):
        three_offer_url(raw, "offer/getPlanOffers/")


def test_upstream_url_builders_accept_supported_brands() -> None:
    for brand in SUPPORTED_BRANDS:
        assert (
            simworld_url(brand, "sim", "1", "WalletBalances")
            == f"{SIMWORLD_API_BASE}/{brand}/sim/1/WalletBalances"
        )
        assert (
            three_offer_url(brand, "offer/getPlanOffers/")
            == f"{THREE_ACCOUNT_BASE}/{brand}/offer/getPlanOffers/"
        )


def _plans_request(brand_query: str) -> Any:
    request = authed_request("/api/plans", "GET")
    request.scope["query_string"] = (
        f"account_id=a@b.com&subscriptionId=s&brand={brand_query}".encode()
    )
    return request


@pytest.mark.parametrize(
    "brand",
    [
        "../../etc/passwd",
        quote("../../etc/passwd", safe=""),
        "%2e%2e%2f",
        "THREE/../X",
        quote("THREE/../X", safe=""),
        "three",
        "Three",
        "SOSIM/../THREE",
        "NOPE",
        "HAHA%2f..%2fX",
    ],
)
def test_plans_api_rejects_traversal_and_non_canonical_brands(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    brand: str,
) -> None:
    outside_before = (
        {p.name for p in Path("/tmp").iterdir()} if Path("/tmp").exists() else set()
    )
    sentinel = tmp_path.parent / f"task2-escape-{tmp_path.name}.json"
    if sentinel.exists():
        sentinel.unlink()

    outbound: list[tuple[Any, ...]] = []

    def capture_background(*args: Any, **_kwargs: Any) -> None:
        outbound.append(args)

    monkeypatch.setattr(main, "PLANS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(main, "fetch_and_save_plans_background", capture_background)

    resp = run_endpoint("/api/plans", _plans_request(brand))
    body = json.loads(bytes(resp.body))

    assert resp.status_code == 400
    assert body["status"] == "error"
    assert body["message"] == INVALID_BRAND_CODE
    assert body.get("code", INVALID_BRAND_CODE) == INVALID_BRAND_CODE
    assert outbound == []
    assert list(tmp_path.iterdir()) == []
    assert not sentinel.exists()
    if Path("/tmp").exists():
        assert {p.name for p in Path("/tmp").iterdir()} == outside_before


def test_plans_api_rejects_explicit_empty_brand_override(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Explicit brand= must not fall through to account brand resolution."""
    (tmp_path / "plans_THREE.json").write_text(
        json.dumps({"status": "success", "plans": [{"offerId": "should-not-read"}]}),
        encoding="utf-8",
    )

    resolver_calls: list[tuple[Any, ...]] = []
    cache_reads: list[Path] = []
    outbound: list[tuple[Any, ...]] = []

    def capture_resolver(*args: Any, **_kwargs: Any) -> str:
        resolver_calls.append(args)
        return "THREE"

    def capture_background(*args: Any, **_kwargs: Any) -> None:
        outbound.append(args)

    real_load = load_plans_from_cache

    def capture_load(cache_file: Path, **kwargs: Any) -> Any:
        cache_reads.append(cache_file)
        return real_load(cache_file, **kwargs)

    monkeypatch.setattr(main, "PLANS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(main, "get_brand_by_sub_id", capture_resolver)
    monkeypatch.setattr(main, "fetch_and_save_plans_background", capture_background)
    monkeypatch.setattr(
        "app.routes.commerce.load_plans_from_cache",
        capture_load,
    )

    resp = run_endpoint("/api/plans", _plans_request(""))
    body = json.loads(bytes(resp.body))

    assert resp.status_code == 400
    assert body == {"status": "error", "message": INVALID_BRAND_CODE}
    assert resolver_calls == []
    assert cache_reads == []
    assert outbound == []
    assert sorted(p.name for p in tmp_path.iterdir()) == ["plans_THREE.json"]


@pytest.mark.parametrize("brand", list(SUPPORTED_BRANDS))
def test_plans_api_accepts_all_supported_brands(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    brand: str,
) -> None:
    (tmp_path / f"plans_{brand}.json").write_text(
        json.dumps({"status": "success", "plans": [{"offerId": f"plan-{brand}"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "PLANS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(main, "fetch_and_save_plans_background", lambda *a, **k: None)

    resp = run_endpoint("/api/plans", _plans_request(brand))
    body = json.loads(bytes(resp.body))
    assert resp.status_code == 200
    assert body["status"] == "success"
    assert body["plans"] == [{"offerId": f"plan-{brand}"}]
