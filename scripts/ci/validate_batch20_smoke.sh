#!/usr/bin/env bash
#
# Batch 20 smoke wrapper: tenant control plane service.
#
# Aggregates the tenant control plane checks: the offline service test
# suites (lifecycle service over GitOps renders, isolation renders,
# approval and audit), the seeded denial fixture sweep (unapproved and
# wrong-risk-class destructive requests, timed-out approvals, illegal
# transitions, retention-window and legal-hold purge preconditions,
# cross-tenant denial, malformed-document rejection - all denied with
# contract-fixed error codes and denial audit records), the OpenAPI
# document's structural validation, and the mechanical cross-check of
# its x-lifecycle-binding block against
# contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml.
#
# Offline by design (TR-20 composed with TR-18): everything here runs
# against fixtures and temp directories; the service never touches a
# live cluster, and live-cluster evidence arrives with the Batch 23
# harness and is never CI-gated.
#
# Cloud-agnostic: the control plane executes transitions as
# GitOps-only renders for any conformant Kubernetes cluster; no
# provider-specific service is required.

set -euo pipefail

echo "Running Batch 20 (tenant control plane) smoke validation suite..."

bash scripts/ci/validate_tenant_control_plane.sh

echo "Batch 20 smoke validation complete."
