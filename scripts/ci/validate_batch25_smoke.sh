#!/usr/bin/env bash
#
# Batch 25 smoke wrapper: release engineering.
#
# Repository-only and offline: validates the release engineering,
# license compliance, production reference architecture, and product
# SLO contracts, the tag-driven release workflow, the wrapped-system
# pin lockstep, the committed release-pins and upgrade-drill
# evidence, and the seeded rejection fixtures WITHOUT a cluster,
# kind, or Docker. The live checks themselves are manual through
# scripts/dev/live_cluster_harness.sh (checks release-pins,
# upgrade-drill) and are never part of pull-request gating (TR-25).

set -euo pipefail

echo "Running Batch 25 smoke validation (release engineering, offline)..."

bash scripts/ci/validate_release_engineering.sh

echo "Batch 25 smoke validation passed."
