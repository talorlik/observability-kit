# Unified Configuration Runbook

This runbook defines the Batch 16 operator flow for the unified
configuration and management plane: changing platform configuration
through the single unified document, responding to drift between
rendered and live state, rolling back, upgrading each wrapped system
through its own upstream mechanism, and operating the single-pane UI
catalog. Batch 19 turned the contract-described flow into executable
steps: the render, drift, and rollback stages below run through the
`obskit` configuration rendering runtime
(`tools/obskit/obskit/configrender/`, ADR-0003).

> [!NOTE]
> This runbook deviates from the single `Pre-checks` / `Procedure` /
> `Verification` layout used by other per-batch guides: it bundles
> several independent procedures (config change flow, drift response,
> rollback, per-system upgrades, single-pane access operations), so
> each major section carries its own preconditions and verification
> steps.

## Table of Contents

- [Scope](#scope)
- [Artifacts](#artifacts)
- [Global Pre-Checks](#global-pre-checks)
- [Config Change Flow](#config-change-flow)
- [Drift Response](#drift-response)
- [Rollback](#rollback)
- [Per-System Upstream Upgrade Procedure](#per-system-upstream-upgrade-procedure)
- [Single-Pane Access Operations](#single-pane-access-operations)
- [Troubleshooting and Failure Modes](#troubleshooting-and-failure-modes)

## Scope

Batch 16 operates:

- edits to the unified configuration document, the one place operators
  change platform configuration (`TR-17`)
- schema and binding validation of the document against the unified
  config schema and the wrapped-system registry
- the GitOps-only propagation pipeline: render, commit, reconcile,
  verify, and continuous drift detection
  (`contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`)
- drift triage, the alert-only and automated-revert postures, and their
  interaction with break-glass access
- rollback via unified-document revert and the rollback drill
- per-system upstream upgrades through each registered system's own
  upgrade mechanism, with version pins changed only through the
  wrapped-system registry
- single-pane access: the UI catalog, SSO role mapping checks, and
  tenant scoping verification pointers

The hard rule underneath every procedure here is wrap, don't fork
(`TR-17`): every wrapped system runs unmodified upstream artifacts and
upgrades through its own upstream mechanism. The platform layers
configuration around upstream code; it never patches, rebuilds, or
vendors modified copies. Allowed wrap methods are `helm-values`,
`kubernetes-crd`, `provisioning-api`, and `sidecar`; `fork` is
forbidden and rejected by validation.

## Artifacts

- `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`
- `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`
- `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`
- `contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`
- `contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`
- `contracts/management/samples/VALID_UNIFIED_CONFIG.yaml`
- `contracts/management/samples/VALID_UNIFIED_CONFIG.json` (JSON twin,
  the renderer's input form)
- `contracts/management/samples/INVALID_UNIFIED_CONFIG_SAMPLES.json`
- `contracts/management/samples/INVALID_REGISTRY_SAMPLES.json`
- `docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md`
- `gitops/platform/search/dashboards/alerts/platform_health_rules.ndjson`
- `scripts/ops/run_rollback_drill.sh`
- `scripts/ops/run_config_rollback_drill.sh`
- `scripts/validate/post_install_readiness.sh`

## Global Pre-Checks

Run these before any management-plane operation:

```bash
bash scripts/ci/validate_management_plane_contracts.sh
```

```bash
bash scripts/ci/validate_batch16_smoke.sh
```

```bash
bash scripts/ci/validate_config_renderer.sh
```

All must pass before editing the unified document, responding to
drift, rolling back, or bumping a version pin. The contract validator
proves the registry, the unified document, the propagation contract,
and the UI catalog are mutually consistent; a red contract layer means
the pipeline's inputs cannot be trusted.

Also confirm the GitOps applications under `gitops/apps/` report
healthy and synced before starting a change; propagating on top of an
already-degraded delivery state makes verification ambiguous.

## Config Change Flow

Every persistent configuration change travels the full pipeline in
order: edit, validate, render, commit, reconcile, verify. There is no
shortcut stage: a change that skips render is a hand edit, a change
that skips commit is untracked state, and a change that skips reconcile
is a direct API write. All three are contract violations.

### Edit the Unified Document

The unified document is the one place operators change configuration.
Start from `contracts/management/samples/VALID_UNIFIED_CONFIG.yaml` as
the canonical reference: it carries every domain (`retention`,
`tracing`, `tls`, `alerting`, `dashboards`, `graph`, `tenancy`,
`delivery`) and a complete `bindings` list.

Field rules that reject most first drafts:

- unified keys carry policy values only: retention days, ratios,
  toggles, and logical channel identities. Endpoints, hosts, webhook
  URLs, and credentials are forbidden in the document; they live in
  per-environment overlays or the secrets adapter.
- every leaf key present under `config` must be targeted by at least
  one binding; unbound keys are rejected.
- every binding's `system` must be a `system` id registered in
  `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml`; bindings to
  unregistered systems are rejected.
- every binding's `native_path.repo_path` must fall under one of the
  target system's registered `config_surface` paths.
- every `render_target` is a repository path under `gitops/`, never a
  live endpoint or mutable API target.

### Validate the Document

```bash
bash scripts/ci/validate_management_plane_contracts.sh
```

This enforces the JSON Schema
(`contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`) plus the three
cross-file rules the schema cannot express: binding targets registered,
every present key bound, and every binding resolving to a present leaf
key. The seeded rejection cases in
`contracts/management/samples/INVALID_UNIFIED_CONFIG_SAMPLES.json`
enumerate what the validator must refuse.

### Render

The renderer reads the schema-validated document and produces native
configuration files (Helm values, provisioning files, saved objects,
alert rules) at each binding's `render_target`. Rendering is the only
way native config under a registered config surface changes.

The renderer consumes the document as JSON (the sample's JSON twin is
the reference form). From the repository root:

```bash
PYTHONPATH=tools/obskit python3 -m obskit render \
  --document <unified-document.json> \
  --contracts-dir contracts \
  --repo-root . \
  --commit-message-out /tmp/config_render_commit_msg.txt
```

The run validates the document against the schema, enforces the
cross-file binding rules, writes every binding's `render_target`
through its cataloged strategy
(`contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`),
refreshes `gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json` (the digest
manifest that carries the marker for comment-incapable formats), and
prepares the commit message. A document that fails validation renders
nothing (exit 2).

Prove idempotency before committing - an unchanged document must
report no diff:

```bash
PYTHONPATH=tools/obskit python3 -m obskit render \
  --document <unified-document.json> \
  --contracts-dir contracts \
  --repo-root . \
  --check
```

Exit 0 prints the no-diff, no-commit line; exit 3 lists targets that
would change (expected only when the document actually changed).

Invariants to hold the render to:

- deterministic: identical document bytes in, byte-identical rendered
  output out. No timestamps, hostnames, random identifiers,
  map-ordering drift, or renderer-version banners in rendered content.
- idempotent: an unchanged document renders no diff and produces no
  commit.
- every rendered file carries the generated-file header marker
  (`GENERATED by the unified configuration renderer - DO NOT EDIT BY
  HAND.`). Formats that cannot carry comments (for example NDJSON
  saved-object bundles) carry the marker in a sibling manifest listing
  the rendered artifacts and their content digests.
- a render that fails schema validation, binding registration, the
  config-surface containment check, or lint is discarded, never
  committed.

### Commit

Rendered outputs land as one git commit per unified-document change
(directly or via pull request, per repository branch protection) on the
delivery branch the GitOps controller watches. The commit is the unit
of propagation, review, audit, and rollback.

Required commit trailers, binding the rendered commit back to the
document revision that produced it:

- `Unified-Config-Schema-Version`
- `Unified-Config-Document-Digest`

The renderer prepares a compliant message (`--commit-message-out`
above); commit the rendered outputs with it:

```bash
git add gitops/
git commit -F /tmp/config_render_commit_msg.txt
```

No rendered output may exist outside Git. A commit missing the
trailers fails the compliance rule
`fail_if_commit_missing_document_linkage`: without the linkage, drift
detection cannot prove which document produced the live state and
rollback cannot pick the correct revert target.

### Reconcile

The GitOps controller applies the committed rendered state; the
platform never bypasses it. Argo CD is the reference controller, and
any equivalent controller preserving the same delivery contract
satisfies the stage (`TR-10`). Per wrap method:

- `helm-values` and `kubernetes-crd`: the controller applies the
  committed values and manifests directly.
- `provisioning-api`: the reconciliation flow pushes the Git-rendered
  artifact through the system's own provisioning interface. The API is
  a delivery channel only; the Git artifact remains the source of
  truth.

### Post-Sync Verification

A change counts as propagated only after per-system checks pass:

1. Sync status is healthy for the owning GitOps application.
1. The rendered artifact digest matches the applied artifact.
1. The system health checks from the `TR-12` validation suite pass.
1. On a deployed instance, run the readiness probe:

   ```bash
   bash scripts/validate/post_install_readiness.sh
   ```

   This is a live-runtime probe under `scripts/validate/`; it never
   runs in repository-only CI.

Verification failures block promotion of the same change to later
environments and trigger the rollback decision (see
[Rollback](#rollback)).

### Direct API Write Prohibition

Direct mutable API writes for persistent configuration are forbidden on
every wrapped system, including writes made through a wrapped UI's own
admin screens. Persistent configuration is anything that must survive a
pod restart, a re-render, or a reconcile: Helm values, provisioning
artifacts, index templates, ILM policies, security roles, saved
objects, alert rule definitions, sync policies. All of it changes only
via the unified document and this pipeline.

The only operations out of scope are transient runtime operations that
carry no persistent configuration and expire or vanish on their own:

- alert silence or acknowledge (time-bounded mute of a firing alert
  during an incident)
- task or job control (retry, cancel, or re-run of a failed task or
  sync job)
- session-scoped UI state (per-user UI preferences not persisted as
  platform config)
- diagnostic reads and exports (read-only queries, support bundles,
  on-demand snapshots)

> [!WARNING]
> A transient operation must never survive a re-render or be used to
> smuggle in persistent state. If the effect is wanted permanently, it
> goes through the unified document. Likewise, never hand-edit a
> render target: every rendered file carries the generated-file header
> marker, and a render target whose content does not match its
> renderer output is drift, even inside Git.

## Drift Response

### How Drift Surfaces

Rendered configuration committed to Git is the source of truth. Live
state that diverges from the last verified rendered commit is drift, no
matter how it was introduced: a direct API write, a hand edit, a
controller failure, or a wrapped-system self-mutation. Three detection
paths run continuously:

| Path                      | Mechanism                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------- |
| `controller-diff`         | GitOps controller live-versus-desired comparison (for example Argo CD `OutOfSync`)   |
| `provisioning-surface-diff` | Re-read of the applied provisioning-api artifact, digest-compared against Git       |
| `render-idempotency-check`  | Re-render of the current document must produce no diff against committed targets    |

Drift surfaces through the `TR-12` meta-monitoring alert path. The
alert rules live in the rendered bundle
`gitops/platform/search/dashboards/alerts/platform_health_rules.ndjson`
and must include these signals:

- `config-drift-detected-per-system`
- `reconcile-sync-failure`
- `render-idempotency-violation`

Produce the rendered-versus-live diff surface on demand with the
drift helper - it compares expected rendered bytes for the current
document against a target tree (a live-exported config checkout or
the delivery branch working tree) and never writes to it:

```bash
PYTHONPATH=tools/obskit python3 -m obskit drift \
  --document <unified-document.json> \
  --contracts-dir contracts \
  --repo-root <target-tree> \
  --report-out <target-tree>/drift_report.json
```

Exit 0 with `"status": "clean"` means no drift; exit 3 emits the
drifted entries (path, system, unified key, expected and actual
digests, signal) that the `TR-12` alert path consumes. The
`render-idempotency-violation` signal marks a hand-edited rendered
file or a renderer determinism regression; every other divergence is
`config-drift-detected-per-system`.

### Triage

1. Identify the affected system and config surface from the alert and
   the detection path that fired.
1. Classify the origin: a hand edit to a render target (idempotency
   check diff), a direct API write or system self-mutation
   (provisioning-surface digest mismatch), or a controller apply
   failure (`reconcile-sync-failure`).
1. Check whether a break-glass window is open for the affected system
   before acting (see below); drift during an authorized intervention
   is expected, not an incident.
1. Decide the outcome: re-sync (re-assert Git) or adopt (change the
   unified document and re-run the full pipeline). Live state is never
   adopted by editing render targets directly.
1. Confirm the drift alert clears after the chosen action and the
   affected system's post-sync checks pass again.

### Alert-Only Versus Automated Revert

The self-heal posture is profile-driven, so production and sandbox
clusters can differ deliberately. Allowed postures:

- `alert-only` (default): drift raises the meta-monitoring alert and
  waits for an operator decision, re-sync or adopt.
- `automated-revert`: the GitOps controller self-heals live state back
  to the rendered commit (for example Argo CD `selfHeal`), and
  provisioning-api surfaces are re-applied from Git. Automated revert
  never renders anything new; it only re-asserts the committed state.

`alert-only` is the safe default because automated revert without
operator awareness can fight an in-progress break-glass intervention;
`automated-revert` must be an explicit install-profile opt-in.

### Break-Glass Interaction

Break-glass access follows the admin-access profile `break_glass`
block (expiry bounded at 15-240 minutes, audited per `TR-09`). During
a break-glass window:

- expect drift alerts for the touched system; they confirm detection
  is working, and they must not be silenced beyond the incident-scoped
  transient mute allowed above
- in `automated-revert` posture, the controller may revert the
  intervention mid-incident; prefer clusters in `alert-only` posture
  for break-glass work, or accept that reverts will race the operator
- any change that must outlive the window is persistent configuration
  and goes through the unified document afterward; the window closing
  plus a re-sync must return live state to the rendered commit

## Rollback

### Rollback Mechanisms

Rollback is a Git operation. There is no out-of-band restore path for
persistent configuration; the revert travels the same pipeline
(render, commit, reconcile, verify).

1. Unified-document revert (preferred): `git revert` of the
   unified-document change, then re-render. Deterministic rendering
   makes rollback provable: the rolled-back document must re-render
   byte-identically to the previously committed rendered state.

   Execute it with the rollback subcommand, which re-renders the
   prior document revision through the identical render-and-commit
   pipeline (there is no separate apply channel). `dry-run` is the
   default mode and writes nothing:

   ```bash
   git show <prior-rev>:<unified-document.json> > /tmp/prior_doc.json
   PYTHONPATH=tools/obskit python3 -m obskit rollback \
     --document /tmp/prior_doc.json \
     --contracts-dir contracts \
     --repo-root . \
     --expected-manifest <previously-committed-manifest.json>
   ```

   The `--expected-manifest` digest-equality proof asserts revert
   plus re-render reproduces the previously committed rendered
   bytes; a mismatch refuses to proceed. Re-run with `--mode real`
   plus `--commit-message-out` to write the rollback render, then
   commit it with the prepared message exactly like a forward
   change.
1. Rendered-commit revert: `git revert` of the rendered-output commit
   on the delivery branch. Permitted as an emergency short path when
   the renderer itself is suspect; the unified document must be
   reverted to match before the next render, or the idempotency check
   fails.
1. GitOps revision rollback: pointing the GitOps application at the
   previous revision, per the `TR-12` requirement. Temporary
   containment only; it must be followed by a matching Git revert so
   the delivery branch head and the applied revision converge.

### Rollback Drill

Rehearse rollback with the operational drill, which is
mode-parameterized per `scripts/ops/` conventions with `dry-run` as
the default mode:

```bash
bash scripts/ops/run_rollback_drill.sh dry-run
```

The drill covers GitOps revision rollback and post-rollback health
verification. Run `real` mode only in non-production environments, and
close every real drill with a matching Git revert so the delivery
branch converges with the applied revision.

Rehearse the configuration-specific rollback (unified-document revert
plus deterministic re-render with the digest-equality proof) with the
Batch 19 drill, which runs entirely in a scratch copy of the offline
fixture tree:

```bash
bash scripts/ops/run_config_rollback_drill.sh
```

`dry-run` is the default mode; `real` executes the rollback re-render
in the scratch tree and verifies the tree returns byte-identically to
the prior rendered state. The drill refuses `real` mode when
`ENVIRONMENT=production`.

## Per-System Upstream Upgrade Procedure

> [!IMPORTANT]
> Never fork. Upgrades never patch images, vendor chart copies with
> source edits, or rebuild binaries. Every system upgrades through its
> OWN upstream mechanism as declared in the registry, and propagation
> never modifies wrapped-system code or charts (`gitops/charts/` is
> read-only for propagation). The registry is the sole version-pin
> authority: a pin that changes in any rendered output or GitOps
> application without a matching registry change fails
> `fail_if_version_pin_changed_outside_registry`.

### Common Upgrade Flow

1. Change the version pin in
   `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml` and, in the
   same commit, the `pinned_in` location the registry entry names.
   Upgrades are deliberate commits, never implicit drift from the
   upstream repository.
1. Let the system's own upgrade mechanism perform the rollout (see the
   table below); never apply the new version by hand.
1. Re-render the current unified document and re-validate it against
   the upgraded system's native config surface:

   ```bash
   bash scripts/ci/validate_management_plane_contracts.sh
   ```

   The upgrade is complete only after re-render and re-validation
   pass. A binding whose native locator moved or changed semantics is
   a breaking binding change (see below).

1. Run the post-sync verification checks from the
   [config change flow](#post-sync-verification) for the upgraded
   system.

### Per-System Mechanisms

| System                    | Upgrade mechanism    | Pin location                                                | Flow                                                                                     |
| ------------------------- | -------------------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| `opentelemetry-collector` | `operator`           | `gitops/platform/observability/values/otel-agent.yaml` and `otel-operator.yaml` | Bump the operator and managed-collector pins together in Git; the unmodified upstream operator performs the rollout |
| `opensearch`              | `helm-chart-upgrade` | Registry placeholder (`to-be-pinned`); concrete pin required in production | Self-managed: bump the pinned upstream chart version and reconcile. Provider-managed: upgrade through the provider's engine-version mechanism; the registry pin then tracks the engine version |
| `opensearch-dashboards`   | `helm-chart-upgrade` | Registry placeholder (`to-be-pinned`); concrete pin required in production | Bump the chart version in lockstep with the OpenSearch deployment; Dashboards must match the engine version |
| `grafana`                 | `helm-chart-upgrade` | `gitops/apps/grafana-application.yaml`                       | Bump the chart `targetRevision`; Argo CD reconciles the upgrade as a deliberate GitOps change |
| `neo4j`                   | `argocd-app-sync`    | `gitops/platform/graph/neo4j/neo4j_module.yaml`              | Bump the pinned image tag in the graph module manifest; the graph-stack Argo CD Application syncs the rollout |
| `argocd`                  | `helm-chart-upgrade` | Registry placeholder (`to-be-pinned`); bring-your-own install | Upgrade the operator-owned Argo CD installation via its upstream chart or install manifests; record the concrete version in production profiles |

Production note: an install profile with a production environment must
not enable a system whose registry `version_pin.status` is
`to-be-pinned` (`fail_if_production_pin_missing`). Replace the
placeholder with a concrete pin before production use.

Enabled adapters are wrapped systems too; they inherit the registry's
wrap-method enum and fork prohibition unchanged, and upgrade per their
own compatibility contracts under `contracts/adapters/` and the Batch
13 adapter procedures (see the
[Core Adapter Integrations Operator Guide](CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md)).

### Migration Notes for Breaking Binding Changes

A breaking binding change is any change that moves a native config
path, renames a locator, or changes value semantics, whether caused by
a unified-schema change or by a wrapped-system upgrade. Per `TR-17`:

- a breaking binding change requires a new
  `UNIFIED_CONFIG_SCHEMA_V<N>.json` version plus documented migration
  notes before release
  (`fail_if_breaking_binding_change_without_migration_notes`)
- never rename an existing contract file; version by suffix per
  `contracts/CONTRACTS_NAMING_CONVENTION.md`
- until the migration lands, hold the upgrade: an upgraded system whose
  bindings no longer resolve strands the unified document

## Single-Pane Access Operations

### UI Catalog Navigation

The unified plane surfaces exactly the `ui_catalog` ids from
`contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml` as its
navigation entries: `opensearch-dashboards-ui`, `grafana-ui`,
`neo4j-browser-ui` (graph-enabled mode only), and `argocd-ui`. Catalog
ids are stable API: they are never renamed within a contract version,
so bookmarks, runbooks, and navigation stay valid across endpoint or
exposure changes.

Endpoint hosts are environment data: every entry references an
admin-access profile `endpoints` key, never a literal URL or host. The
documented exception is Argo CD, a bring-your-own prerequisite whose
endpoint is the operator's existing installation; it must still meet
the same posture (TLS on, SSO against the same identity provider, no
anonymous access). The catalog and the registry move together: a UI is
on the pane if and only if its system is registered with `ui.exposed`
true.

### SSO Role Mapping Checks

Auth always flows through the admin access plane (`TR-03`): one
identity provider, no UI-local user databases for humans, and no
bespoke auth layers (a patched login flow or forked auth proxy fails
`fail_if_bespoke_ui_auth`). Verify that the plane groups map to native
roles per the contract:

| Catalog id                | `readonly_group` maps to                          | `admin_group` maps to                    |
| ------------------------- | ------------------------------------------------- | ---------------------------------------- |
| `opensearch-dashboards-ui`| Tenant/team reader roles plus `kibana_read_only`  | `all_access` via backend-role mapping    |
| `grafana-ui`              | Grafana Viewer                                    | Grafana Admin                            |
| `neo4j-browser-ui`        | Built-in reader role (or curated-dashboard fallback) | Built-in admin role                   |
| `argocd-ui`               | `role:readonly` RBAC policy                       | `role:admin` RBAC policy                 |

Checks to run after any identity or role-mapping change:

1. A `readonly_group` member reaches every cataloged UI and cannot
   write: no saved-object edits, no dashboard edits, no sync or
   rollback operations, no settings mutations.
1. An `admin_group` member holds the native admin role in each UI.
1. All role-mapping configuration is GitOps-committed rendered output
   (OpenSearch `roles`/`roles_mapping`, Grafana provisioning, Argo CD
   `argocd-rbac-cm`); a mapping changed through a UI admin screen is a
   direct API write and will surface as drift.
1. MFA and TLS posture match the deployed admin-access profile.

### Tenant Scoping Verification

Tenant scoping inside each UI follows the tenant isolation matrix
(`TR-16`); verify it per the
[SaaS Tenancy Runbook](SAAS_TENANCY_RUNBOOK.md) rather than duplicating
those procedures here. Pointers:

- OpenSearch Dashboards: per-tenant spaces (`tenant-<tenant_id>`);
  prove CTR-03 (no cross-tenant space access) per the tenancy runbook.
- Grafana: per-tenant org or folder scoping with tenant-scoped data
  sources; no cross-tenant folder or data source sharing.
- Neo4j Browser: one database per tenant, sessions pinned to it; prove
  CTR-05 (cross-database and system-database denial).
- Argo CD: per-tenant `AppProject` confinement; tenant principals get
  no Argo CD access by default.

Operator access that spans tenants, in any UI, is control-plane
break-glass only (CTR-07): named roles, bounded by the admin-access
profile `break_glass` block, audited per `TR-09` with the tenant id on
every record, never mapped to tenant principals.

## Troubleshooting and Failure Modes

- Document rejected by the validator: check for unbound leaf keys,
  bindings naming unregistered systems, bindings whose `unified_key`
  resolves to no present leaf, or a `native_path.repo_path` outside
  the target system's registered config surface. The seeded samples in
  `contracts/management/samples/INVALID_UNIFIED_CONFIG_SAMPLES.json`
  enumerate the rejection cases.
- Re-render of an unchanged document produces a diff: determinism
  violation (`fail_if_render_not_deterministic`) or a hand-edited
  render target. Do not commit the diff; restore the rendered state
  and fix the edit source or the renderer.
- Render interrupted mid-write: the renderer writes targets
  sequentially (not atomically), so a crash can leave uncommitted
  partial state in the working tree; a re-render or `git checkout` of
  the targets repairs it, and drift detection surfaces any remainder.
- A render target is missing the generated-file header marker: treat
  as a hand edit (`fail_if_render_target_hand_edited`); re-render to
  restore the marker and the renderer-owned content.
- Rendered commit rejected for missing trailers: add
  `Unified-Config-Schema-Version` and
  `Unified-Config-Document-Digest`; never merge a rendered commit
  without document linkage.
- Persistent drift re-appears after every re-sync: something is
  writing configuration through a mutable API (possibly a wrapped UI
  admin screen). Locate the writer via the audit trail; the fix is to
  move the change into the unified document, never to widen the
  transient-operation exceptions.
- Drift alert during a break-glass window: expected; confirm the
  window is authorized and audited, and that state converges back to
  the rendered commit when it closes.
- Automated revert fighting an operator intervention: the cluster is
  in `automated-revert` posture; pause the intervention, or perform it
  in an environment with `alert-only` posture. Never disable drift
  detection to win the race.
- Version pin differs between the registry and a rendered output or
  GitOps application: `fail_if_version_pin_changed_outside_registry`;
  reconcile by changing the registry (plus its `pinned_in` location)
  in one commit, never by editing the rendered output alone.
- Post-upgrade validation fails on binding resolution: the upgrade
  moved a native config path or locator. Hold or roll back the
  upgrade; ship a new schema version with migration notes before
  retrying (`fail_if_breaking_binding_change_without_migration_notes`).
- A production profile enables a `to-be-pinned` system: blocked by
  `fail_if_production_pin_missing`; record a concrete upstream version
  pin in the registry first.
- A proposed registry entry declares `wrap_method: fork` or an unknown
  wrap method: rejected by design (`fail_if_wrap_method_fork`,
  `fail_if_wrap_method_unknown`); rework the integration as
  configuration-only wrapping.
- A UI is registered (`ui.exposed: true`) but missing from the
  catalog, or cataloged without auth and tenancy blocks: contract
  violation caught by the consistency rules; fix the catalog, never
  publish a UI outside the plane.
- A cataloged UI carries a literal URL, hostname, or IP: fails
  `fail_if_hardcoded_endpoint` and the no-hardcoded-env-values gate;
  reference an admin-access profile `endpoints` key instead.

Related guides:
[Visualization Admin Access Plane Guide](VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md)
for the admin access plane the UI catalog builds on,
[SaaS Tenancy Runbook](SAAS_TENANCY_RUNBOOK.md) for tenant scoping and
isolation verification, [Rollback Runbook](ROLLBACK_RUNBOOK.md) for the
generic GitOps revision rollback procedure, and
[Validation Runbook](VALIDATION_RUNBOOK.md) for per-batch verification
entrypoints.
