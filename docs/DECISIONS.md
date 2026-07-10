# Decisions Log

Durable record of non-obvious decisions, deviations, gotchas, and
follow-ups captured at the end of each batch run. Appended by the
`/run-batch` command (Step 6); manual entries are welcome. Newest entry
first. Entry format:

```markdown
## YYYY-MM-DD - Batch <ID or n/a> - <short title>

- Decision: <what was decided or discovered>
- Why: <reasoning, trade-off, or evidence>
- Follow-up: <action for a future batch, or "none">
```

## 2026-07-10 - Batch 22 - Commercial Layer Semantics and Gotchas

- Decision: `docs/adr/ADR_0006_METERING_ARCHITECTURE.md` fixes
  derive-from-store metering: usage is computed from OpenSearch
  aggregation and stats surfaces plus validated tenant descriptors -
  no new collection path, no OTel processors, no request middleware.
  The collector is `services/commercial/` (package `commercialsvc`,
  stdlib-only, no optional extras; urllib covers the live OpenSearch
  path) with source/sink protocol duality so offline CI exercises the
  exact record-building code the live job runs.
- Why: TR-23 forbids new collection paths; deriving from the store
  bills what was retained (never charging for dropped data), keeps CI
  offline, and honors the TR-16 plane separation.
- Decision: the TR-16 telemetry reference vocabulary was NOT widened.
  A first draft added `derived-aggregate-value` as a fourth reference
  form; spec review flagged it as an unsanctioned extension of the
  vocabulary fixed by
  `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`.
  Resolution: usage record values are usage MEASUREMENTS, not
  telemetry references; the metering contract states this explicitly
  and keeps exactly the three canonical forms (index-name,
  document-count, content-digest). The tenancy contract was never
  touched.
- Decision: `active_tenants` is stored as per-tenant 0/1 activity
  records (never a platform-scoped record), because every usage
  record must carry `tenant_id`; exporters aggregate the count at
  read time. `retention_days` alone is descriptor-sourced (billed as
  configured capability, not observed storage age) - a deliberate,
  documented deviation from "sourced from telemetry".
- Decision: additive contract surfaces beyond the literal task list:
  `USAGE_RECORD_SCHEMA_V1.json`, `INVOICE_EXPORT_SCHEMA_V1.json`, the
  `commercialsvc.invoicing` module, and VALID/INVALID sample sets.
  They make the hard rules mechanically checkable (tenant_id
  mandatory, payload embedding rejected, vendor/currency fields
  rejected) and make the M4 "exported invoice for a sample period"
  evidence executable offline. Plan catalog prices in abstract units;
  currency assignment is adapter-side only.
- Decision: the plan catalog binds tiers bijectively (four plans,
  one per tier) with quota bounds in the exact Batch 15 field paths;
  `query_volume` has no tenant quota field, so its overage basis is
  full-quantity (ceil per 1000); dimensions without bounds are
  contract-documented as such.
- Gotcha: two review-caught validator holes worth remembering as
  patterns: (a) present-but-null required fields passed validation
  because per-field checks were gated on `is not None` - fixed with a
  `_MISSING` sentinel; (b) a dotted-path walker in the CI validator
  silently resolved nothing (accepting a seeded breach sample) -
  fixed plus a `resolved == 0` hard-fail guard so path bugs can never
  silently accept. The validator also pins every seeded rejection to
  its named `fail_if_*` rule so fixtures cannot drift into being
  rejected for incidental reasons.
- Follow-up (Batch 23): fix the live-path minors before the first
  live probe - `tenant_retention` defaulting missing descriptor
  fields to 0 (silent under-billing; must fail loudly),
  `OpenSearchBulkSink` raising bare RuntimeError instead of a
  MeteringError subclass, and `_TENANT_INDEX_RE` misattributing
  tenant slugs that end in a signal token. Live wiring of
  `control-tenancy-audit-*` and SLO query telemetry (query_volume
  source) lands with the Batch 23 harness; consider validating
  invoice exports at the adapter dispatch boundary, not only in CI.

## 2026-07-10 - Batch 21 - Management Portal Semantics and Gotchas

