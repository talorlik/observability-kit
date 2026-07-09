# Tenancy Contracts

Authoritative contracts for SaaS multi-tenancy and customer isolation
(Batch 15, `TR-16`). The tenant descriptor defined here is the single
source of truth for tenant identity: id, tier, isolation class, residency
constraints, lifecycle state, ownership, and quotas. Customer isolation
layers on top of the Batch 8 team-level isolation and never weakens it.

## Files

- `TENANT_CONTRACT_SCHEMA_V1.json` - JSON Schema (draft 2020-12) for a
  tenant descriptor. `tenant_id` is pattern-constrained to a lowercase
  slug safe for the `tenant-<id>-<signal>-*` index naming convention. A
  cross-field rule requires the `dedicated-stack` isolation class to use
  a `dedicated` residency pool.
- `samples/VALID_TENANT_BASIC.json` - valid descriptor using the
  `shared-partition` isolation class.
- `samples/VALID_TENANT_DEDICATED.json` - valid descriptor using the
  `dedicated-stack` isolation class with a pinned residency region.
- `samples/INVALID_TENANT_SAMPLES.json` - seeded invalid descriptors,
  keyed by case name. Each case wraps one `descriptor` with a single
  intended violation and an `expected_rejection_reason`, mirroring the
  `invalid_fixtures` pattern in `contracts/ai/CASEFILE_FIXTURES_V1.json`.
- `TENANT_ISOLATION_MATRIX_V1.yaml` - per-tenant partitioning rules for
  logs, metrics, traces, vectors, and graph across all three isolation
  classes, with deny-by-default cross-tenant rules (`CTR-*`) and seeded
  denial scenarios (`SDN-B15-*`).
- `TENANT_LIFECYCLE_CONTRACT_V1.yaml` - idempotent state machine over
  the schema's `lifecycle_state` enum, with approval-gated offboarding
  and purge-with-evidence semantics.
- `TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml` - deterministic
  per-tenant GitOps overlay rendering and control-plane versus
  data-plane separation rules.
- `fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json` - one rejection
  fixture per seeded denial scenario in the isolation matrix.

## Isolation Classes

- `shared-partition` - shared indices partitioned by tenant field with
  per-tenant security roles.
- `dedicated-indices` - per-tenant indices, roles, and dashboard spaces
  inside shared stores.
- `dedicated-stack` - per-tenant store instances rendered from generated
  per-tenant GitOps overlays; requires a dedicated residency pool.

## Validation

`scripts/ci/validate_tenancy_contracts.sh` owns validation of this
directory: schema-versus-samples checks with seeded-reason rejection,
isolation matrix coverage, fixture bijection against the seeded denial
scenarios, lifecycle idempotency and purge evidence, and overlay
generation invariants. `scripts/ci/validate_batch15_smoke.sh` wraps it
for batch-level runs.
