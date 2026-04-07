#!/usr/bin/env bash

set -euo pipefail

VENV_DIR="${VENV_DIR:-.venv}"
REQ_FILE="${REQ_FILE:-requirements-ci.txt}"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$REQ_FILE" >/dev/null

echo "Python virtual environment is ready at $VENV_DIR."
