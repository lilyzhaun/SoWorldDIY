from __future__ import annotations

import argparse
import json

import redis

from .auth_code_keys import AuthCodeKeyMode
from .auth_codes import AuthCodeStore
from .config import Settings, load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Redis-backed auth codes")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create or update an auth code")
    create.add_argument("code")
    create.add_argument("--limit", type=int, required=True)
    create.add_argument("--used", type=int, default=0)

    sub.add_parser("list", help="List auth codes")

    revoke = sub.add_parser("revoke", help="Revoke an auth code")
    revoke.add_argument("code")

    sub.add_parser("seed", help="Import missing codes from backend/auth_codes.json")
    return parser


def build_store(settings: Settings) -> AuthCodeStore:
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    return AuthCodeStore(
        client,
        seed_file=settings.base_dir / "auth_codes.json",
        key_mode=settings.auth_code_key_mode,
        hmac_key=settings.auth_code_hmac_key,
    )


def main() -> None:
    args = build_parser().parse_args()
    settings = load_settings()
    store = build_store(settings)

    if args.command == "create":
        store.create(args.code, usage_limit=args.limit, times_used=args.used)
        if settings.auth_code_key_mode is AuthCodeKeyMode.LEGACY:
            payload: dict[str, object] = {"status": "ok", "code": args.code}
        else:
            payload = {"status": "ok", "fingerprint": store.fingerprint(args.code)}
        print(json.dumps(payload, ensure_ascii=False))
    elif args.command == "list":
        print(json.dumps(store.list_codes(), ensure_ascii=False, indent=2))
    elif args.command == "revoke":
        print(
            json.dumps(
                {"status": "ok", "deleted": store.revoke(args.code)}, ensure_ascii=False
            )
        )
    elif args.command == "seed":
        print(
            json.dumps(
                {"status": "ok", "imported": store.seed_from_file()}, ensure_ascii=False
            )
        )


if __name__ == "__main__":
    main()
