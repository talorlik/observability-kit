#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 7 smoke validation bundle..."

bash scripts/ci/validate_multi_agent_scaffolding.sh

echo "Batch 7 smoke validation bundle passed."
