#!/usr/bin/env python3
"""Exercise ignored secrets and the shipped monitoring config with synthetic data."""

from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    subprocess.run(args, check=True, timeout=120, cwd=ROOT)


def main() -> None:
    base = Path(os.environ.get("TMPDIR", "/tmp/opencode"))
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="3hk-deploy-check-", dir=base) as directory:
        work = Path(directory)
        # The Prometheus image runs unprivileged; expose only synthetic fixtures.
        work.chmod(0o755)
        source = work / "context"
        source.mkdir()
        shutil.copyfile(ROOT / ".dockerignore", source / ".dockerignore")
        (source / "Dockerfile").write_text("FROM scratch\nCOPY . /\n", encoding="utf-8")
        for rel in (".env", "backend/.env", "deploy/compose/.env", "deep/.env.private"):
            path = source / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("AUDIT_SYNTHETIC_ONLY=true\n", encoding="utf-8")
        run(["docker", "buildx", "build", "--output", f"type=local,dest={work / 'output'}", str(source)])
        assert not list((work / "output").rglob(".env*")), "nested secrets entered the build context"

        entrypoint = (ROOT / "deploy/compose/prometheus-entrypoint.sh").read_text()
        config = entrypoint.split("<<YAML\n", 1)[1].split("\nYAML", 1)[0]
        (work / "prometheus.yml").write_text(config + "\n", encoding="utf-8")
        (work / "metrics_secret").write_text("audit-synthetic-only\n", encoding="utf-8")
        # Validate with the same upstream promtool version. The rebuilt image is
        # built and scanned separately by compose-scan in the shared workflow.
        image = re.search(r"FROM (prom/prometheus:\S+)", (ROOT / "deploy/monitoring/Dockerfile").read_text())
        assert image is not None
        run(["docker", "run", "--rm", "--network", "none", "--memory", "128m", "--pids-limit", "64", "--entrypoint", "/bin/promtool",
             "--mount", f"type=bind,src={work},dst=/audit,readonly",
             "--mount", f"type=bind,src={work / 'metrics_secret'},dst=/run/secrets/metrics_secret,readonly",
             "--mount", f"type=bind,src={ROOT / 'deploy/monitoring/alerts.yml'},dst=/etc/prometheus/alerts.yml,readonly",
             image.group(1), "check", "config", "/audit/prometheus.yml"])
        print("deployment checks ok (synthetic data only)")


if __name__ == "__main__":
    main()
