# Tenant Administration Runbook

This runbook defines the Batch 20 operator flow for administering
tenants through the tenant control plane service (`TR-21`,
[ADR-0004](../adr/ADR_0004_TENANT_CONTROL_PLANE_SERVICE.md)). It
covers the lifecycle operations (provision, suspend, resume, offboard,
purge), approval handling for the destructive transitions, and purge
evidence verification. The control plane executes every transition as
a GitOps render plus a prepared commit recorded in the control-plane
store; it never writes to a live cluster or telemetry store (`TR-10`).
Rendered output reaches clusters only via git commit and ArgoCD
reconcile.

> [!NOTE]
> This runbook deviates from the single `Pre-checks` / `Procedure` /
> `Verification` layout used by other per-batch guides: it bundles
> several independent procedures (lifecycle operations, approval
> handling, purge evidence verification), so each major section
> carries its own preconditions and verification steps.

## Table of Contents

- [Scope](#scope)
- [Artifacts](#artifacts)
- [Global Pre-Checks](#global-pre-checks)
- [Control Plane Model](#control-plane-model)
- [Lifecycle Operations](#lifecycle-operations)
- [Approval Handling](#approval-handling)
- [Purge Evidence Verification](#purge-evidence-verification)
- [Troubleshooting and Error Codes](#troubleshooting-and-error-codes)
- [Validation](#validation)

## Scope

Batch 20 operates:

- tenant creation, read, and update behind the API surface of
  `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`
- the five lifecycle transitions of
  `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`, each executed
  with idempotent-replay evaluation and full audit capture (`TR-09`)
- approval gating for the destructive transitions (offboard, purge)
  per `contracts/policy/APPROVAL_FLOW_V1.yaml`, including timeout and
  escalation handling
- per-tenant GitOps overlay rendering per
  `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml` and
  isolation-artifact rendering per
  `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`
- purge deletion evidence recorded in the control-plane store

This runbook covers the service that executes the tenancy contracts.
Tenant descriptor authoring, isolation class selection, live-cluster
isolation verification, and the purge drill are covered by the
[SaaS Tenancy Runbook](SAAS_TENANCY_RUNBOOK.md); nothing here replaces
that guide.

## Artifacts

- `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`
- `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`
- `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`
- `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`
- `contracts/policy/APPROVAL_FLOW_V1.yaml`
- `services/tenancy/` (the `tenantctl` package, own `pyproject.toml`)
- `tests/controlplane/` (offline suites and denial fixtures)
- `scripts/ci/validate_tenant_control_plane.sh`
- `scripts/ci/validate_batch20_smoke.sh`
- `docs/adr/ADR_0004_TENANT_CONTROL_PLANE_SERVICE.md`

## Global Pre-Checks

Run these before any tenant administration session:

```bash
bash scripts/ci/validate_tenant_control_plane.sh
```

```bash
bash scripts/ci/validate_batch20_smoke.sh
```

Confirm the Batch 15 tenancy contract layer underneath the service is
green:

```bash
bash scripts/ci/validate_tenancy_contracts.sh
```

All three must pass before provisioning, suspending, resuming,
offboarding, or purging a tenant.

## Control Plane Model

### State Machine

The lifecycle contract fixes five states and five transitions.
`provisioning` is the initial state; `purged` is terminal, with no
transitions out of it:

```text
provisioning --provision--> active
active       --suspend----> suspended
suspended    --resume-----> active
active       --offboard---> offboarding
suspended    --offboard---> offboarding
offboarding  --purge------> purged      (terminal)
```

A transition attempted from a state outside its `from` set is denied
with `illegal-transition` and a denial audit record; there is no
force-transition mechanism.

### Idempotent Replay

Every transition is idempotent. Re-running a transition that already
completed is a safe, audited no-op: the tenant state does not change,
no new render is produced (`render_action: replayed-no-diff`), and
the audit record is marked `replay: true`. Two deliberate exceptions
converge state instead of doing nothing: a provision replay re-renders
a drifted or hand-edited overlay back to its contract shape, and a
purge replay removes an overlay left behind by a partially failed
purge. Denied requests are always denied, replay or not. When an
operation stalls, re-run it rather than repairing artifacts by hand.

### Control-Plane Store

The service persists its records as canonical JSON under one store
root:

```text
<store-root>/
  tenants/<tenant_id>.json               tenant document + legal_hold flag
  transitions/<tenant_id>/<name>.json    completed transitions (replay detection)
  audit/<audit_record_id>.json           append-only audit records
  evidence/<tenant_id>/<category>.json   purge deletion evidence
```

Audit records are append-only and cover every transition attempt:
applied, replayed, and denied.

### Offline and Local Invocation

The `tenantctl` core is standard-library-only (it consumes the repo's
own `tools/obskit` package as a library and adds it to `sys.path`
itself), so it runs with plain `python3` and `services/tenancy` on the
path - no venv, no PyYAML, no web framework:

```bash
cd "$(git rev-parse --show-toplevel)"
PYTHONPATH=services/tenancy python3 - <<'PY'
from pathlib import Path

from tenantctl.service import TenantControlPlaneService
from tenantctl.store import ControlPlaneStore

service = TenantControlPlaneService(
    store=ControlPlaneStore(Path(".controlplane-store")),
    repo_root=Path("."),
    lifecycle_contract_path=Path(
        "contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml"
    ),
)
result = service.transition(
    "suspend",
    "example-tenant",
    {
        "actor": "oncall-sre",
        "trigger_type": "operator",
        "reason": "sustained ingest quota breach",
    },
)
print(result)
PY
```

The offline tests follow the same pattern and run with bare `python3`
(no pytest):

```bash
python3 tests/controlplane/test_lifecycle_service.py
```

### Serving the API

`tenantctl.api` is a thin FastAPI adapter that binds the
contract-fixed routes one-to-one to service calls under the base path
`/api/tenancy/v1`. The module imports without FastAPI installed;
`build_app(service)` raises a clear error pointing at the `[api]`
extra when the framework is missing. To serve it, install the extra
from the package's own manifest (never via `requirements-ci.txt`):

```bash
python3 -m pip install "./services/tenancy[api]"
```

Then construct the app with `tenantctl.api.build_app(service)` and run
it under `uvicorn`. The hand-authored OpenAPI document
`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` is authoritative;
the adapter conforms to it, never the reverse.

## Lifecycle Operations

Tenant CRUD lives on `/tenants` and `/tenants/{tenant_id}`; each
transition is a POST to
`/tenants/{tenant_id}/lifecycle/<transition>`. Requests carry a caller
tenant scope; a caller scoped to one tenant is denied on any other
tenant's resources (`cross-tenant-access-denied`, deny-by-default per
`TR-16`).

| Transition | From                  | To            | Destructive | Approval risk class |
| ---------- | --------------------- | ------------- | ----------- | ------------------- |
| provision  | `provisioning`        | `active`      | no          | none                |
| suspend    | `active`              | `suspended`   | no          | none                |
| resume     | `suspended`           | `active`      | no          | none                |
| offboard   | `active`, `suspended` | `offboarding` | yes         | `write.high-risk`   |
| purge      | `offboarding`         | `purged`      | yes         | `write.critical`    |

### Required Request Fields

Every required field is a non-empty string unless noted. The
`approval` block is a JSON object validated separately (see
[Approval Handling](#approval-handling)).

| Transition | Required fields                  | Optional fields      |
| ---------- | -------------------------------- | -------------------- |
| provision  | `actor`                          | `reason`             |
| suspend    | `actor`, `trigger_type`, `reason` | -                   |
| resume     | `actor`, `reason`                | -                    |
| offboard   | `actor`, `reason`                | `approval`           |
| purge      | `actor`                          | `reason`, `approval` |

`trigger_type` must be `operator` or `automated`. The `approval` block
is syntactically optional but a destructive transition submitted
without it is denied with `approval-required`; treat it as mandatory
for offboard and purge.

### Renders per Isolation Class

Each transition response carries a GitOps render reference
(`render_action`, `overlay_path`, `commit_ref`) describing what the
transition did to the per-tenant overlay. Prepared commit messages are
recorded in the control-plane store; the operator reviews and commits
the rendered tree, and ArgoCD applies it.

| Transition                  | `dedicated-stack`                                        | `shared-partition`, `dedicated-indices` |
| --------------------------- | -------------------------------------------------------- | --------------------------------------- |
| provision                   | Overlay rendered at `gitops/overlays/tenants/<tenant_id>/` | `not-applicable` (no overlay)          |
| suspend, resume, offboard   | Overlay `retained` (no re-render)                         | `not-applicable`                        |
| purge                       | Overlay `removed`, prepared removal commit                | `not-applicable`                        |
| any replay                  | `replayed-no-diff` (see exceptions above)                 | `replayed-no-diff`                      |

Isolation artifacts are rendered on provision for every class, at the
class-specific path:

- `dedicated-stack`: inside the overlay, under
  `gitops/overlays/tenants/<tenant_id>/isolation/`, so the isolation
  artifacts ship with the overlay and are removed with it at purge
- `shared-partition` and `dedicated-indices`: under
  `gitops/platform/tenants/<tenant_id>/isolation/`

The tenant graph artifact is rendered only in graph-enabled mode,
gated declaratively by the `observability-kit.io/profile:
graph-enabled` marker.

### Operating the Transitions

1. Provision: submit the validated tenant document (see the
   [SaaS Tenancy Runbook](SAAS_TENANCY_RUNBOOK.md) for descriptor
   authoring), then POST `provision` with `actor`. Verify the audit
   record carries `tenant_id`, `transition`, `actor`, `requested_at`,
   `completed_at`, and `replay`, and commit the rendered output.
1. Suspend: POST `suspend` with `actor`, `trigger_type`, and `reason`.
   Automated suspends (quota or billing policy) must cite the violated
   policy in `reason`. Audit adds `trigger_type` and `reason`.
1. Resume: POST `resume` with `actor` and `reason`; the suspension
   cause must be resolved. Audit adds `reason`.
1. Offboard: obtain a `write.high-risk` approval, POST `offboard` with
   `actor`, `reason`, and the `approval` block. The audit record
   carries `approval_id` and `retention_window_ends_at` - the longest
   of the tenant contract's `quotas.retention` values (`logs_days`,
   `metrics_days`, `traces_days`) plus any residency-mandated hold.
   Nothing is deleted during offboarding, and a re-run does not reset
   the retention clock.
1. Purge: after the retention window elapses, obtain a
   `write.critical` approval with `change_ticket`, POST `purge` with
   `actor` and the `approval` block, then verify evidence per
   [Purge Evidence Verification](#purge-evidence-verification).

## Approval Handling

Approval semantics are owned by
`contracts/policy/APPROVAL_FLOW_V1.yaml`; the lifecycle contract only
binds offboard and purge to a risk class defined there.

| Risk class        | Bound transition | Required approval fields                                             | Pending timeout | Warning threshold |
| ----------------- | ---------------- | -------------------------------------------------------------------- | --------------- | ----------------- |
| `write.high-risk` | offboard         | `approval_id`, `approver`, `decision`, `decided_at`                  | 60 minutes      | 30 minutes        |
| `write.critical`  | purge            | the above plus `change_ticket`; manual change workflow required      | 120 minutes     | 60 minutes        |

The control plane enforces the window at execution time: the approval
must have been decided (`decided_at`) within the window when the
transition executes, boundary inclusive. A `decided_at` later than the
evaluation time is inconsistent and rejected as `approval-invalid`. A
missing block, missing fields, a `decision` other than approved, or a
wrong risk class are also rejected as `approval-required` or
`approval-invalid`, each with a denial audit record.

### Timeout, Deny-and-Escalate

When the window elapses (`on_timeout: deny-and-escalate`), the request
is denied, an escalation audit event is required, and the denial
carries the machine-readable escalation directive with the default
escalation chain:

| Step | Role                 | SLA        | Operator action                                                          |
| ---- | -------------------- | ---------- | ------------------------------------------------------------------------ |
| 1    | `oncall-sre`         | 30 minutes | Confirm the denial audit record, re-engage the approver, decide re-request or abandon |
| 2    | `incident-commander` | 60 minutes | Own the decision if step 1 is unresolved; for `write.critical`, drive the change-management callback |
| 3    | `platform-director`  | 120 minutes | Final authority on proceeding or abandoning the operation               |

- Unresolved after the chain: the request stays denied
  (`on_unresolved_after_chain: deny`). There is no bypass.
- Notify channels are `audit-log`, `paging-service`, and
  `casefile-comment`. The audit record is written by the control
  plane; paging and casefile notifications are dispatched by the
  surrounding AI/MCP runtime (see the
  [AI Approval Flow Runbook](AI_APPROVAL_FLOW_RUNBOOK.md)).
- `write.critical` timeouts additionally require the change-management
  callback before any re-attempt.

### Re-Approval After Timeout

A timed-out approval is never revived. Obtain a fresh approval whose
`decided_at` falls within the window, then re-submit the transition
with the new `approval` block (including a fresh `change_ticket` for
purge when the change-management process issues one). The denied
attempt and the re-attempt each have their own audit record.

## Purge Evidence Verification

### Preconditions

Purge refuses to run (denied with `precondition-failed`) unless all of
the following hold; these blocks are by design, never bypass them:

- the offboard transition was applied and its audit record is present
- the retention window recorded at offboarding
  (`retention_window_ends_at`) has elapsed; deletion never starts
  before it
- no legal or residency hold is set: the tenant record's `legal_hold`
  flag in the control-plane store must be false (operators set and
  clear it through the control plane; while set, purge stays blocked)
- an approved purge request exists and is referenced by `approval_id`
  and `change_ticket` in the audit record

### Evidence Artifacts

A purge captures one evidence record per store category, written to
the control-plane store at `evidence/<tenant_id>/<category>.json` and
referenced from the purge audit record's `evidence_artifact_refs`:

| Category                      | Proves                                                                  |
| ----------------------------- | ------------------------------------------------------------------------ |
| `opensearch_indices`          | Tenant indices deleted, or zero tenant documents in shared indices       |
| `security_roles_and_mappings` | No role or role mapping references the `tenant_id`                       |
| `dashboard_spaces`            | Tenant dashboard space absent; tenant-scoped saved objects gone          |
| `vector_indices`              | Tenant vector indices deleted, or tenant-filtered count is zero          |
| `graph_database`              | Tenant graph database dropped, or tenant-scoped entity count is zero     |
| `gitops_overlay`              | Overlay removed via prepared commit (`dedicated-stack` only)             |

Every record carries `category`, `tenant_id`, `captured_at`, and
`status` (`recorded`, or `not-applicable` for `gitops_overlay` in the
shared classes). The `gitops_overlay` record additionally carries the
`overlay_path` and `commit_ref` reference forms. Evidence records are
control-plane records: they carry the tenant id and deletion proofs
but never tenant telemetry payloads, and evidence for a
residency-pinned tenant stays in the declared region, exactly as the
data did.

### Verification Procedure

1. Confirm the tenant document reads `lifecycle_state: purged`.
1. Confirm the purge audit record carries `tenant_id`, `transition`,
   `actor`, `approval_id`, `change_ticket`, `evidence_artifact_refs`,
   `purged_at`, and `replay`.
1. Confirm all six evidence categories exist under
   `evidence/<tenant_id>/` and every ref in `evidence_artifact_refs`
   resolves to one of them.
1. Check per-class status: `gitops_overlay` is `recorded` with
   `overlay_path` and `commit_ref` for `dedicated-stack`, and
   `not-applicable` for the shared classes; all other categories are
   `recorded` in every class.
1. For `dedicated-stack`, confirm the overlay directory
   `gitops/overlays/tenants/<tenant_id>/` is gone from the rendered
   tree and the prepared removal commit is recorded.
1. Verify on replay: re-run the purge. The replay must be an audited
   no-op (`replay: true`), deletion steps are delete-if-present,
   absent artifacts still satisfy their evidence checks, and the
   evidence set is unchanged or completed - a partially failed purge
   is safely re-run until every evidence artifact is captured.

## Troubleshooting and Error Codes

Denied transitions always populate `audit_record_id` in the error
response (the lifecycle contract's `emit_audit_record_on_denial`
gate), alongside `error_code`, `message`, and optional `details`.

| Error code                   | Meaning                                                        | Operator response                                                        |
| ---------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------ |
| `validation-failed`          | Request body or tenant document fails the contract schemas      | Fix the payload; the message names the offending field                    |
| `tenant-not-found`           | No tenant record for the id                                     | Check the id; a purged tenant returns only via a new contract document    |
| `tenant-already-exists`      | Create attempted for an existing `tenant_id`                    | Use update, or pick a new id; ids are never reused                        |
| `update-forbidden-field`     | Update touches an immutable identity field (e.g. `tenant_id`)   | Immutable by contract; a class or id change is a migration, not an edit   |
| `illegal-transition`         | Transition not allowed from the current state                   | Read the current state and follow the state machine path                  |
| `precondition-failed`        | Purge preconditions not met (retention, legal hold, offboard)   | Wait for the window, clear the hold via due process, or offboard first    |
| `approval-required`          | Destructive transition submitted without an approval block      | Obtain the approval for the bound risk class and re-submit                |
| `approval-invalid`           | Approval fields missing, wrong risk class, timed out, or inconsistent `decided_at` | Obtain a fresh approval; on timeout follow the escalation chain |
| `cross-tenant-access-denied` | Caller scope does not match the target tenant                   | Verify the caller identity; repeated denials are a `TR-16` signal         |

Additional failure modes:

- A transition succeeded but the rendered tree shows no change:
  expected for replays (`replayed-no-diff`) and for shared-class
  tenants, whose transitions render no overlay.
- Provision replay produced a diff: expected only when the overlay had
  drifted from its contract shape; review the diff, commit it, and
  find who hand-edited the overlay - generated output is never edited
  in place.
- A purge stalls partway: re-run it; deletion steps are
  delete-if-present and the replay completes the evidence set. Never
  delete store records or overlay files by hand.

### Single-Writer Store and Crash Recovery

The file-backed control-plane store assumes a single writer process:
run exactly one API worker per store root. Audit record ids are
assigned sequentially per store root, so a second concurrent writer
would collide; a coordinated multi-writer store is deferred to
Batch 21+.

If the service crashes between a transition's render and its record
save, the rendered files exist but the lifecycle state has not
advanced. Re-running the same transition converges: renders are
apply-style (create-if-absent, converge-if-drifted, byte-identical
when nothing drifted), so the retry completes the record and audit
trail without duplicating or corrupting rendered output. This retry
is the designed recovery - never edit store records by hand.

## Validation

The repository-only validator covers the offline service suites
(lifecycle over GitOps renders, isolation renders, approval and
audit), the seeded denial fixture sweep, the OpenAPI document's
structural validation, and the mechanical cross-check of its
`x-lifecycle-binding` block against the lifecycle contract:

```bash
bash scripts/ci/validate_tenant_control_plane.sh
```

The Batch 20 smoke wrapper aggregates the same checks:

```bash
bash scripts/ci/validate_batch20_smoke.sh
```

Both run offline with plain `python3`: no cluster, no venv, no web
framework.

Related guides:
[SaaS Tenancy Runbook](SAAS_TENANCY_RUNBOOK.md) for the tenancy
contracts, isolation classes, and the purge drill,
[AI Approval Flow Runbook](AI_APPROVAL_FLOW_RUNBOOK.md) for the
approval-gated action flow shared with the AI/MCP layer,
[Unified Configuration Runbook](UNIFIED_CONFIGURATION_RUNBOOK.md) for
the Batch 19 renderer this service builds on,
[Validation Runbook](VALIDATION_RUNBOOK.md) for per-batch verification
entrypoints, and [Rollback Runbook](ROLLBACK_RUNBOOK.md) for GitOps
revision rollback.
