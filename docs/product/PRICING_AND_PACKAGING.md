# Pricing and Packaging

Commercial reference for Observability Kit: the plan and tier
catalog, the usage dimensions the platform meters, the billing
adapter options, and the invoice export flow. The audience is
commercial and sales teams; support engineers should pair this
document with [Support and Onboarding](SUPPORT_AND_ONBOARDING.md).

Everything on this page is bound to shipped contracts. The single
source of truth for plans is the
[plan catalog](../../contracts/commercial/PLAN_CATALOG_V1.yaml);
metering behavior is fixed by the
[metering contract](../../contracts/commercial/METERING_CONTRACT_V1.yaml);
invoicing is fixed by the
[invoice export contract](../../contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml).
The architecture decision behind the commercial layer is
[ADR-0006](../adr/ADR_0006_METERING_ARCHITECTURE.md). When this page
and a contract disagree, the contract wins.

## Table of Contents

- [Pricing Model at a Glance](#pricing-model-at-a-glance)
- [Plans and Tiers](#plans-and-tiers)
- [Quota Bounds per Plan](#quota-bounds-per-plan)
- [Metering Dimensions](#metering-dimensions)
- [Usage Records and Attribution](#usage-records-and-attribution)
- [Overage Pricing](#overage-pricing)
- [Invoice Export Flow](#invoice-export-flow)
- [Billing Adapter Options](#billing-adapter-options)
- [Deployment Sizing per Tier](#deployment-sizing-per-tier)
- [Changing Prices and Moving Tenants](#changing-prices-and-moving-tenants)
- [Reference Documents](#reference-documents)

## Pricing Model at a Glance

- Every plan prices as base-plus-overage in currency-neutral
  abstract units. The core platform never carries a currency; a
  billing adapter assigns currency and tax downstream.
- Usage is derived from telemetry the platform already stores in
  OpenSearch. Metering adds no new collection path: no sidecars, no
  agents, no request middleware, no per-request metering events.
- Plans bind one-to-one to tenant tiers, so a tenant's price point
  follows its `tier` field and nothing else.
- Pricing changes flow through Git and CI validation like every
  other persistent configuration (GitOps-only; no live mutation).

## Plans and Tiers

The catalog defines four plans. Each plan binds to exactly one value
of the tenant `tier` enum in the
[tenant contract schema](../../contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json),
and every enum value has exactly one plan (a bijective mapping,
enforced by validation). The tier enum is `starter`, `standard`,
`premium`, `enterprise`; it is defined only in the tenant schema and
never redefined by the catalog.

| Plan       | Plan id           | Tenant tier  | Base charge (units/month) |
| ---------- | ----------------- | ------------ | ------------------------- |
| Starter    | `plan-starter`    | `starter`    | 100                       |
| Standard   | `plan-standard`   | `standard`   | 400                       |
| Premium    | `plan-premium`    | `premium`    | 1200                      |
| Enterprise | `plan-enterprise` | `enterprise` | 4000                      |

All charges are currency-neutral units. A billing adapter converts
units to money; see
[Billing Adapter Options](#billing-adapter-options).

## Quota Bounds per Plan

Each plan bounds the same five quota fields a tenant descriptor
carries, using identical field names, so a tenant's quotas validate
against its plan field-by-field with no translation layer. Bounds
widen monotonically from Starter to Enterprise. A tenant descriptor
whose quotas fall outside its plan's bounds is rejected at admission
time.

| Quota field (min-max)         | Starter | Standard | Premium    | Enterprise    |
| ----------------------------- | ------- | -------- | ---------- | ------------- |
| Ingest, GB per day            | 1-25    | 25-100   | 100-500    | 500-5000      |
| Ingest, events per second     | 1-500   | 500-2000 | 2000-10000 | 10000-100000  |
| Log retention, days           | 1-14    | 14-30    | 30-90      | 90-3650       |
| Metric retention, days        | 1-14    | 14-30    | 30-90      | 90-3650       |
| Trace retention, days         | 1-7     | 7-30     | 30-90      | 90-3650       |

The catalog fields behind this table are `quota_bounds` entries named
`quotas.ingest.max_gb_per_day`, `quotas.ingest.max_events_per_second`,
`quotas.retention.logs_days`, `quotas.retention.metrics_days`, and
`quotas.retention.traces_days`.

## Metering Dimensions

The metering contract fixes four usage dimensions. All values are
measured per tenant at UTC-day granularity. Three dimensions are
derived from OpenSearch aggregations over data the platform already
stores; `retention_days` alone is read from the validated tenant
descriptor and billed as configured capability, not observed storage
age (a deliberate ADR-0006 decision).

| Dimension           | Unit    | Scope                          | Source                                                                |
| ------------------- | ------- | ------------------------------ | --------------------------------------------------------------------- |
| `ingest_gb_per_day` | gb      | Per signal (logs, metrics, traces) | Index stats and date histogram over `tenant-<tenant_id>-<signal>-*` |
| `retention_days`    | days    | Per signal (logs, metrics, traces) | Tenant descriptor `quotas.retention.*` fields                        |
| `active_tenants`    | count   | Platform                       | Presence over `tenant-<tenant_id>-*-*`: 1 on any activity that day    |
| `query_volume`      | queries | Platform                       | Existing audit and SLO telemetry (`control-tenancy-audit-*`)          |

`ingest_gb_per_day` binds to the `quotas.ingest.max_gb_per_day`
bound and `retention_days` to the `quotas.retention` bounds;
`active_tenants` and `query_volume` have no quota binding and are
priced on full quantity (see [Overage Pricing](#overage-pricing)).

> [!NOTE]
> `query_volume` counts queries from audit and SLO telemetry the
> platform already collects. No query interception is added; the
> OpenTelemetry collector remains the sole collector.

## Usage Records and Attribution

The metering collector (`commercialsvc`, under `services/commercial/`)
writes one usage record per tenant, dimension, signal, and UTC day,
shaped by the
[usage record schema](../../contracts/commercial/USAGE_RECORD_SCHEMA_V1.json).
Every record carries: `record_id`, `tenant_id`, `dimension`,
`signal`, `value`, `unit`, `window_start`, `window_end`,
`source_reference`, `collected_at`, and `collector_version`.

Properties that matter commercially:

- Attribution rides on the isolation-matrix index partitioning
  (`tenant-<id>-<signal>-*`). The collector derives `tenant_id` from
  index naming and validated tenant descriptors; it never parses
  telemetry payloads for attribution.
- Record construction is deterministic and idempotent: `record_id`
  is derived from `(tenant_id, dimension, signal, window_start)`, so
  re-collecting a day never double-bills.
- Records are tenant-management data and live only in control-plane
  OpenSearch indices matching `control-tenancy-usage-v1-*`, never in
  tenant data-plane indices, and never embed telemetry payloads.

## Overage Pricing

Overage is computed against the max of the plan's quota bound for
each bounded dimension (`over-bound` basis). Dimensions without a
quota bound use the `full-quantity` basis: the whole metered quantity
is billable at the dimension's rate, with an implicit bound of zero.
Rates are per plan:

| Dimension           | Overage unit                     | Starter | Standard | Premium | Enterprise |
| ------------------- | -------------------------------- | ------- | -------- | ------- | ---------- |
| `ingest_gb_per_day` | units per GB over bound          | 2       | 2        | 1       | 1          |
| `retention_days`    | units per signal-day over bound  | 1       | 1        | 1       | 1          |
| `active_tenants`    | units per active tenant-day      | 0       | 0        | 0       | 0          |
| `query_volume`      | units per 1000 queries over bound | 1       | 1        | 1       | 1          |

Reading the table: higher tiers pay lower ingest overage rates, and
tenant activity itself (`active_tenants`) is tracked but carries a
zero rate on every plan today - it appears on invoices as a
zero-charge line item for transparency.

Worked rule for the bounded dimensions: per usage record, overage
quantity is `max(0, value - bound)`; the line item's `overage_units`
is the sum over the billing period times the plan's rate for that
dimension.

## Invoice Export Flow

One billing period yields exactly one vendor-neutral export document
per tenant, shaped by the
[invoice export schema](../../contracts/commercial/INVOICE_EXPORT_SCHEMA_V1.json)
(a worked sample lives at
`contracts/commercial/samples/VALID_INVOICE_EXPORT.json`).

1. Verify the period's daily usage records exist (run or verify the
   metering job for each day in the period).
2. Build the export with `commercialsvc.invoicing.build_invoice`.
   Inputs are the tenant's validated usage records, the plan bound
   to the tenant's tier, and the period boundaries. Records that
   fail schema validation, or that carry a foreign `tenant_id`,
   never reach the exporter.
3. Validate with `ensure_invoice_consistent`, which rejects a
   missing `tenant_id`, totals that do not match line items, and
   malformed documents.
4. Hand the document to a billing adapter from `adapters/billing/`
   for currency assignment and delivery.

The document fields: `invoice_id` (deterministic
`<tenant_id>:<period_start>:<period_end>`, so re-export of the same
period is idempotent), `tenant_id`, `plan_id`, `tier`,
`billing_period` (start inclusive, end exclusive, RFC 3339 UTC),
`line_items` (one entry per dimension-signal pair with `quantity`,
`unit`, `overage_units`, and `source_record_count`), `totals`
(`base_monthly_units`, `overage_units`, and `total_units` =
base plus overage), `generated_at`, and `exporter_version`.

## Billing Adapter Options

Vendor billing systems integrate through the adapter boundary under
`adapters/billing/` only ("house" adapter pattern, fixed by
ADR-0006; wrapping via a fork of the core was evaluated and
rejected). The core never imports a vendor SDK and never names a
vendor; currency and tax handling are adapter-side only. Adapter
credentials resolve through the secrets backend as secret
references - a literal credential in configuration or Git is a
contract violation.

| Backend            | Mode                  | Vendor neutral | Profiles                          |
| ------------------ | --------------------- | -------------- | --------------------------------- |
| `file-export`      | `export-file`         | Yes            | `quickstart`, `dev`, `staging`, `prod` |
| `stripe-reference` | `invoice-export-push` | No (stub)      | `staging`, `prod`                 |

- `file-export` writes the neutral export document for downstream
  processing. It is the default and the guaranteed fallback.
- `stripe-reference` is a declarative reference stub
  ([mapping](../../adapters/billing/STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml)):
  field mapping, auth references, and non-goals only - no code and
  no live calls. It is the template for real vendor integrations.
- Disabling any vendor adapter falls back to `file-export` with the
  core contracts unchanged; no invoice data is lost (see
  [rollback notes](../../adapters/billing/ROLLBACK_UNINSTALL_NOTES.md)).

To add a vendor, follow the checklist in the
[billing adapters README](../../adapters/billing/README.md): register
the backend in
[the compatibility file](../../adapters/billing/BILLING_ADAPTER_COMPATIBILITY_V1.yaml),
add a `<VENDOR>_REFERENCE_ADAPTER_STUB_V1.yaml` mapping, and run
`bash scripts/ci/validate_commercial_contracts.sh`.

## Deployment Sizing per Tier

The production reference architecture sizes clusters against the
same tier enum the plans bind to, so a commercial conversation about
tier maps directly to an infrastructure footprint. A cluster is
sized for the largest tier it hosts; quota bounds come from the plan
catalog, not the sizing table. Full node shapes, HA topology,
storage floors, and backup posture are in the
[production reference architecture](../../contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml).

| Tier       | Tenant scale (summary)                              | Worker nodes | OpenSearch data nodes    |
| ---------- | --------------------------------------------------- | ------------ | ------------------------ |
| Starter    | Single-digit tenants, shared-partition isolation    | 3            | 3 x 200 GiB              |
| Standard   | Tens of tenants, shared or dedicated indices        | 5            | 3 x 500 GiB              |
| Premium    | Tens of tenants, dedicated indices, heavy retention | 7            | 5 x 1 TiB                |
| Enterprise | Dedicated-stack isolation available per tenant      | 9            | 6 x 2 TiB, dedicated masters |

Per-tier service commitments (availability and latency SLOs,
including the zero-tolerance tenant isolation SLO) are covered in
[Support and Onboarding](SUPPORT_AND_ONBOARDING.md).

## Changing Prices and Moving Tenants

- To change a plan's quota bounds or billing units, edit
  `contracts/commercial/PLAN_CATALOG_V1.yaml` in a branch and run
  `bash scripts/ci/validate_commercial_contracts.sh`. The validator
  rejects a plan without quota bounds, bounds outside the tenant
  schema ranges, non-monotonic bounds across tiers, duplicate tier
  bindings, and metered dimensions missing from the metering
  contract. Keep `tests/commercial/fixtures/plan_catalog_v1.json`
  in sync; the validator fails on drift.
- Moving a tenant between plans is a tenant lifecycle change: a
  `tier` update through the Batch 20 control-plane API, operated per
  the
  [tenant administration runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md).
  It is never a catalog edit.
- Day-to-day commercial operations (metering runs, invoicing, quota
  breach handling) are documented in the
  [commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md).

## Reference Documents

- [Plan catalog](../../contracts/commercial/PLAN_CATALOG_V1.yaml)
- [Metering contract](../../contracts/commercial/METERING_CONTRACT_V1.yaml)
- [Usage record schema](../../contracts/commercial/USAGE_RECORD_SCHEMA_V1.json)
- [Invoice export contract](../../contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml)
- [Invoice export schema](../../contracts/commercial/INVOICE_EXPORT_SCHEMA_V1.json)
- [Tenant contract schema](../../contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json)
- [Billing adapters](../../adapters/billing/README.md)
- [Metering architecture ADR](../adr/ADR_0006_METERING_ARCHITECTURE.md)
- [Commercial operations runbook](../runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md)
- [Documentation index](INDEX.md)
