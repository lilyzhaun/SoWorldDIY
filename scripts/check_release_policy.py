#!/usr/bin/env python3
"""Reject production-deploy patterns in release workflows."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

from release_notes import extract_release_notes

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
RELEASE_NOTES_COMMAND: Final = "python3 scripts/release_notes.py"
RELEASE_NOTES_FIXTURE: Final = """# Changelog

## [Unreleased]
manual notes

## [1.2.3] - 2026-07-20
tag notes
"""

# Patterns that must never appear in release automation.
FORBIDDEN = [
    (re.compile(r"\bssh\b", re.I), "SSH"),
    (re.compile(r"\bscp\b", re.I), "SCP"),
    (re.compile(r"\bsystemctl\b", re.I), "SYSTEMCTL"),
    (re.compile(r"\bansible\b", re.I), "ANSIBLE"),
    (re.compile(r"\bkubectl\b", re.I), "KUBECTL"),
    (re.compile(r"\bhelm\s+upgrade\b", re.I), "HELM_UPGRADE"),
    (re.compile(r"production\s+url", re.I), "PRODUCTION_URL"),
    (re.compile(r"0\.0\.0\.0:\d+"), "PUBLIC_BIND"),
]


def main() -> int:
    paths = sorted(WORKFLOWS.glob("release*.yml")) + sorted(
        WORKFLOWS.glob("release*.yaml")
    )
    if not paths:
        print("ERROR: no release workflow found", file=sys.stderr)
        return 2

    violations: list[str] = []
    if (
        extract_release_notes(RELEASE_NOTES_FIXTURE, "refs/heads/main")
        != "manual notes"
    ):
        violations.append("release_notes_manual_selection")
    if extract_release_notes(RELEASE_NOTES_FIXTURE, "refs/tags/v1.2.3") != "tag notes":
        violations.append("release_notes_tag_selection")
    if extract_release_notes(RELEASE_NOTES_FIXTURE, "refs/tags/v9.9.9") is not None:
        violations.append("release_notes_missing_tag_section")

    for path in paths:
        text = path.read_text(encoding="utf-8")
        if RELEASE_NOTES_COMMAND not in text:
            violations.append(f"{path.relative_to(ROOT)}: RELEASE_NOTES_HELPER")
        for pattern, name in FORBIDDEN:
            if pattern.search(text):
                violations.append(f"{path.relative_to(ROOT)}: {name}")

    if violations:
        print("RELEASE_POLICY_VIOLATION")
        for item in violations:
            print(item, file=sys.stderr)
        return 1

    print("release policy ok (no deploy/SSH/systemctl patterns)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
