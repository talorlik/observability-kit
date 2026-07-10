#!/usr/bin/env bash
#
# Batch 27 smoke wrapper: demo workloads and observability playground.
#
# Repository-only and offline: validates the demo package under
# demo/, the scenario contract and its seeded samples, the demo
# dashboards, the AI prompt pack, the offline demo tests, and the
# playground guide and runbook registration WITHOUT a cluster, kind,
# or Docker. Nothing here deploys or probes a runtime; the demo
# package is validated structurally with the same gating discipline
# as the platform itself (TR-27, ADR-0011).

set -euo pipefail

echo "Running Batch 27 smoke validation (demo playground, offline)..."

bash scripts/ci/validate_demo_playground.sh

echo "Batch 27 smoke validation passed."