- Decision: `docs/adr/ADR_0005_MANAGEMENT_PORTAL_STACK.md` fixes the
  portal as `services/portal/` (package `portalsvc`): stdlib-typed
  core plus optional FastAPI `[api]` adapter (ADR-0004 posture) and a
  server-rendered `string.Template` no-JS frontend - no npm, no
  bundler, no vendored JS.
- Why: offline CI can neither install nor rebuild a frontend asset
  bundle; every contract-bearing behavior stays testable with system
  `python3`, and a richer SPA remains a frontend-layer swap behind
  the same core and JSON API.
- Decision: contract-first additions - new
  `contracts/management/PORTAL_CONTRACT_V1.yaml` (views, api_surface,
  authentication, fail_if rules) and an additive optional `portal`
  key in the admin-access profile `endpoints` schema. The portal's
  five lifecycle routes mirror the control plane's discrete
  operations (a generic transitions route was rejected in spec review
  as state-machine forking; `delegates_to` must name real
  operationIds).
- Decision: the contract JSON routes accept both raw-JSON and
  urlencoded form bodies (same routes, same semantics): dotted field
  names nest (`approval.approver`), empty fields drop (blank approval
  fieldset yields the contract's `approval-required` denial), and on
  form posts `actor` is ALWAYS overwritten with the authenticated
  subject so audit attribution cannot be forged from the browser.
  JSON API callers may still assert `actor` (Batch 20 API contract
  semantics).
- Decision: the Batch 20 caller_scope gap is closed -
  `tenantctl/api.py` binds `x-portal-tenant` to the service-layer
  `caller_scope` on every handler. Fail-closed on malformed input on
  both sides: portal rejects an empty tenant header
  (NotAuthenticated); tenantctl maps it to a scope matching no
  tenant.
- Gotcha: the portal config commit flow mutates the working tree at
  `repo_root` (persist document, re-render, prepare commit), so it is
  single-writer per `repo_root`: in-process `threading.Lock`, and the
  runbook mandates one replica/worker for the commit path (an
  earlier "scale portal replicas freely" claim was corrected in
  review).
- Follow-up: tenantctl should bind the audit `actor` to
  `x-portal-user` server-side when the header is present, so non-form
  callers cannot assert an arbitrary actor either - the portal is not
  the only possible caller. Candidate for Batch 22 alongside its
  metering/audit work.

## 2026-07-10 - Batch 20 - Tenant Control Plane Semantics and Gotchas

- Decision: `docs/adr/ADR_0004_TENANT_CONTROL_PLANE_SERVICE.md` fixes
  the control plane as `services/tenancy/` (package `tenantctl`):
  FastAPI is a thin adapter behind the `[api]` extra while ALL
  contract-bearing logic (contract-loaded state machine, replay,
  approval gating, audit, render planning) is a stdlib-only core so
  offline CI needs no dependencies. Transitions execute exclusively
  through the Batch 19 renderer (`execute_plan`/`changed_paths`,
  `owned-artifact` strategy); no strategy-catalog change was needed
  because tenant descriptors are not management-plane unified keys.
- Non-obvious calls: (1) per-tenant GitOps overlays render ONLY for
  `dedicated-stack` tenants - the lifecycle contract's
  `outputs_by_isolation_class` scopes the overlay to that class;
  shared classes get `render_action: not-applicable` plus isolation
  artifacts under `gitops/platform/tenants/<id>/isolation/`
  (additive, never touching core charts), while dedicated-stack
  isolation artifacts live inside the overlay so purge removes them
  with it. (2) The per-tenant Neo4j database artifact is gated
  declaratively with the `observability-kit.io/profile:
  graph-enabled` marker (the `browser-access.yaml` mechanism), not a
  planner branch: the tenant schema has no graph field and overlay
  generation may parameterize only by tenant-descriptor fields.
  (3) Approval timeout maps to error code `approval-invalid` - the
  API contract's 403 description explicitly covers timed-out
  approvals and adding a new enum value would change fixed API
  surface. Timeout denials carry the full escalation directive
  (chain, deny-after-chain, notify channels,
  `requires_change_management_callback` for `write.critical`).
  (4) Provision replay is converge-if-drifted for BOTH the overlay
  and isolation artifacts (code-review finding: the first cut
  re-planned only the overlay, so post-completion isolation drift
  survived a replay). (5) The file-backed store assumes a single
  writer per store root (atomic `os.replace` writes; documented in
  ADR-0004 and the runbook); a coordinated store is deferred to the
  live deployment batches.
- Gotcha for later batches: `validate_ai_boundary_contracts.sh`
  (run by BOTH batch 1 and batch 14 smoke bundles) scanned all of
  `services/` for datastore markers and failed on `tenantctl`
  docstrings naming Neo4j. Its scan root is now `services/mcp` -
  scoped to AI components per the AI boundary contract's own intent.
  Batch 21's `services/portal/` will NOT be scanned by it; if the
  portal embeds AI-runtime code paths, extend the scan roots
  deliberately.
- Follow-up: (1) Batch 21 must bind authenticated identity to the
  service's `caller_scope` argument - the HTTP adapter currently has
  no principal extraction and every HTTP caller is platform-scoped
  (safe only behind authenticated infrastructure). (2) Contract
  question flagged to the Batch 15 surface owners: `isolation_class`
  is mutable through CRUD today; changing it relocates the isolation
  directory on the next provision replay and orphans the old one -
  consider adding it to `x-immutable-fields` in a future contract
  revision.

## 2026-07-10 - Batch 19 - Config Renderer Semantics and Gotchas

- Decision: `docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md` fixes
  the renderer as the `obskit.configrender` subpackage (`obskit
  render|drift|rollback`), with target-preserving patching instead of
  whole-file templating: stdlib JSON parse/re-emit for JSON targets,
  a bounded line-based patcher for YAML targets (plain scalars only;
  block/folded/flow/anchored/quoted-with-`#` values are rejected
  loudly, as are duplicate keys and CRLF files), renderer-owned
  artifacts for directory targets, and presence-gated graph
  manifests. Strategy per binding pair is machine-readable in
  `contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml` and
  loaded at runtime; an uncataloged binding fails the render.
- Why: whole-file templates would dual-maintain native files owned by
  earlier batches (silent-fork risk); PyYAML would break the
  zero-dependency contract and destroy comments. Line-based patching
  preserves bytes, keeps first-adoption diffs minimal, and fails
  loudly outside its bounded subset (code-review finding: the first
  cut silently corrupted block scalars/anchors - now rejected and
  regression-locked in `tests/configrender/test_render_core.py`).
- Non-obvious calls: (1) the document is consumed as JSON (ADR-0002
  precedent); `contracts/management/samples/VALID_UNIFIED_CONFIG.json`
  is the committed JSON twin, semantic equality with the YAML sample
  enforced by `validate_config_renderer.sh` via the CI venv's PyYAML
  (the runtime itself never imports yaml). (2) `render_target`
  containment is enforced twice: cross-file rule 4 applies the
  registered-config-surface check to BOTH `native_path.repo_path` and
  `render_target`, rejecting `.`/`..` segments, plus resolve-time
  `is_relative_to` defense on every write including manifest,
  drift-report, rollback-report, and commit-message paths. (3) The
  repo's own `gitops/` tree is NOT adopted by Batch 19 - rendering is
  proven on fixtures; adoption happens when the first canonical
  per-instance unified document is committed (installer/portal flow,
  Batch 21+), so hand-authored native files keep their content until
  then. (4) The render manifest
  (`gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json`) is the sibling
  marker carrier for comment-incapable formats AND the drift input
  surface; drift attributes hand-edits of marker-carrying files as
  `render-idempotency-violation` and everything else as
  `config-drift-detected-per-system`. (5) Rollback is plan_render
  plus execute_plan of the prior document with an
  `--expected-manifest` digest-equality proof asserted before any
  write in both modes; `scripts/ops/run_config_rollback_drill.sh`
  (dry-run default) rehearses it in a scratch tree and refuses real
  mode in production. (6) `execute_plan` writes sequentially
  (non-atomic) - acceptable in the Git working-tree flow and
  documented in the runbook's troubleshooting section.
- Follow-up: Batch 20 reuses the renderer as a library
  (`plan_render`/`execute_plan`/`changed_paths` in
  `obskit.configrender.render`) for tenant overlay generation - do
  not re-implement rendering. The install-contract gap from Batch 18
  stands: no `gitops_revision` field yet (Application targetRevision
  hardcoded `main`).

## 2026-07-09 - Batch 18 - Guided Installer Semantics and Gotchas

- Decision: `docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md` fixes the
  installer as the `obskit.install` subpackage (stdlib-only, JSON
  answers files because the core cannot parse YAML, template-emitted
  YAML output, hand-rolled JSON-Schema subset validator that fails
  loudly on unimplemented keywords). Non-obvious calls beyond the
  ADR: (1) the rendered bootstrap Application is MULTI-SOURCE
  (`sources` with a `ref: values` entry) because a bare `$values`
  valueFile never resolves in a single-source Application - the
  committed `gitops/apps/platform-core-application.yaml` carries
  that exact pre-existing bug and still needs the same fix (spawned
  as a follow-up task); the documented operator convention is that
  the GitOps repo carries the kit's `gitops/` tree and the CONTENTS
  of `rendered/` land under `gitops_path`. (2) Contract-first fix:
  `contracts/install/INSTALL_CONTRACT_SCHEMA.json` (a Batch 1
  artifact) now requires `attached_services.opensearch_endpoint` for
  attach/hybrid - an empty attached_services object previously
  validated and would silently deploy the standalone default
  backend. (3) Overlay keys `baseDomain`/`deploymentMode`/
  `environment`/`profiles.*`/`attachedServices` are contract
  metadata with no platform-core chart binding yet; only
  `opensearch.endpoint` binds today - Batch 19's renderer owns the
  deep wiring. (4) Live-mode resume: cluster-reading steps always
  re-execute (no stable digest); the flow contract invariant is
  qualified accordingly. (5) Post-install readiness is
  scaffold-based until Batch 23; the runbook says so explicitly.
- Why: TR-19 parity/idempotency/GitOps-only invariants plus the
  stdlib-only posture inherited from ADR-0001; the Application and
  schema fixes came out of the wave-2 spec review and the pre-merge
  code review (both agents verified against live Argo CD semantics
  and empirical schema probing).
- Follow-up: fix the same `$values` bug in `gitops/apps/`
  Applications (task chip spawned); add a `gitops_revision` field to
  the install contract schema (targetRevision is hardcoded `main`) -
  input for Batch 19 or 26; Batch 19 binds the overlay metadata keys
  to native configs; Batch 23 replaces scaffold readiness with live
  evidence through the same finalize step.

## 2026-07-09 - Batch 18 - All-Batches Report Registration Gotcha

- Decision: registering a batch in
  `scripts/ci/validate_all_batches_with_report.sh` requires
  extending FOUR parallel arrays: `BATCH_IDS`, `BATCH_NAMES`,
  `SCRIPT_PATHS`, and `VALIDATION_CRITERIA`. Missing any of them
  fails the run at line ~114 with `unbound variable` only AFTER
  every earlier batch has executed (~2 minutes wasted per miss).
- Why: discovered when the Batch 18 registration extended only the
  first two arrays and the full regression failed post-Batch-17.
- Follow-up: every Batch 19-26 run registers itself the same way -
  extend all four arrays in one edit (also recorded in auto-memory).

## 2026-07-09 - Batch 17 - Discovery Executor Architecture Calls

- Decision: `docs/adr/ADR_0001_DISCOVERY_EXECUTOR_ARCHITECTURE.md`
  fixes the executor shape (Python 3.11+ `obskit` under
  `tools/obskit/`, stdlib-only core, Kubernetes client as a lazy
  `[k8s]` extra pinned to 36.0.2 - PyPI-verified latest, re-pin in
  Batch 25). Non-obvious calls beyond the ADR: (1) RBAC grants zero
  Secret access - stronger than the "metadata-only" TR-18 wording -
  because secret integrations are detected via CRDs and workloads;
  (2) the blocked-condition codes of GRADING_RULES.json map to
  evaluation dimensions via a `BlockedCodeBindings` dataclass whose
  field names are validated against the contract in BOTH directions
  at load (contract growth or shrinkage fails loudly) - the one
  sanctioned exception to "no decision rules in code", since the
  contract has no machine-readable code-to-dimension mapping;
  (3) preflight classifies missing-default-storage-class and
  no-gitops-controller as `warn` (exit 0) because the Batch 18
  installer remediates both; (4) reader accessors raising mid-check
  (live partial RBAC) yield `fail`/`check_execution_error`, never a
  traceback; (5) CronJobs were added to LiveReader, RBAC
  (`batch/cronjobs`), and READ_PERMISSIONS for live/fixture report
  parity.
- Why: TR-18 hard constraints (offline lint-only CI, byte-identical
  determinism, contract-sourced grading) plus code-review findings on
  live-mode robustness and parity.
- Follow-up: `kind` is deliberately absent from
  COMPATIBILITY_MATRIX.json distributions, so live runs on the kind
  evidence harness grade `blocked`/`unsupported_distribution`.
  Batches 18 and 23 must decide deliberately: add `kind` to the
  matrix as a conditional distribution (contract change with samples)
  or capture the blocked grade as expected harness evidence.

## 2026-07-09 - Batch n/a - Session-Based Batch Execution

- Decision: Batches 17-26 execute one per fresh session, in numeric
  order, with multi-agent waves inside each batch; the plan's
  cross-batch parallelism is deliberately unused. The execution
  prompt is now a self-perpetuating chain: a kick-off prompt runs
  Batch 17, and /run-batch Step 7 ends every session with handoff
  verification (clean main with squash commit, green report, worktree
  removed, decisions captured) plus the printed continuation prompt
  for the next batch (same batch with a fix note on STOPPED; the
  Definition of Done completion report after Batch 26).
- Why: owner choice of the lower-risk model - per-batch sessions
  bound context-compaction risk and orchestration complexity, and the
  durable per-batch merge discipline makes the two models converge on
  identical results anyway.
- Follow-up: none; recovery from an interrupted session is documented
  in SAAS_EXECUTION_PROMPT.md (rerun the first batch without a squash
  commit).

## 2026-07-09 - Batch n/a - Production Validation Deferred

- Decision: production-cluster validation is deferred to a separate,
  owner-initiated engagement after GA readiness. Batches 17-26
  complete entirely on the local stacks; autonomous runs must never
  provision, modify, or delete cloud resources. The EKS contexts in
  the local kubeconfig are stale remnants of a decommissioned
  cluster, not targets. The isolated-kubeconfig fencing in the
  harness contract stays: it costs one flag and protects exactly the
  end-stage moment when a live production cluster context appears.
- Why: owner direction (production tests at the very end, on a
  cluster spun up for that purpose); prevents an autonomous session
  from interpreting "production tests" as license to create billable
  infrastructure.
- Follow-up: post-GA, provision a short-lived production-grade
  cluster, install with the prod overlay, run readiness plus
  reference-architecture conformance, capture evidence, tear down.

## 2026-07-09 - Batch n/a - Deployment Stack Roles

- Decision: three cluster roles are now contract-fixed. Development
  stack: the OrbStack built-in Kubernetes cluster with the dev
  overlay (persistent, resettable, never an evidence source).
  Evidence harness: a disposable kind cluster on the local Docker
  engine (OrbStack), created and destroyed per Batch 23/24 run, using
  an isolated kubeconfig that refuses contexts it did not create.
  Production stack: any conformant multi-node cluster that grades
  supported against the Batch 25 production reference architecture
  (new Batch 25 Task 7); production installs use the same installer
  with the prod overlay - stacks differ by profile, never code path.
- Why: verified on the reference machine (OrbStack 2.2.1 running,
  kind installed, 24 GB RAM / 8 CPUs - sufficient for the dev-sized
  stack) and the default kubeconfig carries live EKS production
  contexts, so harness isolation must be structural, not
  convention-based.
- Follow-up: Batch 23 Task 1 implements the kubeconfig fencing;
  Batch 25 Task 7 delivers the reference architecture.

## 2026-07-09 - Batch n/a - SaaS Productization Backlog (17-26)

- Decision: authored Batches 17-26 and TR-18..TR-26 as the complete
  gap-closure backlog from validated blueprint to operational SaaS,
  governed by `SAAS_PRODUCTIZATION_PLAN.md` and executable via
  `SAAS_EXECUTION_PROMPT.md`. Key calls: runtime tooling is Python
  3.11+ under `tools/obskit/` and `services/` with dependency
  manifests separate from `requirements-ci.txt`; every implementation
  batch starts with an ADR; live-cluster batches (23-24) use
  disposable kind/k3d clusters and are never PR-gated; billing and
  model providers are adapter-class integrations to stay
  vendor-neutral; the Batch 26 filenames in TASKS.md are authoritative
  over the plan's documentation table.
- Why: keeps the productization work inside the same contract-first,
  wave-executed, evidence-gated methodology that built batches 1-16,
  and keeps the core cloud-agnostic while commercial and AI vendor
  choices stay swappable.
- Follow-up: execute batches 17-26 in order; reconcile the plan's
  documentation table if Batch 26 deliverables change during
  execution.

## 2026-07-09 - Batch 16 - Management Plane Semantics

- Decision: three load-bearing choices made during Batch 16. (1) The
  wrap-method enum defines `kubernetes-crd` broadly as GitOps-reconciled
  Kubernetes resources running the unmodified upstream image, which
  covers the platform-owned Neo4j module until it moves to the upstream
  chart. (2) OpenSearch, Dashboards, and Argo CD version pins are
  recorded as `to-be-pinned` with a fail-if rule requiring concrete
  pins in production profiles; Grafana (10.5.15), the collector
  (0.101.0), and Neo4j (5.26) pins were taken from actual repo
  artifacts. (3) Drift self-heal defaults to alert-only rather than
  automated revert because auto-revert can fight break-glass
  intervention.
- Why: keeps the registry truthful about what the repo actually
  deploys today while making the gaps machine-visible; upstream chart
  sources were verified live against each Helm repository index.
- Follow-up: pin OpenSearch, Dashboards, and Argo CD versions before
  any production profile ships; move the Neo4j module to the upstream
  chart when feasible.

## 2026-07-09 - Batch 15 - Tenancy Contract Semantics

- Decision: four load-bearing choices made during Batch 15. (1) Vector
  indices never co-mingle tenants and retrieval filters fail closed;
  graph isolation is always one Neo4j database per tenant - these are
  floors that apply even to the `shared-partition` class. (2) The
  lifecycle contract adds a `resume` transition beyond the four named
  in TASKS.md so `suspended` is provably non-destructive. (3) Denial
  fixtures mirror the isolation matrix's per-scenario semantics
  (`deny` for runtime scenarios, `reject` for config-validation ones)
  rather than a uniform `deny` literal. (4) The schema's
  `allowed_regions` prose was softened to non-normative because JSON
  Schema cannot express region-membership across fields; enforcement
  is procedural.
- Why: approximate-kNN filtering and Neo4j's lack of row-level
  security make store-level isolation the only defensible posture;
  the rest keep contracts machine-checkable and internally consistent
  (spec-review findings, wave 2).
- Follow-up: when a tenancy validator gains sample-level region
  checks, re-tighten the `allowed_regions` wording.

## 2026-07-09 - Batch n/a - Adopt /run-batch and Wave-Based Execution

- Decision: added the `/run-batch` command
  (`.claude/commands/run-batch.md`), adapted from the
  claude-code-ai-coach-assistant repository, and optimized batch
  execution for multi-agent-driven development via
  `docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`.
- Why: batches in `TASKS.md` carry explicit intra-batch dependencies, so
  independent tasks can run as parallel implementer agents in waves; the
  command makes batch runs hands-off, evidence-gated, and safe to run in
  fresh sessions. Baseline at adoption: all 15 batch smoke wrappers pass
  (`docs/reports/validation/` report of 2026-07-09).
- Follow-up: recompute a batch's wave plan whenever its `Dependencies`
  lines change in `TASKS.md`.
