"""DB0 migration helpers: DUMP/RESTORE session/cache; HMAC-rewrite auth codes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Protocol

from .auth_code_keys import (
    LEGACY_KEY_PREFIX,
    V2_KEY_PREFIX,
    is_legacy_redis_key,
    is_v2_redis_key,
    legacy_code_from_key,
    v2_redis_key,
)

SESSION_PREFIX = "session:"
CACHE_PREFIX = "cache:"
_PREFIX = {
    "session": SESSION_PREFIX,
    "cache": CACHE_PREFIX,
    "auth_legacy": LEGACY_KEY_PREFIX,
    "auth_v2": V2_KEY_PREFIX,
}


class MigrationRedisClient(Protocol):
    def scan_iter(self, match: str | None = None) -> Iterable[object]: ...
    def pttl(self, name: str) -> int: ...
    def dump(self, name: str) -> bytes | None: ...
    def restore(
        self, name: str, ttl: int, value: bytes, *, replace: bool = False
    ) -> object: ...
    def hgetall(self, name: str) -> Mapping[str, object]: ...
    def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: Mapping[str, object] | None = None,
    ) -> object: ...
    def exists(self, *names: str) -> int | bool: ...
    def get(self, name: str) -> bytes | None: ...
    def pexpire(self, name: str, ttl: int) -> object: ...


@dataclass(frozen=True)
class PlannedKey:
    kind: str
    source_key: str
    dest_key: str
    pttl_ms: int


@dataclass(frozen=True)
class MigrationPlan:
    session_count: int
    cache_count: int
    auth_legacy_count: int
    auth_v2_count: int
    items: tuple[PlannedKey, ...]

    def as_public_dict(self) -> dict[str, object]:
        """Counts/prefixes/TTLs only; never values or plaintext codes."""
        return {
            "session_count": self.session_count,
            "cache_count": self.cache_count,
            "auth_legacy_count": self.auth_legacy_count,
            "auth_v2_count": self.auth_v2_count,
            "prefixes": dict(_PREFIX),
            "keys": [
                {
                    "kind": i.kind,
                    "source_prefix": _PREFIX.get(i.kind, i.kind),
                    "dest_prefix": (
                        V2_KEY_PREFIX
                        if i.kind in {"auth_legacy", "auth_v2"}
                        else _PREFIX.get(i.kind, i.kind)
                    ),
                    "pttl_ms": i.pttl_ms,
                }
                for i in self.items
            ],
        }


def _scan_keys(client: MigrationRedisClient, match: str) -> list[str]:
    return sorted(str(key) for key in client.scan_iter(match=match))


def _safe_pttl(client: MigrationRedisClient, key: str) -> int:
    try:
        return int(client.pttl(key))
    except (TypeError, ValueError):
        return -1


def build_plan(source: MigrationRedisClient, *, hmac_key: bytes) -> MigrationPlan:
    items: list[PlannedKey] = []
    session_count = cache_count = auth_legacy_count = auth_v2_count = 0
    for key in _scan_keys(source, f"{SESSION_PREFIX}*"):
        session_count += 1
        items.append(PlannedKey("session", key, key, _safe_pttl(source, key)))
    for key in _scan_keys(source, f"{CACHE_PREFIX}*"):
        cache_count += 1
        items.append(PlannedKey("cache", key, key, _safe_pttl(source, key)))
    for key in _scan_keys(source, f"{LEGACY_KEY_PREFIX}*"):
        pttl_ms = _safe_pttl(source, key)
        if is_v2_redis_key(key):
            auth_v2_count += 1
            items.append(PlannedKey("auth_v2", key, key, pttl_ms))
        elif is_legacy_redis_key(key):
            dest = v2_redis_key(hmac_key, legacy_code_from_key(key))
            auth_legacy_count += 1
            items.append(PlannedKey("auth_legacy", key, dest, pttl_ms))
    return MigrationPlan(
        session_count=session_count,
        cache_count=cache_count,
        auth_legacy_count=auth_legacy_count,
        auth_v2_count=auth_v2_count,
        items=tuple(items),
    )


def _restore_binary(
    source: MigrationRedisClient, dest: MigrationRedisClient, item: PlannedKey
) -> None:
    payload = source.dump(item.source_key)
    if payload is None:
        raise RuntimeError(f"missing dump for {item.kind} key")
    remaining = _safe_pttl(source, item.source_key)
    if remaining == -2:
        raise RuntimeError("source key expired during migration")
    ttl = max(1, remaining) if remaining >= 0 else 0
    # Refuse to overwrite an independently populated destination.
    dest.restore(item.dest_key, ttl, payload, replace=False)


def _copy_auth_hash(
    source: MigrationRedisClient, dest: MigrationRedisClient, item: PlannedKey
) -> None:
    mapping = {str(k): str(v) for k, v in dict(source.hgetall(item.source_key)).items()}
    if not mapping:
        raise RuntimeError(f"empty auth hash for {item.kind}")
    if dest.exists(item.dest_key):
        raise RuntimeError("destination auth key already exists")
    dest.hset(item.dest_key, mapping=mapping)
    remaining = _safe_pttl(source, item.source_key)
    if remaining >= 0:
        dest.pexpire(item.dest_key, max(1, remaining))
    elif remaining == -2:
        raise RuntimeError("source auth key expired during migration")


def apply_plan(
    source: MigrationRedisClient, dest: MigrationRedisClient, plan: MigrationPlan
) -> dict[str, int]:
    copied = {"session": 0, "cache": 0, "auth_legacy": 0, "auth_v2": 0}
    for item in plan.items:
        if item.kind in {"session", "cache"}:
            _restore_binary(source, dest, item)
        elif item.kind in {"auth_legacy", "auth_v2"}:
            try:
                _copy_auth_hash(source, dest, item)
            except RuntimeError:
                if item.kind != "auth_v2":
                    raise
                _restore_binary(source, dest, item)
        else:
            raise RuntimeError(f"unknown plan kind {item.kind!r}")
        copied[item.kind] += 1
    return copied


def verify_plan(
    source: MigrationRedisClient,
    dest: MigrationRedisClient,
    plan: MigrationPlan,
    *,
    ttl_slack_ms: int = 5_000,
) -> dict[str, object]:
    mismatches: list[str] = []
    for item in plan.items:
        if not dest.exists(item.dest_key):
            mismatches.append(f"missing:{item.kind}")
            continue
        if item.kind in {"auth_legacy", "auth_v2"}:
            src = {
                str(k): str(v) for k, v in dict(source.hgetall(item.source_key)).items()
            }
            dst = {str(k): str(v) for k, v in dict(dest.hgetall(item.dest_key)).items()}
            if src != dst:
                mismatches.append(f"hash_mismatch:{item.kind}")
        else:
            # Project session/cache keys are strings. Compare GET values, not
            # DUMP bytes (RDB encodings may differ across Redis versions).
            if source.get(item.source_key) != dest.get(item.dest_key):
                mismatches.append(f"value_mismatch:{item.kind}")
        source_pttl = _safe_pttl(source, item.source_key)
        if source_pttl >= 0:
            dest_pttl = _safe_pttl(dest, item.dest_key)
            if dest_pttl < 0:
                mismatches.append(f"ttl_missing:{item.kind}")
            elif abs(dest_pttl - source_pttl) > ttl_slack_ms:
                mismatches.append(f"ttl_drift:{item.kind}")
        elif source_pttl == -2:
            mismatches.append(f"source_expired:{item.kind}")
        elif _safe_pttl(dest, item.dest_key) != -1:
            mismatches.append(f"unexpected_ttl:{item.kind}")
    return {
        "ok": not mismatches,
        "planned": len(plan.items),
        "mismatch_kinds": sorted(set(mismatches)),
        "mismatch_count": len(mismatches),
    }


def rollback_plan_public(
    *,
    old_redis_url_hint: str = "redis://127.0.0.1:6379/0",
    new_redis_url_hint: str = "redis://127.0.0.1:6380/0",
) -> dict[str, object]:
    """Document atomic REDIS_URL + AUTH_CODE_KEY_MODE rollback."""
    return {
        "before_old_key_deletion": {
            "steps": [
                "Stop app service",
                f"Set REDIS_URL back to old instance ({old_redis_url_hint})",
                "Set AUTH_CODE_KEY_MODE=legacy|dual",
                "Restart app service",
                "Verify health endpoints",
            ],
            "note": "Old DB0 project keys remain for the 24h retention window.",
        },
        "after_old_key_deletion": {
            "steps": [
                "Stop app service",
                "Restore DB0 project-key backup onto old Redis",
                f"Set REDIS_URL to {old_redis_url_hint}",
                "Set AUTH_CODE_KEY_MODE=legacy",
                "Restart app service",
                "Verify health endpoints",
            ],
            "note": "Never FLUSHDB/FLUSHALL; restore only project prefixes.",
        },
        "new_instance": new_redis_url_hint,
        "db15": "never inspect or mutate DB 15",
    }
