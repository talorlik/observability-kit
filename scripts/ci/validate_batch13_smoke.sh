#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 13 smoke validation bundle..."

bash scripts/ci/validate_core_adapter_integrations.sh

echo "Batch 13 smoke validation bundle passed."
