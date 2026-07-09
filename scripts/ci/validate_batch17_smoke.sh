#!/usr/bin/env bash
#
# Batch 17 smoke wrapper: discovery and preflight execution engine.
#
# Aggregates the discovery executor checks: the executor architecture
# contract (read-only cluster access, stdlib-only core, lint-only
# requirements-ci.txt) and the offline fixture-driven test suite for
# the obskit CLI - preflight check classes, discovery probe groups,
# schema conformance of both reports, the four derived evaluation
# artifacts with contract-exact grading and mode decisions, TR-18
# byte-identical determinism, and the lazy-import / RBAC / grading
# drift boundary guards.
#
# Offline by design (TR-18): everything here runs against recorded
# cluster snapshots under tests/executor/fixtures/. The live kind
# integration probe is scripts/validate/discovery_executor_kind_integration.sh
# and is never CI-gated.
#
# Cloud-agnostic: the executor reads any conformant Kubernetes cluster;
# no provider-specific service is required.

set -euo pipefail

echo "Running Batch 17 (discovery executor) smoke validation suite..."

bash scripts/ci/validate_discovery_executor.sh

echo "Batch 17 smoke validation complete."
