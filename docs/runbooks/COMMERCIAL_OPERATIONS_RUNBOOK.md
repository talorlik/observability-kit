# Commercial Operations Runbook

Operator guide for the Batch 22 commercial layer: usage metering, the
plan and tier catalog, invoicing, and quota breach handling. The
architecture is fixed by `docs/adr/ADR_0006_METERING_ARCHITECTURE.md`;
the contract surfaces live under `contracts/commercial/` and the
billing adapter boundary under `adapters/billing/`.

Everything in this runbook is offline-operable: metering derives usage
from telemetry already in OpenSearch (no new collection path), and no
step calls a billing vendor. Live-cluster evidence for the full loop
follows the Batch 23 harness discipline.

Convention note: this runbook deviates from the standard
`Scope`/`Pre-checks`/`Procedure`/`Verification` skeleton because it
covers three independent operator flows (pricing configuration,
invoicing, quota breach handling) fixed by the Batch 22 task list;
each flow section below is its own procedure, and the shared
`Verification` and `Rollback` sections close the runbook.

## Components at a Glance

| Surface | Location |
| ---- | ---- |
| Metering contract | `contracts/commercial/METERING_CONTRACT_V1.yaml` |
| Usage record schema | `contracts/commercial/USAGE_RECORD_SCHEMA_V1.json` |
| Plan catalog | `contracts/commercial/PLAN_CATALOG_V1.yaml` |
| Invoice export contract | `contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml` |
| Metering and invoicing code | `services/commercial/` (package `commercialsvc`) |
| Billing adapters | `adapters/billing/` |
| Validator | `scripts/ci/validate_commercial_contracts.sh` |

## Pricing Configuration

Pricing is contract-first and flows through Git like every other
persistent configuration (GitOps-only; no live mutation).

1. Plans bind to tenant tiers bijectively: every plan in
   `contracts/commercial/PLAN_CATALOG_V1.yaml` carries exactly one
   `tier` from the tenant contract schema enum (`starter`,
   `standard`, `premium`, `enterprise`), and every tier has exactly
   one plan.
2. To change a plan's quota bounds or billing units, edit
   `PLAN_CATALOG_V1.yaml` in a branch and run
   `bash scripts/ci/validate_commercial_contracts.sh`. The validator
   rejects a plan without quota bounds, bounds outside the tenant
   schema ranges, non-monotonic bounds across tiers, duplicate tier
   bindings, and metered dimensions missing from the metering
   contract.
3. Keep `tests/commercial/fixtures/plan_catalog_v1.json` in sync with
   the YAML; the validator fails on drift between the two.
4. Pricing stays currency-neutral in the core: plans price in
   abstract units (`base_monthly_units` plus per-dimension overage
   rates). Currency assignment happens only inside a billing adapter.
5. A tenant's price point follows its `tier` field, owned by the
   Batch 20 control plane. Moving a tenant between plans is a tenant
   lifecycle change (tier update through the control-plane API), not
   a catalog edit.

## Metering Operations

The collector job derives usage from OpenSearch aggregation surfaces
and writes usage records to control-plane indices
(`control-tenancy-usage-v1-<YYYY.MM.DD>`), honoring the TR-16 plane
separation: records carry aggregates and references (index names,
document counts, content digests) and never embed telemetry payloads.
Every record carries `tenant_id`; a record without one is rejected.

Run the job for one UTC day against a fixture (offline) with:

```bash
PYTHONPATH=services/commercial python3 -m commercialsvc.metering \
  --fixture tests/commercial/fixtures/aggregation_window_2026_07_09.json
```

The four contract dimensions are `ingest_gb_per_day` (per signal),
`retention_days` (per signal, descriptor-sourced), `active_tenants`
(per-tenant 0/1 activity), and `query_volume` (platform). Re-running a
window is idempotent: record ids are deterministic over
`tenant:dimension:signal:day`.

## Invoicing Flow

1. Ensure the billing period's daily usage records exist (run or
   verify the metering job for each day in the period).
2. Build the vendor-neutral invoice export per tenant with
   `commercialsvc.invoicing.build_invoice`: inputs are the tenant's
   usage records for the period, the plan bound to the tenant's tier,
   and the period boundaries. Totals are
   `base_monthly_units + overage_units`, with overage computed per
   dimension exactly as `INVOICE_EXPORT_CONTRACT_V1.yaml` fixes it.
3. Validate consistency: `ensure_invoice_consistent` rejects
   missing `tenant_id`, totals that do not match line items, and
   malformed documents. The document shape is
   `contracts/commercial/INVOICE_EXPORT_SCHEMA_V1.json`; a worked
   sample is `contracts/commercial/samples/VALID_INVOICE_EXPORT.json`.
4. Hand the export document to a billing adapter from
   `adapters/billing/`:
   - `file-export` (vendor-neutral) writes the document for
     downstream processing; this is the default and the fallback.
   - `stripe-reference` (stub) maps the neutral document to vendor
     objects per
     `adapters/billing/STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml`;
     credentials resolve through the secrets backend, never from Git.
5. Vendor rollback: disable the vendor backend and fall back to
   `file-export` per `adapters/billing/ROLLBACK_UNINSTALL_NOTES.md`.
   The core keeps exporting; no invoice data is lost.

## Quota Breach Handling

Breach handling is evidence-based and never mutates stores directly.

1. Detection compares usage records against the tenant descriptor
   quotas and the plan catalog bounds. Admission-time validation
   already rejects a descriptor whose quotas exceed its plan's
   bounds (`fail_if_tenant_quota_exceeds_plan_bound`).
2. Runtime breaches (usage above quota) surface through the TR-12
   alerting path, like every other platform alert. Do not build a
   parallel notification channel.
3. Enforcement is a tenant lifecycle action executed through the
   Batch 20 control plane (for example suspend on sustained breach),
   subject to the approval flow; every enforcement action emits a
   TR-09 audit record carrying the tenant id.
4. Never respond to a breach by editing tenant indices, roles, or
   dashboards directly; isolation surfaces are owned by the tenancy
   contracts and validated by
   `scripts/ci/validate_tenancy_contracts.sh`.

## Verification

```bash
bash scripts/ci/validate_commercial_contracts.sh
bash scripts/ci/validate_batch22_smoke.sh
```

Both must pass before any commercial contract or adapter change
merges. Seeded rejection fixtures prove the hard rules: a usage
record without `tenant_id`, a plan without quota bounds, and a
billing adapter with a fork-like core mutation are all rejected.

## Rollback

The commercial layer is additive. To roll it back, revert the Batch
22 commit(s); no core contract, chart, or pipeline changes are
involved. Billing vendor rollback alone follows
`adapters/billing/ROLLBACK_UNINSTALL_NOTES.md` and never touches
metering records, the plan catalog, or tenant contracts.
