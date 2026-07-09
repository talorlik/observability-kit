#!/usr/bin/env bash
#
# Batch 19 smoke wrapper: configuration rendering runtime.
#
# Aggregates the config renderer checks: the renderer architecture
# contract (obskit.configrender placement, stdlib-only core, lint-only
# requirements-ci.txt, ADR-0003 binding), strategy catalog coverage of
# the unified-config sample bindings, the offline renderer test suite
# (deterministic byte-identical rendering, generated-file header
# marker and commit trailers, render-idempotency --check, drift diff
# surface, rollback re-render), the real-CLI re-render and drift
# sweep on a scratch fixture tree, the dry-run rollback drill, and
# the seeded rejection-document sweep.
#
# Offline by design (TR-20 composed with TR-18): everything here runs
# against the recorded fixture tree under tests/configrender/fixtures/
# and never touches a live cluster or runs Git; live rendering
# evidence arrives with the Batch 23 harness and is never CI-gated.
#
# Cloud-agnostic: the renderer emits GitOps-only configuration for any
# conformant Kubernetes cluster; no provider-specific service is
# required.

set -euo pipefail

echo "Running Batch 19 (config renderer) smoke validation suite..."

bash scripts/ci/validate_config_renderer.sh

echo "Batch 19 smoke validation complete."
