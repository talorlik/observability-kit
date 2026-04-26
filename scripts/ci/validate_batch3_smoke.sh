#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 3 smoke validation bundle..."

bash scripts/ci/validate_ai_state_contracts.sh
bash scripts/ci/validate_compatibility_and_modes.sh
bash scripts/ci/validate_preflight_and_discovery.sh

echo "Batch 3 smoke validation bundle passed."
