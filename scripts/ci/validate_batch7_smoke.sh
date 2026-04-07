#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 7 smoke validation bundle..."

bash scripts/ci/validate_onboarding_subscription.sh

echo "Batch 7 smoke validation bundle passed."
