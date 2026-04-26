#!/usr/bin/env bash
#
# Teardown the local Python venv created by setup_python_env.sh.
# Idempotent — safe to run when no venv exists.
#
# Use cases:
#   - Refreshing a stale local environment (e.g., after pip-conflict).
#   - Reclaiming disk space on a developer machine.
#   - Reproducible CI cleanup when running locally.
#
# Cloud-agnostic; touches only repo-local paths.

set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"

if [ -d "$VENV_DIR" ]; then
  # Try to deactivate any active venv first; ignore errors when none active.
  type deactivate >/dev/null 2>&1 && deactivate || true
  rm -rf "$VENV_DIR"
  echo "Removed Python virtual environment at $VENV_DIR."
else
  echo "No Python virtual environment at $VENV_DIR; nothing to remove."
fi

# Best-effort: clear pip's local wheel cache to free space. Pip cache lives
# outside the venv, so it survives venv removal otherwise.
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip cache purge >/dev/null 2>&1 || true
fi

echo "Python environment teardown complete."
