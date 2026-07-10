# Tenant Admin Guide

This guide is for SaaS operators and tenant administrators who create,
operate, and retire tenants on the Observability Kit platform. It
covers the tenant record, isolation classes, tiers and quotas, the
tenant lifecycle, approval-gated destructive transitions, per-tenant
GitOps overlays, and audit records.

Automation against the same surface is documented in the
[API Reference](API_REFERENCE.md). The operator-side drill procedures
live in the
[Tenant Administration Runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md)
and the [SaaS Tenancy Runbook](../runbooks/SAAS_TENANCY_RUNBOOK.md).
The full documentation map is in the [index](INDEX.md).

## Table of Contents

- [How Tenant Management Works](#how-tenant-management-works)
- [The Tenant Record](#the-tenant-record)
- [Isolation Classes](#isolation-classes)
- [Cross-Tenant Access Is Denied by Default](#cross-tenant-access-is-denied-by-default)
- [Tiers and Quotas](#tiers-and-quotas)
- [The Tenant Lifecycle](#the-tenant-lifecycle)
- [Approvals for Destructive Transitions](#approvals-for-destructive-transitions)
- [Per-Tenant GitOps Overlays](#per-tenant-gitops-overlays)
- [Audit Records](#audit-records)
- [Related Documents](#related-documents)

## How Tenant Management Works

Every tenant operation runs through the tenant control plane service.
You reach it two ways:

- The management portal's tenants view, which lists tenants, shows a
  single tenant, and submits lifecycle transition requests. The portal
  holds no tenant logic of its own: it delegates every operation to
  the control plane API and binds your authenticated SSO principal to
  the API's `caller_scope`, so portal actions carry exactly your
  authority and land in the same audit trail. See the
  [Management Portal Guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md).
- The control plane HTTP API directly, for automation. Every path,
  schema, and error is generated from the governing contract in the
  [API Reference](API_REFERENCE.md).

Two properties hold everywhere:

- Writes are GitOps-only. A lifecycle transition renders per-tenant
  overlays and isolation artifacts and emits a prepared commit
  reference; the GitOps controller reconciles the change. The service
  never writes mutable cluster or store state directly for persistent
  configuration.
- The control plane carries tenant management data only. Tenant
  telemetry never flows through it; telemetry stays on the data plane.

## The Tenant Record

The authoritative record for a tenant is a tenant contract document
validated against
`contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`. Its
`lifecycle_state` field is the single source of truth for where the
tenant is in its lifecycle; executors reconcile toward it and never
infer state from store contents.

Required fields:

| Field | Meaning |
| ---- | ---- |
| `tenant_id` | Lowercase slug, up to 32 characters, pattern `^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$`. Embedded verbatim in index names, security roles, and dashboard space names. |
| `display_name` | Human-readable tenant name. |
| `tier` | One of `starter`, `standard`, `premium`, `enterprise`. Binds the tenant to exactly one commercial plan. |
| `isolation_class` | One of `shared-partition`, `dedicated-indices`, `dedicated-stack`. See below. |
| `residency` | `region` (provider-neutral label), `data_residency_required` (when true, tenant telemetry never leaves the declared region), and `pool`. |
| `lifecycle_state` | One of `provisioning`, `active`, `suspended`, `offboarding`, `purged`. |
| `owner` | Name and email of the accountable owner (optional team). |
| `contacts` | Contact list for the tenant. |
| `quotas` | Ingest and retention quotas; see [Tiers and Quotas](#tiers-and-quotas). |
| `created_at` | RFC 3339 timestamp. |

> [!WARNING]
> Choose `tenant_id` carefully. It is embedded in index names, roles,
> role mappings, dashboard spaces, and the overlay directory name, so
> it cannot be renamed. A purged `tenant_id` can be reused only via a
> brand-new tenant contract document.

## Isolation Classes

The isolation class declares how strongly the tenant's data is
partitioned from other tenants. All three classes use only native
mechanisms of the wrapped systems (OpenSearch security roles,
document-level security, Dashboards tenant spaces, Neo4j
multi-database); forking a wrapped system to achieve isolation is
forbidden. The full per-store matrix is
`contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`.

| Class | Logs, metrics, traces | Vectors | Graph |
| ---- | ---- | ---- | ---- |
| `shared-partition` | Shared per-env/per-team indices; every document carries an immutable `tenant_id` stamped at ingest, and reads are constrained by a document-level security filter on that field. | Per-tenant vector index even in this class (the floor rule: never a shared vector index), plus a mandatory tenant retrieval filter that fails closed. | Tenant-scoped graph access rules; no dedicated database. |
| `dedicated-indices` | Per-tenant indices named `tenant-<tenant_id>-<signal>-*` in the shared cluster; the index-name prefix is the isolation boundary. | Per-tenant vector index with the mandatory retrieval filter. | One Neo4j database per tenant in graph-enabled mode. |
| `dedicated-stack` | Per-tenant store instances rendered from the tenant's GitOps overlay; index naming is unchanged so tooling stays uniform. | Per-tenant vector index inside the tenant's own instance; the retrieval filter still applies as defense in depth. | Per-tenant database in the tenant's own instance. |

In every class each tenant gets a dedicated dashboard space
(`tenant-<tenant_id>`) bound to per-tenant reader roles, and tenant
user principals never hold telemetry write permissions; writes flow
only through platform pipeline service identities scoped to a single
tenant namespace.

## Cross-Tenant Access Is Denied by Default

Cross-tenant access or leakage is a hard failure, not a policy
preference. There is no allow-list mechanism between tenants. The
isolation matrix fixes the rule set (CTR-01 through CTR-07),
including:

- No tenant-scoped role can carry an index pattern or wildcard that
  spans another tenant's namespace.
- Every read role on a shared-partition index must pin `tenant_id` to
  exactly one tenant via document-level security.
- Dashboard spaces are per tenant; no role mapping can place a tenant
  principal in another tenant's space.
- Vector retrievals without the tenant filter are rejected (fail
  closed); graph queries execute only against the caller tenant's own
  database.
- Only named control-plane operator roles span tenant namespaces.
  That access is break-glass, time-bounded, and audited with the
  tenant id on every record; it is never mapped to tenant principals.

These rules were established by the platform's security batch and are
never weakened by later platform layers. Denied attempts emit audit
records and are exercised continuously by seeded denial scenarios.

## Tiers and Quotas

The tenant `tier` binds the tenant to exactly one commercial plan in
`contracts/commercial/PLAN_CATALOG_V1.yaml`; the mapping is bijective
(every tier has exactly one plan, every plan exactly one tier). Each
plan expresses its quota bounds in the same field names as the tenant
record's `quotas` object, so a tenant's declared quotas validate
against its plan's bounds field by field:

- `quotas.ingest.max_gb_per_day` (number, greater than 0; required)
- `quotas.ingest.max_events_per_second` (integer, at least 1)
- `quotas.retention.logs_days`, `quotas.retention.metrics_days`,
  `quotas.retention.traces_days` (integers, 1 to 3650; required)

Bounds widen monotonically from `starter` to `enterprise`. Plan
pricing, metered dimensions, and invoice export are commercial topics
covered in [Pricing and Packaging](PRICING_AND_PACKAGING.md).

## The Tenant Lifecycle

Lifecycle transitions execute the state machine of
`contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml` verbatim. States
are `provisioning`, `active`, `suspended`, `offboarding`, and `purged`
(terminal). Every transition is idempotent: re-running a transition
that already completed is a no-op that leaves the tenant in the same
end state and emits an audit record marked as a replay, so a partially
failed transition is always safe to re-run.

| Transition | From | To | Approval | What happens |
| ---- | ---- | ---- | ---- | ---- |
| `provision` | `provisioning` | `active` | none | Creates every partition and access artifact for the declared isolation class, then marks the tenant active once verification passes. Operator submits the tenant contract; completion is automated. |
| `suspend` | `active` | `suspended` | none | Halts ingest and revokes tenant UI access, reversibly. Triggered by an operator or by automation (for example quota enforcement). Data is retained. |
| `resume` | `suspended` | `active` | none | Restores ingest and UI access. Because suspended tenants keep their GitOps overlay with sync disabled, resume is a pure GitOps toggle, not a re-render. |
| `offboard` | `active` or `suspended` | `offboarding` | `write.high-risk` | Terminally revokes ingest and UI access. Data enters its contractual retention window (the longest of the retention quotas plus any residency-mandated hold); nothing is deleted yet. Never automated. |
| `purge` | `offboarding` | `purged` | `write.critical` | Irreversibly deletes every tenant data partition and access artifact, capturing deletion evidence per store. Eligible only after the retention window elapses and no legal or residency hold is set. There are no transitions out of `purged`. |

Provisioning outputs depend on the isolation class: shared-partition
tenants get field partitions, per-tenant roles, and role mappings
inside the shared indices; dedicated-indices tenants get per-tenant
indices, roles, and dashboard spaces; dedicated-stack tenants
additionally get a rendered per-tenant GitOps overlay that stands up
their own store instances.

## Approvals for Destructive Transitions

Destructive transitions delegate approval semantics to
`contracts/policy/APPROVAL_FLOW_V1.yaml`; the lifecycle contract binds
each transition to a risk class and never redefines the rules.

| Risk class | Used by | Human approval | Pending timeout | Extra requirements |
| ---- | ---- | ---- | ---- | ---- |
| `write.high-risk` | `offboard` | Required (`approval_id`, `approver`, `decision`, `decided_at`) | 60 minutes, warning at 30, then deny and escalate | Audit event on timeout. |
| `write.critical` | `purge` | Required, same fields plus `change_ticket` | 120 minutes, warning at 60, then deny and escalate | Manual workflow and change-management callback. |

Escalation follows the default chain: on-call SRE (30 minute SLA),
then incident commander (60), then platform director (120). If the
chain is exhausted unresolved, the request is denied. Every
escalation notifies the audit log, the paging service, and the
casefile comment stream, and emits an audit event.

A missing, invalid, expired, or timed-out approval surfaces on the API
as an HTTP 403 with `error_code` `approval-required` or
`approval-invalid`, and the denial itself is audited. The operator
procedure for granting approvals is in the approval handling section
of the
[Tenant Administration Runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md).

## Per-Tenant GitOps Overlays

Tenant provisioning renders one overlay directory per tenant under
`gitops/overlays/tenants/<tenant_id>/`, per
`contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`:

- `tenant-values.yaml`: a Helm values overlay layered over the base
  overlay by the tenant delivery ApplicationSet. It parameterizes
  values the core charts already expose; it never patches chart
  templates. Core charts are never modified per tenant.
- `applicationset-element.yaml`: a flat parameter element merged into
  the tenant delivery ApplicationSet's list generator.
  Environment-specific fields (destination server, repo URL, target
  revision) live in the ApplicationSet template owned by the control
  plane, never in the element.

Generated output is parameterized only by fields of the validated
tenant descriptor, and every generated file carries the header marker
`GENERATED by the tenant overlay generator - DO NOT EDIT BY HAND.`

Overlay handling follows the lifecycle: suspended tenants keep their
overlay with sync disabled, offboarding tenants retain the overlay
until purge evidence is recorded, and purge removes the overlay
directory via a Git commit.

## Audit Records

Every transition attempt emits an audit record carrying the tenant id:
applied transitions, idempotent replays (marked `replay: true`), and
denials alike. Required fields per transition include `tenant_id`,
`transition`, `actor`, timestamps, and, for approval-gated
transitions, the `approval_id`; offboard additionally records
`retention_window_ends_at`. Purge captures per-store deletion
evidence, retained immutably as control-plane records.

Audit records are control-plane records and never embed tenant
telemetry payloads. The exact per-transition field lists are in the
lifecycle binding section of the [API Reference](API_REFERENCE.md).

## Related Documents

- [API Reference](API_REFERENCE.md) - the generated control plane API
  reference for automation.
- [Pricing and Packaging](PRICING_AND_PACKAGING.md) - plans, metering,
  and invoice export.
- [Tenant Administration Runbook](../runbooks/TENANT_ADMINISTRATION_RUNBOOK.md)
  and [SaaS Tenancy Runbook](../runbooks/SAAS_TENANCY_RUNBOOK.md) -
  operator drills for the flows above.
- [Management Portal Guide](../runbooks/MANAGEMENT_PORTAL_GUIDE.md) -
  the portal that fronts the tenant control plane.
- [End User Guide](END_USER_GUIDE.md) - what your tenant's users see.
