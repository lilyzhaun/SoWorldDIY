#!/usr/bin/env python3
"""Compare documented env/routes/commands against live config, OpenAPI, and manifests."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

# Documented Settings-facing env names (must match .env.example + docs).
DOCUMENTED_ENV = {
    "SESSION_SECRET",
    "PASSWORD_ENCRYPTION_KEY",
    "REDIS_URL",
    "REDIS_MIGRATE_DEST_URL",
    "REDIS_SESSION_PREFIX",
    "PROXY_URL",
    "CMN_PROXY_URL",
    "COOKIE_SECURE",
    "AUTH_CODE_KEY_MODE",
    "AUTH_CODE_HMAC_KEY",
    "TRUSTED_PROXY_IPS",
    "METRICS_SECRET",
    "RATE_LIMIT_CHECK_USER_IP",
    "RATE_LIMIT_CHECK_USER_WINDOW",
    "RATE_LIMIT_SEND_OTP_ID",
    "RATE_LIMIT_SEND_OTP_ID_WINDOW",
    "RATE_LIMIT_SEND_OTP_IP",
    "RATE_LIMIT_SEND_OTP_IP_WINDOW",
    "RATE_LIMIT_LOGIN_IP",
    "RATE_LIMIT_LOGIN_IP_WINDOW",
    "RATE_LIMIT_LOGIN_FAIL_ID",
    "RATE_LIMIT_LOGIN_FAIL_ID_WINDOW",
}

# Required Settings keys that must appear in .env.example (commented or active).
REQUIRED_SETTINGS_ENV = {
    "SESSION_SECRET",
    "REDIS_URL",
    "COOKIE_SECURE",
    "AUTH_CODE_KEY_MODE",
    "METRICS_SECRET",
}

FORBIDDEN_CLONE = re.compile(r"your-org", re.I)
ENV_LINE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=")
ROUTE_DOC = re.compile(
    r"`((?:GET|POST|PUT|PATCH|DELETE)\s+/[A-Za-z0-9_{}/.-]*)`",
    re.I,
)


def _load_env_example_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        m = ENV_LINE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def _frontend_scripts() -> set[str]:
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    return set(pkg.get("scripts", {}))


def _openapi_methods() -> dict[str, set[str]]:
    # Ensure required env for Settings import during check.
    os.environ.setdefault("SESSION_SECRET", "docs-check-secret")
    os.environ.setdefault("COOKIE_SECURE", "false")
    os.environ.setdefault("METRICS_SECRET", "docs-check-metrics")
    os.environ.setdefault("AUTH_CODE_KEY_MODE", "legacy")
    # Prefer backend virtualenv so FastAPI/redis deps resolve.
    venv_site = BACKEND / ".venv" / "lib"
    if venv_site.is_dir():
        for candidate in sorted(venv_site.glob("python*/site-packages")):
            sys.path.insert(0, str(candidate))
    sys.path.insert(0, str(BACKEND))
    from app.main import create_app  # noqa: WPS433

    schema = create_app().openapi()
    out: dict[str, set[str]] = {}
    for path, ops in schema.get("paths", {}).items():
        out[path] = {m.lower() for m in ops if m.lower() in {"get", "post", "put", "patch", "delete"}}
    return out


def main() -> int:
    errors: list[str] = []

    env_example = ROOT / ".env.example"
    if not env_example.is_file():
        errors.append("missing .env.example")
        print("\n".join(errors), file=sys.stderr)
        return 1

    example_keys = _load_env_example_keys(env_example)
    for key in sorted(REQUIRED_SETTINGS_ENV):
        if key not in example_keys:
            errors.append(f"env.example missing required Settings key: {key}")

    # Documented rate-limit / auth / metrics knobs should appear in example when documented.
    for key in sorted(DOCUMENTED_ENV):
        if key.startswith("RATE_LIMIT_") or key in {
            "AUTH_CODE_HMAC_KEY",
            "REDIS_MIGRATE_DEST_URL",
            "TRUSTED_PROXY_IPS",
            "CMN_PROXY_URL",
            "PROXY_URL",
            "PASSWORD_ENCRYPTION_KEY",
        }:
            # optional keys may be commented; still require presence as a line
            if key not in example_keys:
                errors.append(f"env.example missing documented key: {key}")

    # Clone URL must not use your-org placeholder.
    for rel in ("README.md", "docs/02-setup.md"):
        path = ROOT / rel
        if path.is_file() and FORBIDDEN_CLONE.search(path.read_text(encoding="utf-8")):
            errors.append(f"clone_url_placeholder: {rel} contains your-org")

    # Package scripts referenced in docs/CONTRIBUTING must exist.
    scripts = _frontend_scripts()
    required_scripts = {
        "build",
        "lint",
        "typecheck",
        "test",
        "test:coverage",
        "format:check",
    }
    for name in sorted(required_scripts):
        if name not in scripts:
            errors.append(f"frontend script missing: {name}")

    # Documented HTTP routes must exist in OpenAPI with matching method.
    openapi = _openapi_methods()
    doc_text = "\n".join(
        (ROOT / rel).read_text(encoding="utf-8")
        for rel in (
            "docs/05-api-reference.md",
            "docs/04-entrypoints.md",
            "docs/09-security-and-operations.md",
        )
        if (ROOT / rel).is_file()
    )
    for match in ROUTE_DOC.finditer(doc_text):
        method, path = match.group(1).split(None, 1)
        method = method.lower()
        path = path.split("?")[0]
        # Normalize path params like {account_id}
        if path not in openapi:
            # allow prefix match for templated docs
            if not any(path == p or path.rstrip("/") == p.rstrip("/") for p in openapi):
                errors.append(f"documented_route_missing: {method.upper()} {path}")
                continue
        methods = openapi.get(path) or next(
            (openapi[p] for p in openapi if path.rstrip("/") == p.rstrip("/")),
            set(),
        )
        if method not in methods:
            errors.append(f"documented_method_mismatch: {method.upper()} {path} (have {sorted(methods)})")

    # Critical routes must be present.
    for path, method in (
        ("/_health", "get"),
        ("/_ready", "get"),
        ("/metrics", "get"),
        ("/login", "post"),
        ("/logout", "post"),
        ("/api/check-user", "post"),
        ("/api/send-otp", "post"),
    ):
        if path not in openapi or method not in openapi[path]:
            errors.append(f"openapi_missing_critical: {method.upper()} {path}")

    if errors:
        print("DOCS_CONSISTENCY_FAIL")
        for item in errors:
            print(item, file=sys.stderr)
        return 1

    print("docs consistency ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
