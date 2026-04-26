#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 10 smoke validation bundle..."

bash scripts/ci/validate_kagent_khook_release.sh

echo "Batch 10 smoke validation bundle passed."
