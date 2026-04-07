#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 12 smoke validation bundle..."

bash scripts/ci/validate_risk_scoring_assisted_rca.sh

echo "Batch 12 smoke validation bundle passed."
