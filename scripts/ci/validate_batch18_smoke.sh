#!/usr/bin/env bash
#
# Batch 18 smoke wrapper: guided installation experience.
#
# Aggregates the guided installer checks: the install flow contract
# (fixed seven-step order, ADR-0002 binding), the offline installer
# test suite (interactive/non-interactive wizard parity, install
# contract schema validation, idempotent and resumable flow,
# byte-identical GitOps-only rendering, readiness finalization), and
# the seeded invalid-answers rejection sweep through the real CLI.
#
# Offline by design (TR-19 composed with TR-18): everything here runs
# against recorded cluster snapshots; live install evidence arrives
# with the Batch 23 harness and is never CI-gated.
#
# Cloud-agnostic: the installer targets any conformant Kubernetes
# cluster; no provider-specific service is required.

set -euo pipefail

echo "Running Batch 18 (guided installer) smoke validation suite..."

bash scripts/ci/validate_guided_installer.sh

echo "Batch 18 smoke validation complete."
