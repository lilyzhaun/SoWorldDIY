"""CLI: ``python -m app.redis_migrate {plan|apply|verify|rollback-plan}``.

Sanitized JSON only — never prints Redis passwords, auth codes, or key values.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from typing import TextIO
from urllib.parse import parse_qs, urlsplit, urlunsplit

import redis

from .auth_code_keys import parse_auth_code_hmac_key
from .redis_migrate_core import (
    apply_plan,
    build_plan,
    rollback_plan_public,
    verify_plan,
)


def _redact_redis_url(url: str) -> str:
    parts = urlsplit(url)
    if not parts.password and "@" not in (parts.netloc or ""):
        return url
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    user = parts.username or ""
    netloc = f"{user}:***@{host}" if user else f"***@{host}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--source-url",
        default=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        help="Source Redis URL (DB0 project data only)",
    )
    parser.add_argument(
        "--dest-url",
        default=os.environ.get("REDIS_MIGRATE_DEST_URL", "redis://127.0.0.1:6380/0"),
        help="Destination dedicated Redis URL",
    )
    parser.add_argument(
        "--hmac-key",
        default=os.environ.get("AUTH_CODE_HMAC_KEY"),
        help="AUTH_CODE_HMAC_KEY (≥32 bytes); never printed",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate 3HK project keys from shared Redis DB0 to a dedicated instance"
        )
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("plan", "Inventory source keys (counts/prefixes/TTLs only)"),
        ("apply", "Copy planned keys into destination"),
        ("verify", "Verify destination matches plan"),
        (
            "rollback-plan",
            "Print atomic REDIS_URL + AUTH_CODE_KEY_MODE rollback steps",
        ),
    ):
        child = sub.add_parser(name, help=help_text)
        _add_common(child)
    return parser


def _connect(url: str) -> redis.Redis:
    parts = urlsplit(url)
    if parts.path not in {"", "/", "/0"} or any(
        db != "0" for db in parse_qs(parts.query).get("db", [])
    ):
        raise SystemExit("Migration is restricted to DB 0")
    return redis.Redis.from_url(
        url, decode_responses=False, socket_connect_timeout=3, socket_timeout=3
    )


def _require_hmac(raw: str | None) -> bytes:
    try:
        return parse_auth_code_hmac_key(raw)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


class _DecodeHashProxy:
    """Adapt binary redis-py client to the migration Protocol."""

    def __init__(self, client: redis.Redis) -> None:
        self._c = client

    def scan_iter(self, match: str | None = None) -> list[str]:
        raw = (
            self._c.scan_iter(match=match) if match is not None else self._c.scan_iter()
        )
        out: list[str] = []
        for key in raw:
            out.append(key.decode("utf-8") if isinstance(key, bytes) else str(key))
        return out

    def pttl(self, name: str) -> int:
        result = self._c.pttl(name)
        if isinstance(result, bool):
            return int(result)
        if isinstance(result, int):
            return result
        raise TypeError(f"redis PTTL returned unexpected type {type(result)!r}")

    def dump(self, name: str) -> bytes | None:
        result = self._c.dump(name)
        if result is None:
            return None
        if isinstance(result, bytes):
            return result
        raise TypeError("redis DUMP returned non-bytes")

    def restore(
        self,
        name: str,
        ttl: int,
        value: bytes,
        *,
        replace: bool = False,
    ) -> object:
        if replace:
            return self._c.restore(name, ttl, value, replace=True)
        return self._c.restore(name, ttl, value)

    def hgetall(self, name: str) -> dict[str, str]:
        raw = self._c.hgetall(name)
        if not isinstance(raw, dict):
            raise TypeError("redis HGETALL returned unexpected type")
        out: dict[str, str] = {}
        for field, value in raw.items():
            fk = field.decode("utf-8") if isinstance(field, bytes) else str(field)
            fv = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            out[fk] = fv
        return out

    def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: Mapping[str, object] | None = None,
    ) -> object:
        if mapping is not None:
            encoded = {
                str(k).encode("utf-8"): str(v).encode("utf-8")
                for k, v in mapping.items()
            }
            return self._c.hset(name, mapping=encoded)
        if key is None or value is None:
            raise TypeError("hset requires key/value or mapping")
        return self._c.hset(name, key, value)

    def exists(self, *names: str) -> int | bool:
        result = self._c.exists(*names)
        if isinstance(result, bool):
            return result
        if isinstance(result, int):
            return result
        raise TypeError(f"redis EXISTS returned unexpected type {type(result)!r}")

    def get(self, name: str) -> bytes | None:
        result = self._c.get(name)
        if result is None or isinstance(result, bytes):
            return result
        raise TypeError("redis GET returned non-bytes")

    def pexpire(self, name: str, ttl: int) -> object:
        return self._c.pexpire(name, ttl)


def run(argv: list[str] | None = None, out: TextIO | None = None) -> int:
    stream = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    if args.command == "rollback-plan":
        payload = rollback_plan_public(
            old_redis_url_hint=_redact_redis_url(args.source_url),
            new_redis_url_hint=_redact_redis_url(args.dest_url),
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream)
        return 0

    hmac_key = _require_hmac(args.hmac_key)
    source = _DecodeHashProxy(_connect(args.source_url))
    dest = _DecodeHashProxy(_connect(args.dest_url))
    plan = build_plan(source, hmac_key=hmac_key)

    if args.command == "plan":
        print(
            json.dumps(plan.as_public_dict(), ensure_ascii=False, indent=2),
            file=stream,
        )
        return 0

    if args.command == "apply":
        counts = apply_plan(source, dest, plan)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "copied": counts,
                    "source": _redact_redis_url(args.source_url),
                    "dest": _redact_redis_url(args.dest_url),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=stream,
        )
        return 0

    if args.command == "verify":
        result = verify_plan(source, dest, plan)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=stream)
        return 0 if result.get("ok") else 1

    raise SystemExit(f"unknown command {args.command!r}")


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
