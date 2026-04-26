#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 2 smoke validation bundle..."

bash scripts/ci/validate_ai_governance_contracts.sh
bash scripts/ci/validate_compatibility_and_modes.sh

echo "Batch 2 smoke validation bundle passed."
