#!/usr/bin/env python3
"""Fail if any workflow uses a third-party Action without a 40-hex commit SHA pin."""

from __future__ import annotations

import re
import sys
from pathlib import Path

USES_RE = re.compile(
    r"^\s*-?\s*uses:\s*(?P<quote>['\"]?)(?P<ref>[^'\"\s#]+)(?P=quote)",
    re.MULTILINE,
)
# owner/name@40hex
PINNED_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}$")
# local actions are allowed
LOCAL_RE = re.compile(r"^\./")
# docker:// images are not GitHub Actions marketplace refs; still require digest when used
DOCKER_RE = re.compile(r"^docker://")

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def main() -> int:
    if not WORKFLOWS.is_dir():
        print("ERROR: .github/workflows missing", file=sys.stderr)
        return 2

    violations: list[str] = []
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        text = path.read_text(encoding="utf-8")
        for match in USES_RE.finditer(text):
            ref = match.group("ref")
            if LOCAL_RE.match(ref):
                continue
            if DOCKER_RE.match(ref):
                if "@sha256:" not in ref:
                    violations.append(f"{path.relative_to(ROOT)}: unpinned docker action {ref}")
                continue
            if not PINNED_RE.match(ref):
                violations.append(f"{path.relative_to(ROOT)}: unpinned action {ref}")

    if violations:
        print("UNPINNED_ACTION")
        for item in violations:
            print(item, file=sys.stderr)
        return 1

    print("all workflow actions pinned to 40-hex SHAs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
