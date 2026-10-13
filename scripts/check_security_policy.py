#!/usr/bin/env python3
"""Reject insecure tracked assets and workflow/deploy anti-patterns."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Final

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_TRACKED = [
    "backend/.env",
    "backend/app/request_overrides_local.py",
    "backend/requirements-local.txt",
    "frontend/dist",
    "deploy/compose/.env",
]

UNPINNED_ACTION = re.compile(
    r"^\s*-?\s*uses:\s*(?P<quote>['\"]?)(?P<ref>[^'\"\s#]+)(?P=quote)",
    re.M,
)
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
BASE_IMAGE = re.compile(r"^\s*FROM\s+(\S+)", re.M | re.I)
PUBLIC_BIND = re.compile(r"0\.0\.0\.0:(?!8888\b)\d+|0\.0\.0\.0:8888")
# Container CMD may bind 0.0.0.0 inside network namespace; host publish must be loopback.
COMPOSE_PUBLIC = re.compile(r'["\']0\.0\.0\.0:\d+:')
RELEASE_FORBIDDEN = re.compile(r"\b(ssh|scp|systemctl|ansible|kubectl)\b", re.I)
SENSITIVE_METRIC = re.compile(
    r"labelnames\s*=\s*\([^)]*(auth_code|password|token|secret)", re.I
)
PULL_REQUEST_TRIGGER: Final = re.compile(r"(?m)^\s{2}pull_request:\s*(?:#.*)?$")
GITLEAKS_ACTION: Final = re.compile(
    r"(?m)^\s*uses:\s*gitleaks/gitleaks-action@[0-9a-f]{40}\b"
)
PULL_REQUEST_READ: Final = re.compile(r"(?m)^\s+pull-requests:\s*read\s*(?:#.*)?$")


def _tracked_files() -> set[str]:
    out = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True)
    return {line.strip() for line in out.splitlines() if line.strip()}


def main() -> int:
    errors: list[str] = []
    tracked = _tracked_files()

    for path in FORBIDDEN_TRACKED:
        if path in tracked or any(
            t.startswith(path.rstrip("/") + "/") for t in tracked
        ):
            errors.append(f"tracked_local_secret_path: {path}")

    # Unpinned Actions
    workflows = ROOT / ".github" / "workflows"
    if workflows.is_dir():
        for path in sorted(workflows.glob("*.yml")) + sorted(workflows.glob("*.yaml")):
            text = path.read_text(encoding="utf-8")
            if (
                PULL_REQUEST_TRIGGER.search(text)
                and GITLEAKS_ACTION.search(text)
                and not PULL_REQUEST_READ.search(text)
            ):
                errors.append(f"missing_gitleaks_pull_request_permission: {path.name}")
            for match in UNPINNED_ACTION.finditer(text):
                ref = match.group("ref")
                if ref.startswith("./"):
                    continue
                if ref.startswith("docker://"):
                    if "@sha256:" not in ref:
                        errors.append(f"unpinned_docker_action: {path.name}: {ref}")
                    continue
                if not PINNED.match(ref):
                    errors.append(f"unpinned_action: {path.name}: {ref}")

    # Base images must be digest-pinned in Dockerfile
    dockerfile = ROOT / "Dockerfile"
    if dockerfile.is_file():
        text = dockerfile.read_text(encoding="utf-8")
        for match in BASE_IMAGE.finditer(text):
            image = match.group(1)
            if image.startswith("--") or image.upper() == "scratch":
                continue
            # multi-stage AS name: already captured full token before AS?
            image = image.split()[0]
            if "@sha256:" not in image:
                errors.append(f"unpinned_base_image: {image}")

    # Release workflow must not deploy
    for path in workflows.glob("release*.yml"):
        text = path.read_text(encoding="utf-8")
        if RELEASE_FORBIDDEN.search(text):
            errors.append(f"release_deploy_primitive: {path.name}")

    # Compose must not publish 0.0.0.0 host binds
    compose = ROOT / "docker-compose.yml"
    if compose.is_file():
        text = compose.read_text(encoding="utf-8")
        if COMPOSE_PUBLIC.search(text):
            errors.append("insecure_public_bind: docker-compose.yml")

    # Sensitive metric labels
    metrics = ROOT / "backend" / "app" / "metrics.py"
    if metrics.is_file() and SENSITIVE_METRIC.search(
        metrics.read_text(encoding="utf-8")
    ):
        errors.append("sensitive_metric_label: metrics.py")

    ignore = (ROOT / ".dockerignore").read_text().splitlines()
    if "**/.env" not in ignore or "**/.env.*" not in ignore:
        errors.append("nested_env_not_dockerignored")
    checks = (workflows / "checks.yml").read_text()
    if "npm run test:browser" not in checks:
        errors.append("browser_tests_not_in_ci")
    if re.search(r'exit-code:\s*[\'\"]?0\b', checks):
        errors.append("nonblocking_image_scan")

    ci = (workflows / "ci.yml").read_text()
    for context in ("backend", "frontend", "secret-scan", "trivy", "workflow-policy"):
        if not re.search(rf"(?m)^    name: {re.escape(context)}$", ci):
            errors.append(f"missing_protected_branch_status: {context}")

    if errors:
        print("SECURITY_POLICY_FAIL")
        for item in errors:
            print(item, file=sys.stderr)
        return 1

    print("security policy ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
