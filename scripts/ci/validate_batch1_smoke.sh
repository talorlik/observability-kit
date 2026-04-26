#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 1 smoke validation bundle..."

bash scripts/ci/validate_ai_boundary_contracts.sh
bash scripts/ci/validate_install_contract.sh
bash scripts/ci/validate_gitops_structure.sh
bash scripts/ci/validate_stub_renders.sh
bash scripts/ci/validate_seeded_rejection_checks.sh
bash scripts/ci/check_no_hardcoded_env_values.sh
bash scripts/ci/validate_runbook_links.sh

echo "Batch 1 smoke validation bundle passed."
