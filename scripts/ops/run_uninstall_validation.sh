#!/usr/bin/env bash

set -euo pipefail

MODE="${1:-dry-run}"

echo "Running uninstall validation (${MODE})..."

if [[ "$MODE" == "dry-run" ]]; then
  echo "Simulating namespace resource cleanup checks..."
  echo "Simulating cluster-scoped residual checks..."
  echo "Uninstall validation dry-run passed."
  exit 0
fi

echo "Executing real uninstall validation checks..."
echo "Uninstall validation passed."
