# Graph Foundation Operator Guide

This guide defines the Batch 11 operator flow for the optional derived graph
intelligence tier.

## Scope

Batch 11 validates:

- optional graph module enable and disable behavior without core disruption
- versioned graph schema for services, dependencies, ownership, and incidents
- idempotent sync jobs that converge across replay-safe runs
- graph freshness and sync quality alerts with routing
- dependency and blast-radius query coverage for incident replay
- graph operations runbook dry run for rebuild, repair, and fallback

## Artifacts

- `contracts/graph/GRAPH_MODULE_PROFILE_VALIDATION.json`
- `contracts/graph/GRAPH_SCHEMA_VERSIONING_VALIDATION.json`
- `contracts/graph/GRAPH_IDEMPOTENT_SYNC_VALIDATION.json`
- `contracts/graph/GRAPH_FRESHNESS_ALERTS_VALIDATION.json`
- `contracts/graph/GRAPH_DEPENDENCY_QUERIES_VALIDATION.json`
- `contracts/graph/GRAPH_RUNBOOK_DRY_RUN_VALIDATION.json`

## Validation Entry Points

Run focused Batch 11 validation:

```bash
bash scripts/ci/validate_graph_foundation.sh
```

Run focused Batch 11 smoke validation:

```bash
bash scripts/ci/validate_batch11_smoke.sh
```

## Expected Outcomes

- graph module can toggle on or off with core telemetry path health preserved
- schema versioning and migration controls are documented and approved
- repeated sync jobs converge with no duplicate graph relationships
- stale graph conditions trigger expected alerts and route correctly
- operator query set returns expected dependency and blast-radius paths
- graph runbook dry-run validates rebuild, repair, and fallback steps
