#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 4 smoke validation bundle..."

bash scripts/ci/validate_collector_core_topology.sh

echo "Batch 4 smoke validation bundle passed."
