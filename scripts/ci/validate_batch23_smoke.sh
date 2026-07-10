#!/usr/bin/env bash
#
# Batch 23 smoke wrapper: live-cluster validation and evidence.
#
# Repository-only and offline: validates the harness contract, the
# captured evidence tree, and the nightly workflow posture WITHOUT a
# cluster, kind, or Docker. The live run itself is manual or nightly
# through scripts/dev/live_cluster_harness.sh (TR-24) and is never
# part of pull-request gating.

set -euo pipefail

echo "Running Batch 23 smoke validation (live evidence, offline)..."

bash scripts/ci/validate_live_evidence.sh

echo "Batch 23 smoke validation passed."
