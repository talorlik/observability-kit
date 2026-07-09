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
