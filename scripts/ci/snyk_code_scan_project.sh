#!/usr/bin/env bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCAN_PATH="${1:-$PROJECT_ROOT}"
CACHE_DIR="$PROJECT_ROOT/.cache/snyk-cli"

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
mkdir -p "$CACHE_DIR"
export SNYK_CACHE_PATH="$CACHE_DIR"

check_auth() {
  if snyk whoami --experimental >/dev/null 2>&1; then
    return 0
  fi

  echo "ERROR: Snyk authentication is invalid or expired."
  echo "Run one of the following, then retry:"
  echo "  snyk auth"
  echo "  snyk auth <SNYK_API_TOKEN>"
  return 1
}

check_auth

run_snyk_scan() {
  local target_path="$1"
  set +e
  local output
  output="$(snyk code test "$target_path" 2>&1)"
  local exit_code=$?
  set -e
  printf "%s\n" "$output"
  return "$exit_code"
}

set +e
scan_output="$(run_snyk_scan "$ABS_SCAN_PATH")"
scan_exit=$?
set -e
printf "%s\n" "$scan_output"

if [ "$scan_exit" -eq 3 ] && [[ "$scan_output" == *"SNYK-CODE-0006"* ]]; then
  if [ "$ABS_SCAN_PATH" != "$PROJECT_ROOT" ]; then
    echo "No supported files found at $ABS_SCAN_PATH. Retrying at project root..."
    run_snyk_scan "$PROJECT_ROOT"
    exit $?
  fi
  echo "No supported Snyk Code file types found in project root."
  echo "Treating this as a pass for script-only changes."
  exit 0
fi

exit "$scan_exit"
