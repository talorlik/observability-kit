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
