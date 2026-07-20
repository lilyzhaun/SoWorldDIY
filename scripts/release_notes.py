#!/usr/bin/env python3
"""Extract release notes for a branch dry-run or version tag."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

SECTION_PATTERN: Final = re.compile(
    r"^## \[(?P<section>[^]]+)]\s*\n(?P<body>.*?)(?=^## \[|\Z)",
    re.MULTILINE | re.DOTALL,
)


def section_name_for_ref(ref: str) -> str:
    tag_prefix = "refs/tags/v"
    if ref.startswith(tag_prefix):
        return ref.removeprefix(tag_prefix)
    return "Unreleased"


def extract_release_notes(changelog: str, ref: str) -> str | None:
    section_name = section_name_for_ref(ref)
    for match in SECTION_PATTERN.finditer(changelog):
        if match.group("section") == section_name:
            return match.group("body").strip()
    return None


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 3:
        print("usage: release_notes.py CHANGELOG REF OUTPUT", file=sys.stderr)
        return 2

    changelog_path = Path(arguments[0])
    ref = arguments[1]
    output_path = Path(arguments[2])
    notes = extract_release_notes(changelog_path.read_text(encoding="utf-8"), ref)
    if notes is None:
        print(
            f"missing_changelog_section: {section_name_for_ref(ref)}", file=sys.stderr
        )
        return 1

    output_path.write_text(notes + "\n", encoding="utf-8")
    print(f"release_notes_section={section_name_for_ref(ref)} notes_bytes={len(notes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
