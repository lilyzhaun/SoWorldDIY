#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${VENV_DIR:-$SCRIPT_DIR/.venv}"
UVICORN_BIN="$VENV_DIR/bin/uvicorn"

if [[ ! -x "$UVICORN_BIN" ]]; then
  echo "Missing uvicorn in $VENV_DIR. Run: cd $SCRIPT_DIR && python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

cd "$SCRIPT_DIR"
# Default to loopback; override with HOST/PORT for local multi-interface debugging.
exec "$UVICORN_BIN" run:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
