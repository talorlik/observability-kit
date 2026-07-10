# ADR-0006: Metering Architecture

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 22 owner)
**Markers:** TB-22, TR-16, TR-23

## Context

Batches 15, 20, and 21 made tenants first-class: a tenant contract
(`contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`), an executing
control plane (`services/tenancy`, package `tenantctl`, ADR-0004), and
a portal (`services/portal`, ADR-0005). Nothing yet meters what a
tenant consumes, binds a tenant tier to a commercial plan, or exports
billing data, so the product cannot charge for what it serves (plan
milestone M4). Batch 22 closes that gap with a metering contract, a
collector job, a plan catalog, and a billing adapter boundary.

Forces shaping the decision:

- `TR-23` fixes the usage dimensions - ingest GB per day per signal,
  retention days, active tenants, and query volume - and requires them
  to be sourced from platform telemetry already in OpenSearch, with no
  new collection path. OpenTelemetry stays the sole collector; metering
  must not add agents, sidecars, or interceptors.
- The control-plane versus data-plane separation of `TR-16`
  (`contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`) is a
  hard boundary: usage records are tenant-management data and belong in
  `control-tenancy-*` indices; they may reference telemetry only
  through the three forms that contract fixes - index names, document
  counts, and content digests - never embedded payloads. The metered
  numeric value itself is a usage measurement, not a telemetry
  reference, and carries no telemetry content. Three dimensions are
  telemetry-derived; `retention_days` alone is descriptor-derived,
  billed as configured capability rather than observed storage age.
- Every usage record must carry `tenant_id`; a record without one is
  rejected. Attribution rides on the store partitioning the isolation
  matrix already guarantees (`tenant-<id>-<signal>-*`), so metering
  reads attribution from index naming instead of inventing its own.
- CI validation is offline and fixture-driven: no live OpenSearch, no
  PyPI at validation time, `requirements-ci.txt` stays lint-only, and
  every contract-bearing behavior must be testable with system
  `python3` (ADR-0001 posture, reaffirmed by ADR-0004 and ADR-0005).
- Billing vendors must stay pluggable (risk register: billing-adapter
  vendor lock). The core may depend on a vendor-neutral adapter
  contract only; vendor logic is adapter-scoped under
  `adapters/billing/` and forking wrapped systems remains forbidden.

## Decision

Meter by deriving usage from the stores the platform already operates,
and keep every commercial surface contract-first:

- **Derive-from-store metering.** The collector computes usage from
  OpenSearch aggregation and stats surfaces over the per-tenant
  indices (`tenant-<id>-<signal>-*`) and from validated tenant
  descriptors (retention days). No new collection path: no new
  receivers, no request middleware, no per-request metering events.
  Dimensions, sources, granularity, record shape, destination, and
  rejection rules are fixed by
  `contracts/commercial/METERING_CONTRACT_V1.yaml` and
  `contracts/commercial/USAGE_RECORD_SCHEMA_V1.json`.
- **Typed Python job under `services/commercial/`** (package
  `commercialsvc`), Python 3.11+, frozen dataclasses, type hints
  mandatory. The core is stdlib-only; the live OpenSearch path uses
  stdlib `urllib` through a narrow client protocol, so there is no
  mandatory third-party dependency and no optional extra is required
  for metering. The service owns its dependency manifest
  (`services/commercial/pyproject.toml`) and is never added to
  `requirements-ci.txt`.
- **Source and sink duality for offline CI.** The collector reads
  from a `UsageSource` protocol (live OpenSearch source, or a fixture
  source fed by committed aggregation-result JSON) and writes through
  a `UsageSink` protocol (live bulk writer targeting
  `control-tenancy-usage-v1-*`, or an in-memory/file sink for tests).
  The transformation from source data to usage records is pure and
  deterministic, so offline tests exercise the exact record-building
  code the live job runs.
- **Per-tenant activity records for the active-tenants dimension.**
  Because every usage record must carry `tenant_id`, the platform
  count of active tenants is not stored as a platform-scoped record;
  the collector emits one per-tenant activity record per window and
  exporters aggregate the count at read time.
- **Plan catalog binds tiers to quota bounds.**
  `contracts/commercial/PLAN_CATALOG_V1.yaml` maps every plan to
  exactly one value of the tenant `tier` enum (`starter`, `standard`,
  `premium`, `enterprise`) and defines quota bounds expressed in the
  same fields as the Batch 15 tenant quotas
  (`quotas.ingest.max_gb_per_day`, `quotas.retention.*_days`); a plan
  without quota bounds is invalid. Quota breach handling is
  evidence-based: breaches surface through the `TR-12` alerting path
  and every enforcement action emits a `TR-09` audit record carrying
  the tenant id.
- **Vendor-neutral billing boundary.** The invoice-export contract
  (`contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml`) is the
  product surface: it fixes the export document shape (billing period,
  per-tenant line items derived from usage records and the plan
  catalog) independent of any vendor. `adapters/billing/` follows the
  house adapter pattern (`*_COMPATIBILITY_V1.yaml`,
  `STUB_METADATA.json`, `ROLLBACK_UNINSTALL_NOTES.md`, `README.md`)
  with a Stripe reference adapter stub that maps the neutral export to
  vendor objects. A billing adapter never mutates the platform core;
  fork-like core mutation is rejected by validation.

## Alternatives Considered

- **Collector-side metering (OTel processor or receiver counting
  bytes per tenant).** Rejected: it is a new collection path, adds a
  processor to the sole-collector pipeline for a commercial concern,
  and double-counts against what the store actually retained.
- **Billing-vendor-native metering (emit usage events straight to a
  vendor metering API).** Rejected: couples the core to one vendor,
  violates the adapter boundary, and makes CI depend on a SaaS.
- **Metering inside `tenantctl`.** Rejected: the control plane
  executes lifecycle transitions; metering is a scheduled read-side
  job with a different cadence, failure domain, and dependency
  surface. A separate `services/commercial/` package keeps both small.
- **A third-party OpenSearch client library.** Rejected for the core:
  the query surface needed (aggregations, `_stats`, `_bulk`) is small
  and stdlib `urllib` covers it; offline CI must import the package
  with system `python3` alone.

## Consequences

- Usage numbers reflect what OpenSearch retained and served, not what
  crossed the wire; under-measurement from dropped data is accepted
  and documented in the runbook. This is the correct bias for
  billing: never charge for data the platform failed to keep.
- Metering accuracy inherits the store's aggregation accuracy and the
  collector's window alignment; windows are fixed UTC days to keep
  records deterministic and idempotent (same window re-collected
  yields byte-identical records apart from `collected_at`).
- The stdlib-only client means no connection pooling or retry
  sophistication; the job is a batch CronJob-style run where simple
  bounded retries suffice. Deployment wiring of the CronJob is
  deliberately deferred to the live-cluster batches (23+).
- Offline CI proves record construction, schema validation, rejection
  behavior, plan-catalog binding, and invoice export against
  fixtures; live-cluster evidence for the full loop lands with Batch
  23 discipline.
