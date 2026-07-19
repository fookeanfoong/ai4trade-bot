#!/bin/bash
# SessionStart hook: install dependencies so builds/linters/tests work in
# Claude Code on the web sessions. Idempotent and non-interactive.
set -euo pipefail

# Only run in the remote (web) environment.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

ROOT="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# --- Python trading bot (repo root) ---
if [ -f "$ROOT/requirements.txt" ]; then
  echo "[session-start] installing Python dependencies..."
  pip install --quiet -r "$ROOT/requirements.txt" || true
fi

echo "[session-start] done."
