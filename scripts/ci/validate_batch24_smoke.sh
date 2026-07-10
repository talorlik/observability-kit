#!/usr/bin/env bash
#
# Batch 24 smoke wrapper: AI/MCP runtime activation.
#
# Repository-only and offline: validates the model-provider adapter
# contract, the runtime's embedded contract constants, the committed
# activation evidence (deployment, rehearsal, signoff), and the
# extended AI runbooks WITHOUT a cluster, kind, or Docker. The live
# activation itself is manual through
# scripts/dev/live_cluster_harness.sh (ai-deploy, ai-rehearsal,
# ai-signoff) and is never part of pull-request gating (TR-24).

set -euo pipefail

echo "Running Batch 24 smoke validation (AI activation, offline)..."

bash scripts/ci/validate_ai_activation.sh

echo "Batch 24 smoke validation passed."
