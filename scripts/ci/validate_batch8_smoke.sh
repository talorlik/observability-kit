#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 8 smoke validation bundle..."

bash scripts/ci/validate_khook_trigger_scaffolding.sh

echo "Batch 8 smoke validation bundle passed."
