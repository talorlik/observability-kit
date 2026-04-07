#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 6 smoke validation bundle..."

bash scripts/ci/validate_metrics_traces_pipeline.sh

echo "Batch 6 smoke validation bundle passed."
