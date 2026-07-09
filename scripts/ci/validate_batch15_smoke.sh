#!/usr/bin/env bash
#
# Batch 15 smoke wrapper: SaaS multi-tenancy and customer isolation.
#
# Aggregates the tenancy contract checks: tenant contract schema and seeded
# rejection samples, the tenant isolation matrix, the seeded cross-tenant
# denial fixtures, the tenant lifecycle contract, and the per-tenant GitOps
# overlay generation contract with its committed example.
#
# Run separately from Batches 1-14 because tenancy is an outer isolation
# boundary layered on top of the core platform (Batch 8 team/env isolation
# stays intact beneath it).
#
# Cloud-agnostic: every script invoked here validates only Kubernetes-resident
# components and contract artifacts.

set -euo pipefail

echo "Running Batch 15 (tenancy) smoke validation suite..."

bash scripts/ci/validate_tenancy_contracts.sh

echo "Batch 15 smoke validation complete."
