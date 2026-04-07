#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 9 smoke validation bundle..."

bash scripts/ci/validate_operator_experience_slo.sh

echo "Batch 9 smoke validation bundle passed."
