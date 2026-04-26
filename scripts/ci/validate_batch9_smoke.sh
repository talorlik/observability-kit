#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 9 smoke validation bundle..."

bash scripts/ci/validate_action_gate_scaffolding.sh

echo "Batch 9 smoke validation bundle passed."
