from __future__ import annotations

from collections import UserDict
from types import SimpleNamespace
from typing import Any

import pytest
from pytest import MonkeyPatch

from app import request_overrides


def _patch_local(
    monkeypatch: MonkeyPatch,
    resolver: Any,
) -> None:
    monkeypatch.setattr(
        request_overrides.importlib,
        "import_module",
        lambda name, package=None: SimpleNamespace(resolve_proxies=resolver),
    )


def test_resolve_proxies_returns_default_identity_when_local_absent(
    monkeypatch: MonkeyPatch,
) -> None:
    default = {"http": "https://proxy.local"}

    def missing_module(name: str, package: str | None = None) -> object:
        raise ModuleNotFoundError(
            f"No module named '{package}.request_overrides_local'",
            name=f"{package}.request_overrides_local",
        )

    monkeypatch.setattr(request_overrides.importlib, "import_module", missing_module)

    assert request_overrides.resolve_proxies("https://example.test", default) is default
    assert request_overrides.resolve_proxies("https://example.test", None) is None


def test_resolve_proxies_preserves_dict_identity_from_local_override(
    monkeypatch: MonkeyPatch,
) -> None:
    expected = {"http": "https://local-proxy", "https": "https://local-proxy"}
    _patch_local(monkeypatch, lambda url, default: expected)

    result = request_overrides.resolve_proxies("https://example.test", {"http": "x"})
    assert result is expected


def test_resolve_proxies_normalizes_non_dict_mapping_from_local_override(
    monkeypatch: MonkeyPatch,
) -> None:
    mapping = UserDict({"http": "https://mapped-proxy"})
    _patch_local(monkeypatch, lambda url, default: mapping)

    result = request_overrides.resolve_proxies("https://example.test", None)
    assert result == {"http": "https://mapped-proxy"}
    assert isinstance(result, dict)
    assert result is not mapping


def test_resolve_proxies_returns_none_from_local_override(
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_local(monkeypatch, lambda url, default: None)
    assert (
        request_overrides.resolve_proxies("https://example.test", {"http": "x"}) is None
    )


def test_resolve_proxies_rejects_invalid_local_return(
    monkeypatch: MonkeyPatch,
) -> None:
    _patch_local(monkeypatch, lambda url, default: "not-a-mapping")

    with pytest.raises(TypeError, match="Mapping\\[str, str\\] \\| None"):
        request_overrides.resolve_proxies("https://example.test", {})


def test_resolve_proxies_rejects_non_callable_local_resolver(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        request_overrides.importlib,
        "import_module",
        lambda name, package=None: SimpleNamespace(resolve_proxies=None),
    )

    with pytest.raises(TypeError, match="callable resolve_proxies"):
        request_overrides.resolve_proxies("https://example.test", {})
