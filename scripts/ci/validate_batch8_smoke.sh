#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 8 smoke validation bundle..."

bash scripts/ci/validate_security_isolation_resilience.sh

echo "Batch 8 smoke validation bundle passed."
