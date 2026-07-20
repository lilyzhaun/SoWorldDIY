#!/usr/bin/env bash
# Stage tracked application files into a deployment root (default /opt/3hk-new).
# Preserves ignored local files: backend/.env, request_overrides_local.py,
# requirements-local.txt (byte-for-byte when present).
# Merges unknown keys from an existing destination .env into the staged copy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST_ROOT="${DEST_ROOT:-/opt/3hk-new}"
STAGE_ROOT="${STAGE_ROOT:-}"
DRY_RUN="${DRY_RUN:-0}"

LOCAL_FILES=(
  "backend/.env"
  "backend/app/request_overrides_local.py"
  "backend/requirements-local.txt"
)

usage() {
  cat <<USAGE
Usage: DEST_ROOT=/path scripts/deploy_sync.sh [--dry-run]

Stages tracked sources into DEST_ROOT without deleting preserved local files.
Environment:
  DEST_ROOT   Final install root (default: /opt/3hk-new)
  STAGE_ROOT  Optional staging directory (default: mktemp under /tmp)
  DRY_RUN=1   Plan only; print actions without writing DEST_ROOT
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

log() { printf '%s\n' "$*"; }

# Merge .env: keep destination-only keys (unknown to source) so local secrets survive.
merge_env_preserve_unknown() {
  local src="$1"
  local dst="$2"
  local out="$3"
  python3 - "$src" "$dst" "$out" <<'PY'
import sys
from pathlib import Path

src_path, dst_path, out_path = map(Path, sys.argv[1:4])

def parse(path: Path) -> tuple[list[str], dict[str, str]]:
    order: list[str] = []
    values: dict[str, str] = {}
    if not path.exists():
        return order, values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            order.append(line)
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not key:
            order.append(line)
            continue
        if key not in values:
            order.append(f"__KEY__{key}")
        values[key] = val
    return order, values

src_order, src_vals = parse(src_path)
dst_order, dst_vals = parse(dst_path)

# Source keys win for overlapping names; destination-only keys appended.
out_lines: list[str] = []
seen: set[str] = set()
for item in src_order:
    if item.startswith("__KEY__"):
        key = item.removeprefix("__KEY__")
        out_lines.append(f"{key}={src_vals[key]}")
        seen.add(key)
    else:
        out_lines.append(item)
for key, val in dst_vals.items():
    if key not in seen:
        out_lines.append(f"{key}={val}")
        seen.add(key)

out_path.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
PY
}

if [[ -z "$STAGE_ROOT" ]]; then
  STAGE_ROOT="$(mktemp -d /tmp/3hk-deploy-stage.XXXXXX)"
  CLEAN_STAGE=1
else
  CLEAN_STAGE=0
  mkdir -p "$STAGE_ROOT"
fi

log "repo=$REPO_ROOT"
log "dest=$DEST_ROOT"
log "stage=$STAGE_ROOT"
log "dry_run=$DRY_RUN"

# 1) Stage tracked tree (exclude venv, caches, secrets, git, omo)
rsync -a \
  --delete \
  --exclude 'AGENTS.md' \
  --exclude '.git/' \
  --exclude '.omo/' \
  --exclude '.venv/' \
  --exclude 'venv/' \
  --exclude 'node_modules/' \
  --exclude '__pycache__/' \
  --exclude '.pytest_cache/' \
  --exclude '.ruff_cache/' \
  --exclude '.mypy_cache/' \
  --exclude 'backend/.env' \
  --exclude 'backend/auth_codes.json' \
  --exclude 'backend/app/request_overrides_local.py' \
  --exclude 'backend/requirements-local.txt' \
  --exclude 'frontend/node_modules/' \
  --exclude '**/*.pyc' \
  "$REPO_ROOT/" "$STAGE_ROOT/"

# 2) Preserve local files from DEST if present; otherwise seed from repo when present
for rel in "${LOCAL_FILES[@]}"; do
  if [[ -e "$DEST_ROOT/$rel" ]]; then
    mkdir -p "$(dirname "$STAGE_ROOT/$rel")"
    cp -a "$DEST_ROOT/$rel" "$STAGE_ROOT/$rel"
    log "preserve $rel (byte-for-byte from dest)"
  elif [[ -e "$REPO_ROOT/$rel" ]]; then
    mkdir -p "$(dirname "$STAGE_ROOT/$rel")"
    cp -a "$REPO_ROOT/$rel" "$STAGE_ROOT/$rel"
    log "seed $rel (from repo local copy)"
  else
    log "missing_in_dest $rel (not created)"
  fi
done

# Optional: if both example and dest .env exist, also ensure dest-only keys remain
# (already preserved byte-for-byte above). Document merge helper for upgrades:
if [[ -f "$DEST_ROOT/backend/.env" && -f "$REPO_ROOT/.env.example" && "${MERGE_ENV:-0}" == "1" ]]; then
  merge_env_preserve_unknown "$REPO_ROOT/.env.example" "$DEST_ROOT/backend/.env" "$STAGE_ROOT/backend/.env.merged"
  mv "$STAGE_ROOT/backend/.env.merged" "$STAGE_ROOT/backend/.env"
  log "merge_env applied (MERGE_ENV=1)"
fi

if [[ "$DRY_RUN" == "1" ]]; then
  log "dry_run complete; stage left at $STAGE_ROOT"
  exit 0
fi

# 3) Promote stage -> dest. Delete stale source files while protecting runtime state.
mkdir -p "$DEST_ROOT"
rsync -a \
  --delete \
  --exclude 'backend/.env' \
  --exclude 'backend/auth_code.txt' \
  --exclude 'backend/auth_codes.json' \
  --exclude 'backend/.venv/' \
  --exclude 'backend/app/request_overrides_local.py' \
  --exclude 'backend/plans_cache/*.json' \
  --exclude 'backend/requirements-local.txt' \
  --exclude 'frontend/node_modules/' \
  "$STAGE_ROOT/" "$DEST_ROOT/"

# Ensure plans_cache exists and is writable by service group later (task 10)
mkdir -p "$DEST_ROOT/backend/plans_cache"

log "sync_complete dest=$DEST_ROOT"

if [[ "$CLEAN_STAGE" == "1" ]]; then
  rm -rf "$STAGE_ROOT"
fi
