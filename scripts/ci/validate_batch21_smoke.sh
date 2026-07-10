#!/usr/bin/env bash
#
# Batch 21 smoke wrapper: unified management portal.
#
# Aggregates the portal checks: the offline portal test suites (UI
# catalog aggregation over the single-pane access contract, the
# Git-commit-only config edit flow through the TR-20 renderer,
# server-rendered views, SSO role mapping from the admin access plane
# groups, TR-16 tenant scoping), the wrap-not-fork and GitOps-only
# source guards, the portal contract's structural validation, and the
# mechanical cross-contract enforcement of its consistency_policy
# (control plane delegation by operationId, catalog reachability,
# route parity against the FastAPI adapter, the admin-access profile
# `portal` endpoint key) with seeded rejection evidence.
#
# Offline by design (TB-21 composed with TR-17 and TR-22): everything
# here runs against repository files and temp directories; the portal
# never touches a live cluster in CI, and live portal endpoint
# evidence arrives with scripts/validate/admin_gui_smoke.sh
# (operator-run, never CI-gated).
#
# Cloud-agnostic: the portal wraps the cataloged UIs of any
# conformant Kubernetes cluster, authenticates only through the admin
# access plane, and writes configuration only through the GitOps
# render path; no provider-specific service is required.

set -euo pipefail

echo "Running Batch 21 (management portal) smoke validation suite..."

bash scripts/ci/validate_portal_contracts.sh

echo "Batch 21 smoke validation complete."
