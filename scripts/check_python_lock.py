#!/usr/bin/env python3
"""Fail dependency PRs that change direct pins without updating the runtime lock."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1] / "backend"
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?==([^\s\\]+)", re.M)


def pins(filename: str) -> dict[str, str]:
    return {name.lower().replace("_", "-"): version for name, version in PIN.findall((ROOT / filename).read_text())}


def main() -> None:
    direct, locked = pins("requirements.txt"), pins("requirements.lock")
    missing = [name for name, version in direct.items() if locked.get(name) != version]
    if missing:
        raise SystemExit("runtime lock out of sync: " + ", ".join(sorted(missing)))
    print("python direct pins match runtime lock")


if __name__ == "__main__":
    main()
