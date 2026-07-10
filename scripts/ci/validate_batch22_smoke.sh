#!/usr/bin/env bash
#
# Batch 22 smoke wrapper: metering, billing, and commercial operations.
#
# Aggregates the commercial checks: the offline commercialsvc test
# suites (usage record validation with the tenant_id hard rule and
# TR-16 payload-embedding rejection, deterministic metering record
# construction for all four TR-23 dimensions, control-plane sink
# naming with plane-separation refusal, the fixture-driven metering
# job end to end, and vendor-neutral invoice export math), the
# metering and plan-catalog and invoice-export contract structural
# checks (bijective tier binding against the tenant schema enum,
# quota bounds inside schema ranges and monotonic across tiers), the
# adapters/billing/ house-pattern checks (Stripe reference stub, fork
# forbidden, export-only dispatch), and mechanical execution of every
# seeded rejection fixture (usage record without tenant_id, plan
# without quota bounds, billing adapter with a fork-like core
# mutation, vendor and currency fields in the core export document).
#
# Offline by design (TB-22 composed with TR-23 and TR-16): everything
# here runs against repository files; metering derives usage from
# fixtures standing in for telemetry already in OpenSearch, no
# billing vendor is called, and live usage evidence arrives with the
# Batch 23 harness discipline (operator-run, never CI-gated).
#
# Cloud-agnostic and vendor-neutral: the core meters and exports in
# abstract units through contract surfaces; vendor logic stays under
# adapters/billing/ and no provider-specific service is required.

set -euo pipefail

echo "Running Batch 22 (commercial operations) smoke validation suite..."

bash scripts/ci/validate_commercial_contracts.sh

echo "Batch 22 smoke validation complete."
