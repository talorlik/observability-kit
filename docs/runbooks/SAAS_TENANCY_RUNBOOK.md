# SaaS Tenancy Runbook

This runbook defines the Batch 15 operator flow for serving multiple
customers (tenants) from one platform deployment with zero cross-tenant
leakage. It covers tenant onboarding, isolation verification, suspend
and resume, offboarding, and the purge drill.

> [!NOTE]
> This runbook deviates from the single `Pre-checks` / `Procedure` /
> `Verification` layout used by other per-batch guides: it bundles
> several independent procedures (onboarding, verification, lifecycle
> transitions, purge drill), so each major section carries its own
> preconditions and verification steps.

## Table of Contents

- [Scope](#scope)
- [Artifacts](#artifacts)
- [Global Pre-Checks](#global-pre-checks)
- [Tenant Onboarding](#tenant-onboarding)
- [Isolation Verification](#isolation-verification)
- [Suspend and Resume](#suspend-and-resume)
- [Offboarding](#offboarding)
- [Purge Drill](#purge-drill)
- [Troubleshooting and Failure Modes](#troubleshooting-and-failure-modes)

## Scope

Batch 15 operates:

- tenant descriptor authoring against the authoritative tenant contract
  schema
- isolation class selection across `shared-partition`,
  `dedicated-indices`, and `dedicated-stack`
- tenant provisioning per the tenant lifecycle contract, including
  per-tenant GitOps overlay generation
- cross-tenant isolation verification at the contract layer and on a
  live cluster
- suspend, resume, and offboarding with approval gates
- purge drills with per-store evidence capture and retention rules

Customer isolation layers on top of Batch 8 team and environment
isolation and must never weaken it. Isolation is achieved only through
native mechanisms of the wrapped systems (OpenSearch security roles,
document-level security, Dashboards tenant spaces, Neo4j
multi-database). Forking a wrapped system to achieve isolation is
forbidden (`TR-16`).

## Artifacts

- `contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`
- `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`
- `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`
- `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`
- `contracts/tenancy/samples/VALID_TENANT_BASIC.json`
- `contracts/tenancy/samples/VALID_TENANT_DEDICATED.json`
- `contracts/tenancy/samples/INVALID_TENANT_SAMPLES.json`
- `contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json`
- `contracts/policy/APPROVAL_FLOW_V1.yaml`
- `gitops/overlays/tenants/README.md`

## Global Pre-Checks

Run these before any tenant operation:

```bash
bash scripts/ci/validate_tenancy_contracts.sh
```

```bash
bash scripts/ci/validate_batch15_smoke.sh
```

Confirm the Batch 8 isolation baseline underneath tenancy is green:

```bash
bash scripts/ci/validate_security_isolation_resilience.sh
```

All three must pass before onboarding, suspending, offboarding, or
purging a tenant. Tenancy never replaces Batch 8 isolation; it adds an
outer boundary on top of it.

## Tenant Onboarding

### Author the Tenant Descriptor

The tenant descriptor is the authoritative identity record for one
customer. Start from `contracts/tenancy/samples/VALID_TENANT_BASIC.json`
(shared-partition) or
`contracts/tenancy/samples/VALID_TENANT_DEDICATED.json`
(dedicated classes) and validate against
`contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`.

Field rules that reject most first drafts:

- `tenant_id` is a lowercase slug matching
  `^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$`. It is embedded verbatim in
  index names (`tenant-<id>-<signal>-*`), role names, dashboard space
  names, and graph database names, so it cannot be changed after
  provisioning. No uppercase, underscores, dots, or edge hyphens.
- `lifecycle_state` must be `provisioning` for a new tenant. The
  provision transition moves it to `active`.
- `isolation_class` is one of `shared-partition`, `dedicated-indices`,
  or `dedicated-stack` (see the next section).
- `residency.pool` must be `dedicated` when `isolation_class` is
  `dedicated-stack`; the schema enforces this conditionally.
- `residency.allowed_regions`, when present, must include
  `residency.region`.
- `quotas.ingest` and `quotas.retention` are required; the retention
  values later define the offboarding retention window, so set them
  deliberately.
- at least one entry in `contacts` and a full `owner` block are
  required.

Do not put credentials, cluster endpoints, or environment names in the
descriptor; it carries tenant identity only, and the overlay generator
rejects any other input source.

### Choose an Isolation Class

The isolation class controls how logs, metrics, traces, and dashboards
are partitioned per `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`:

| Class               | Partitioning                                                          | Choose when                                                                                   |
| ------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `shared-partition`  | Shared Batch 8 indices; immutable `tenant_id` field plus DLS on read  | Starter and standard tiers, no strict residency, lowest cost per tenant                        |
| `dedicated-indices` | Per-tenant indices, roles, and spaces in the shared stores            | Divergent quotas or retention, compliance needs index-level separation, default paid posture   |
| `dedicated-stack`   | Per-tenant store instances rendered from a generated GitOps overlay   | Enterprise tier, hard residency (`data_residency_required: true`), dedicated storage pool      |

Decision guidance:

1. Start from the tier: `starter` and `standard` default to
   `shared-partition`; `premium` defaults to `dedicated-indices`;
   `enterprise` and any tenant with `data_residency_required: true`
   plus a dedicated pool get `dedicated-stack`.
1. Escalate a class when the tenant's retention or ingest quotas
   diverge far enough from the shared pool that index lifecycle
   policies would conflict.
1. Never plan to downgrade later: moving a tenant to a weaker class is
   a data migration, not a descriptor edit.

> [!IMPORTANT]
> Two floor rules apply in every class. Vectors: tenants are never
> co-mingled inside one vector index, because approximate-kNN result
> filtering is a weaker guarantee than index-name isolation; every
> class gets a per-tenant vector index plus a mandatory tenant
> retrieval filter that fails closed. Graph: Neo4j has no native
> row-level security, so every class gets one Neo4j database per
> tenant in graph-enabled mode. The class choice therefore only varies
> the telemetry-index and store-instance boundaries.

### Provision the Tenant

Provisioning follows the `provision` transition of
`contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`
(`provisioning` to `active`).

Preconditions:

- the descriptor validates against the authoritative schema
- the `tenant_id` is not present in any lifecycle state other than
  `provisioning` (a purged id may return only via a new contract
  document)
- residency constraints are satisfiable by the target data plane
  before any partition is created

Procedure:

1. Submit the validated descriptor with
   `lifecycle_state: provisioning`. The operator submits; completion to
   `active` is automated once every provisioning output verifies
   healthy. There is no second human step.
1. The executor creates the outputs for the declared isolation class:
   per-tenant roles, role mappings, and dashboard space in every
   class; per-tenant indices for the dedicated classes; the mandatory
   vector retrieval filters; the per-tenant graph database or graph
   access rules; and, for `dedicated-stack`, the generated overlay and
   the store instances deployed from it.
1. Confirm the audit record: every transition emits a record carrying
   `tenant_id`, `transition`, `actor`, `requested_at`, `completed_at`,
   and `replay` (`TR-09`).

Provisioning is idempotent: re-running it for an already-active tenant
is a no-op audited with `replay=true`, and a partially failed provision
is safely re-run to completion. When a provision stalls, re-run it
rather than deleting partial artifacts by hand.

### Generate the GitOps Overlay

Overlay generation follows
`contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml` and is
required for `dedicated-stack` tenants (the generator runs for every
tenant whose lifecycle state allows it):

1. Feed the generator exactly one validated descriptor. Generation is
   allowed only in the `provisioning`, `active`, and `suspended`
   states.
1. The output is one directory,
   `gitops/overlays/tenants/<tenant_id>/`, whose name equals the
   descriptor `tenant_id` verbatim, containing exactly
   `tenant-values.yaml` and `applicationset-element.yaml`. Both files
   carry the generated-file header marker.
1. Commit the generated directory. Overlays reach clusters only via
   git commit and GitOps reconcile; direct `kubectl` or API writes of
   tenant delivery config are forbidden (`TR-10`).
1. Confirm determinism: regenerating from an unchanged descriptor must
   produce no diff and no commit. A diff on regeneration is a contract
   violation, not noise.

> [!WARNING]
> Never hand-edit a generated overlay and never diff
> `gitops/charts/` in a tenant change. Core charts are read-only per
> tenant; a tenant change that touches them fails validation. Change
> the descriptor and regenerate instead. Generated output is
> parameterized only by descriptor fields and must never contain
> environment names, cluster endpoints, repository URLs, credentials,
> provider-specific identifiers, or telemetry payloads.

`gitops/overlays/tenants/EXAMPLE_TENANT_OVERLAY/` is the committed
reference output for the basic sample; its uppercase name is
deliberately outside the `tenant_id` pattern so it can never collide
with a real tenant.

### Post-Provision Verification

1. Confirm the tenant contract document reads
   `lifecycle_state: active`.
1. Re-run the contract layer:

   ```bash
   bash scripts/ci/validate_tenancy_contracts.sh
   ```

1. Verify per-store artifacts against the isolation matrix for the
   declared class: telemetry indices or DLS-filtered shared access,
   `tenant-<tenant_id>-<signal>-reader` (and, where applicable,
   `-writer`) roles with their role mappings, the
   `tenant-<tenant_id>` dashboard space, the per-tenant vector index
   with its mandatory retrieval filter, and the `tenant-<tenant_id>`
   graph database in graph-enabled mode.
1. For `dedicated-stack`, confirm the ApplicationSet rendered a
   healthy, synced application from the tenant overlay.
1. Spot-check denial from the new tenant's side: a principal of the
   new tenant must be denied on any other tenant's indices, space,
   vectors, and graph database (see the next section).
1. Confirm Batch 8 team and environment isolation still holds inside
   the tenant partition; tenant provisioning must never broaden a
   Batch 8 role or index pattern.

## Isolation Verification

### Contract-Layer Verification

The contract layer proves the configuration rules without a cluster:

```bash
bash scripts/ci/validate_tenancy_contracts.sh
```

This validates the schema and samples, the isolation matrix totality
(every store covered for every class), the lifecycle and overlay
contracts, and the seeded cross-tenant fixtures in
`contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json`. A
seeded fixture that is not rejected or denied fails the batch; treat
that as an isolation incident, not a flaky test.

### Walk the Cross-Tenant Rules

Cross-tenant access is deny-by-default with no allow-list mechanism
between tenants. Prove each rule of the isolation matrix
(`cross_tenant_access.rules`) as follows:

| Rule   | Statement                                        | Operator proof                                                                     |
| ------ | ------------------------------------------------ | ----------------------------------------------------------------------------------- |
| CTR-01 | No foreign or spanning index pattern in roles    | Inspect every tenant role; no pattern, alias, or template match crosses namespaces   |
| CTR-02 | DLS mandatory on shared-partition read roles     | Every shared-index read role pins `tenant_id` to exactly one tenant                  |
| CTR-03 | No cross-tenant dashboard space access           | No mapping places a principal in a foreign space; saved objects stay in-namespace    |
| CTR-04 | Mandatory vector tenant filter                   | Unfiltered retrieval rejected (fail closed); mismatched tenant filter denied         |
| CTR-05 | Graph queries scoped to own database             | Cross-database, enumeration, and system-database access denied to tenant principals  |
| CTR-06 | Tenant principals never write telemetry          | Writer roles bind only to platform pipeline service identities                       |
| CTR-07 | Operator spans are control-plane break-glass     | Spanning roles are named, audited per `TR-09` with tenant id, never tenant-mapped    |

### Seeded Denial Scenarios

The `SDN-B15-*` scenarios in the isolation matrix are the concrete
denial cases; Batch 15 Task 5 turns each into a rejection fixture
consumed by `validate_tenancy_contracts.sh`:

| Scenario    | Store      | Enforcement point | Expected |
| ----------- | ---------- | ----------------- | -------- |
| SDN-B15-001 | logs       | runtime           | deny     |
| SDN-B15-002 | metrics    | config-validation | reject   |
| SDN-B15-003 | traces     | runtime           | deny     |
| SDN-B15-004 | dashboards | config-validation | reject   |
| SDN-B15-005 | vectors    | runtime           | reject   |
| SDN-B15-006 | vectors    | runtime           | deny     |
| SDN-B15-007 | graph      | runtime           | deny     |
| SDN-B15-008 | logs       | config-validation | reject   |
| SDN-B15-009 | all        | config-validation | reject   |

The `config-validation` scenarios are proven by the contract layer:
invalid configuration (a spanning wildcard, a missing DLS filter, a
foreign-space mapping) must be rejected before apply.

### Runtime Checks on a Live Cluster

The `runtime` scenarios need a deployed instance and two provisioned
tenants (use disposable drill tenants in non-production). Using a
principal authenticated for the first tenant, verify each denial and
its audit record:

1. Search a second tenant's log index directly and through any alias
   that resolves into it: both denied (SDN-B15-001, SDN-B15-003).
1. Query a shared-partition index and confirm only documents whose
   `tenant_id` matches the caller come back.
1. Issue a vector retrieval without the tenant filter: rejected, fail
   closed, never fail open (SDN-B15-005). Issue one whose filter names
   the second tenant: denied (SDN-B15-006).
1. Open a graph session targeting the second tenant's database and the
   system database: both denied (SDN-B15-007).
1. Attempt a telemetry write as a tenant user principal: denied
   (CTR-06); writes flow only through pipeline service identities.
1. Confirm every denial above produced an audit record carrying the
   tenant id (`TR-09`).

Do not embed literal credentials in any recorded check; runtime checks
authenticate through the identity backend adapter configured for the
deployment (Batch 13).

## Suspend and Resume

### Suspend a Tenant

Suspend (`active` to `suspended`) stops ingest and revokes tenant UI
access while retaining all data. It is triggered by an operator (with a
cited reason) or by automated policy (sustained quota breach or a
billing signal; the audit record must cite the violated policy). It is
not approval-gated because it is non-destructive.

Semantics to verify after suspending:

- ingest stops at the collector routing layer; tenant-attributed
  telemetry is rejected, not buffered into another tenant's partition
- no indices, spaces, vector indices, graph databases, or overlays are
  deleted or narrowed
- UI access is revoked by disabling the tenant role mappings, never by
  deleting roles or spaces
- audit capture continues throughout suspension
- the tenant overlay is retained with sync disabled, so resume is a
  pure GitOps toggle, not a re-render

Suspend is idempotent; a repeat is a no-op audited with `replay=true`.

### Resume a Tenant

Resume (`suspended` to `active`) is operator-initiated and requires
the suspension cause recorded at suspend time to be marked resolved in
the audit trail. Verification: ingest flows again, role mappings are
re-enabled, dashboard access works, and the audit record for the
transition is present. Resume is idempotent.

## Offboarding

Offboard (`active` or `suspended` to `offboarding`) begins controlled
removal and is destructive, so it is approval-gated.

Approval gate:

- approval semantics follow the `write.high-risk` rules of
  `contracts/policy/APPROVAL_FLOW_V1.yaml` (required fields, pending
  timeout, escalation); this runbook does not redefine them
- the approved request's `approval_id` must appear in the offboard
  audit record
- offboarding is never automated

Procedure:

1. Obtain the approved offboarding request.
1. Apply the offboard transition. Ingest and UI access are terminally
   revoked (not reversible via resume).
1. Record the retention window: the longest of the descriptor's
   `logs_days`, `metrics_days`, and `traces_days`, plus any
   residency-mandated hold. The audit record carries
   `retention_window_ends_at`.
1. Confirm nothing was deleted: data remains in place for the full
   window, and the tenant overlay is retained until purge evidence is
   recorded.

Offboard is idempotent; a re-run does not reset the retention clock.
Retention expiry makes the tenant eligible for purge but never executes
it.

## Purge Drill

The purge drill rehearses the terminal `purge` transition
(`offboarding` to `purged`) end to end, including evidence capture, so
a real customer purge is routine rather than novel.

> [!CAUTION]
> Like the restore and rollback drills under `scripts/ops/`, the purge
> drill is non-production-first: rehearse only against a disposable
> drill tenant in a non-production environment. A real purge
> irreversibly deletes every tenant partition; there are no
> transitions out of `purged`, and re-onboarding a returning customer
> is a new provision with a new contract document.

### Drill Preconditions

- non-production environment (mirror the `scripts/ops/` convention of
  refusing to run when `ENVIRONMENT` is `production`)
- a disposable drill tenant, provisioned for this drill with a short
  retention quota so the window elapses quickly
- the drill tenant has been offboarded and its
  `retention_window_ends_at` has elapsed
- no legal or residency hold flag is set on the drill tenant
- an approved purge request exists: purge binds to the
  `write.critical` rules of `contracts/policy/APPROVAL_FLOW_V1.yaml`,
  including the manual workflow requirement and the `change_ticket`
  field

### Drill Procedure

1. Provision the drill tenant, ingest a small amount of synthetic
   telemetry into each store (logs, metrics, traces, vectors, and
   graph in graph-enabled mode), and confirm it is `active`.
1. Offboard the drill tenant with an approved request and record
   `retention_window_ends_at`.
1. After the window elapses, execute the purge transition with the
   approved purge request.
1. Capture one evidence artifact per store, exactly as the lifecycle
   contract's `evidence_capture` block defines:

   | Store                       | Evidence proves                                                     |
   | --------------------------- | ------------------------------------------------------------------- |
   | OpenSearch indices          | Tenant indices deleted, or zero tenant documents in shared indices   |
   | Security roles and mappings | No role or mapping references the `tenant_id`                        |
   | Dashboard spaces            | Tenant space absent; tenant-scoped saved-objects query returns empty |
   | Vector indices              | Tenant vector indices deleted, or tenant-filtered count is zero      |
   | Graph database              | Tenant database dropped, or tenant-scoped entity count is zero       |
   | GitOps overlay              | Overlay removed via git commit; rendered set shows no tenant app     |

   The overlay evidence applies to `dedicated-stack` tenants and is
   recorded as not-applicable for the other classes.

1. Verify the purge audit record carries `tenant_id`, `transition`,
   `actor`, `approval_id`, `change_ticket`, `evidence_artifact_refs`,
   `purged_at`, and `replay`.
1. Re-run the purge to prove idempotency: deletion steps are
   delete-if-present, absent artifacts satisfy their evidence checks,
   and the replay is audited with `replay=true`.
1. Confirm a neighboring tenant in the same environment is untouched:
   its indices, roles, space, vectors, and graph database still exist
   and its isolation checks still pass.

### Evidence Retention and Audit Expectations

- retention rules are honored before deletion: purge never starts
  before the recorded retention window has elapsed
- evidence for a residency-pinned tenant stays in the declared region,
  exactly as the data did
- evidence artifacts and the purge audit record are control-plane
  records: they carry the tenant id and deletion proofs (index names,
  document counts, content digests) but never tenant telemetry
  payloads
- evidence is retained immutably in the control plane for the
  configured evidence retention period (default 365 days after purge;
  deployments may extend it, never shorten it)

### Drill Exit Criteria

- every per-store evidence artifact captured and referenced from the
  purge audit record
- idempotent replay verified with `replay=true`
- neighboring tenant unaffected
- `bash scripts/ci/validate_tenancy_contracts.sh` still passes

## Troubleshooting and Failure Modes

- Descriptor rejected by the schema: check the `tenant_id` pattern
  (lowercase slug, no edge hyphens), required `owner`, `contacts`, and
  `quotas` blocks, and the conditional rule that `dedicated-stack`
  requires `residency.pool: dedicated`. The seeded invalid samples in
  `contracts/tenancy/samples/INVALID_TENANT_SAMPLES.json` enumerate
  the rejection cases.
- Provision stuck in `provisioning`: verify residency constraints are
  satisfiable by the target data plane, then re-run the transition;
  provisioning is apply-style and converges. Do not delete partial
  artifacts by hand.
- Regeneration produces a diff for an unchanged descriptor: this is a
  determinism violation of the overlay contract, not noise. Do not
  commit the diff; fix the generator input or report the generator
  defect.
- Generated overlay was hand-edited: the next regeneration overwrites
  it and review rejects it. Change the descriptor and regenerate.
- A tenant change diffs `gitops/charts/`: contract violation
  (core charts are read-only per tenant); the change must be rewritten
  as a values overlay.
- A seeded denial fixture is not rejected: hard batch failure. Treat
  it as a cross-tenant isolation incident and block tenant operations
  until `validate_tenancy_contracts.sh` is green again.
- Legitimate tenant vector queries fail: check for a missing mandatory
  tenant retrieval filter. Fail-closed rejection of unfiltered queries
  is by design (CTR-04); fix the caller, never relax the filter.
- Tenant sees no data in `shared-partition`: confirm the collector
  pipeline stamps the immutable `tenant_id` field at ingest and that
  the read role carries the matching DLS filter.
- Ingest continues after suspend: the stop is enforced at the
  collector routing layer; verify the routing change applied and that
  rejected telemetry is not being buffered into another tenant's
  partition.
- Purge blocked by preconditions: retention window not elapsed, a
  legal or residency hold set, or approval fields missing. These
  blocks are by design; never bypass them.
- A cross-tenant read succeeds at runtime: treat as a severity-one
  isolation incident (`TR-16` hard failure). Suspend the affected
  access path, use only named break-glass control-plane roles for
  investigation (CTR-07), and capture the `TR-09` audit trail.

Related guides:
[Security Isolation Resilience Operator Guide](SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md)
for the Batch 8 baseline underneath tenancy,
[Validation Runbook](VALIDATION_RUNBOOK.md) for per-batch verification
entrypoints, and [Rollback Runbook](ROLLBACK_RUNBOOK.md) for GitOps
revision rollback.
