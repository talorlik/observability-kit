#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 5 smoke validation bundle..."

bash scripts/ci/validate_ai_runtime_base_scaffolding.sh
bash scripts/ci/validate_logs_pipeline.sh

echo "Batch 5 smoke validation bundle passed."
