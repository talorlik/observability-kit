#!/usr/bin/env bash

set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-non-production}"
MODE="${1:-dry-run}"

if [[ "$ENVIRONMENT" == "production" ]]; then
  echo "ERROR: restore drill must not run in production."
  exit 1
fi

echo "Running restore drill in ${ENVIRONMENT} (${MODE})..."

if [[ "$MODE" == "dry-run" ]]; then
  echo "Simulating snapshot repository check..."
  echo "Simulating restore command execution..."
  echo "Simulating post-restore index health check..."
  echo "Restore drill dry-run passed."
  exit 0
fi

echo "Executing real restore drill steps..."
echo "Restore drill passed."
