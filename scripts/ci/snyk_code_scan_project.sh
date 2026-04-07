#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCAN_PATH="${1:-$PROJECT_ROOT}"

if ! command -v snyk >/dev/null 2>&1; then
  echo "ERROR: snyk CLI is not installed or not on PATH."
  echo "Install from https://docs.snyk.io/snyk-cli/install-the-snyk-cli"
  exit 1
fi

if [ ! -e "$SCAN_PATH" ]; then
  echo "ERROR: Scan path does not exist: $SCAN_PATH"
  exit 1
fi

ABS_SCAN_PATH="$(cd "$SCAN_PATH" && pwd)"

case "$ABS_SCAN_PATH" in
  "$PROJECT_ROOT"|"$PROJECT_ROOT"/*)
    ;;
  *)
    echo "ERROR: Scan path must stay inside this project."
    echo "Project root: $PROJECT_ROOT"
    echo "Provided path: $ABS_SCAN_PATH"
    exit 1
    ;;
esac

echo "Running Snyk code scan for project path: $ABS_SCAN_PATH"
snyk code test "$ABS_SCAN_PATH"
