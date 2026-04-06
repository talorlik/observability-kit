#!/usr/bin/env bash

set -euo pipefail

SCHEMA="contracts/install/INSTALL_CONTRACT_SCHEMA.json"
VALID_GLOB="contracts/install/samples/valid/*.json"
INVALID_GLOB="contracts/install/samples/invalid/*.json"

echo "Validating install contract samples against schema..."
npx --yes ajv-cli validate \
  -s "$SCHEMA" \
  -d "$VALID_GLOB" \
  --spec=draft2020

echo "Ensuring invalid samples are rejected..."
set +e
npx --yes ajv-cli validate \
  -s "$SCHEMA" \
  -d "$INVALID_GLOB" \
  --spec=draft2020 >/dev/null 2>&1
invalid_status=$?
set -e

if [ "$invalid_status" -eq 0 ]; then
  echo "Expected invalid sample validation to fail, but it passed."
  exit 1
fi

echo "Install contract schema validation checks passed."
