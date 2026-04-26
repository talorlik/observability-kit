#!/usr/bin/env bash
#
# Batch 9A smoke wrapper.
#
# Note on the dual-directory layout: this wrapper invokes scripts from two
# top-level directories by design.
#
#   scripts/ci/        — bespoke contract / GitOps validators that are safe
#                        to run anywhere (no cluster, no GUI, no pod IP).
#                        These are what GitHub Actions and pre-merge CI run.
#   scripts/validate/  — runtime / smoke probes that need a real cluster or
#                        a running admin GUI to be meaningful (e.g.,
#                        admin_gui_smoke.sh probes TLS + login behavior of a
#                        deployed admin GUI; post_install_readiness.sh probes
#                        a live install). These are operator-driven.
#
# Batch 9A intentionally bridges the two: the contract validator stays in
# scripts/ci/, while the live-GUI smoke stays in scripts/validate/. See
# scripts/ci/README.md for the full rationale and the operator entry point.

set -euo pipefail

echo "Running Batch 9A smoke validation bundle..."

bash scripts/ci/validate_visualization_admin_access.sh
bash scripts/validate/admin_gui_smoke.sh

echo "Batch 9A smoke validation bundle passed."
