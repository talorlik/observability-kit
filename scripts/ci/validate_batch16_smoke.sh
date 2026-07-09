#!/usr/bin/env bash
#
# Batch 16 smoke wrapper: unified configuration and management plane.
#
# Aggregates the management-plane contract checks: the wrapped-system
# registry with its seeded fork-method rejection fixtures, the unified
# configuration document with its propagation bindings and seeded
# unbound-key rejection fixtures, the propagation and reconciliation
# contract, and the single-pane access contract against the registry and
# the admin-access profile schema.
#
# Run separately from Batches 1-15 because the management plane wraps the
# systems those batches deliver: it layers one configuration and access
# surface over them without forking any of them (TR-17).
#
# Cloud-agnostic: every script invoked here validates only Kubernetes-resident
# components and contract artifacts.

set -euo pipefail

echo "Running Batch 16 (management plane) smoke validation suite..."

bash scripts/ci/validate_management_plane_contracts.sh

echo "Batch 16 smoke validation complete."
