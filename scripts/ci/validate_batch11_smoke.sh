#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 11 smoke validation bundle..."

bash scripts/ci/validate_graph_foundation.sh

echo "Batch 11 smoke validation bundle passed."
