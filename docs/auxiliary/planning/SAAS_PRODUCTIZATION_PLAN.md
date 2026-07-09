# SaaS Productization Plan (Batches 17-26)

This plan maps every gap between the validated Observability Kit
blueprint (Batches 1-16, all smoke wrappers green) and an operational,
sellable SaaS product. It defines ten new batches (17-26), their strict
sequencing, milestones with acceptance evidence, the documentation
program, a risk register, and a testable Definition of Done. The batch
charters below are fixed; the executable task lists for Batches 17-26
live in `docs/auxiliary/planning/TASKS.md` alongside Batches 1-16, with
their technical requirements in `docs/auxiliary/planning/TECHNICAL.md`
(markers `TR-18` through `TR-26`).

## Table of Contents

- [1. Purpose and Product Vision](#1-purpose-and-product-vision)
- [2. Current State](#2-current-state)
- [3. Gap Analysis](#3-gap-analysis)
- [4. Execution Methodology](#4-execution-methodology)
- [5. Dependency Graph and Sequencing](#5-dependency-graph-and-sequencing)
- [6. Milestones](#6-milestones)
- [7. Documentation Plan](#7-documentation-plan)
- [8. Risk Register](#8-risk-register)
- [9. Definition of Done for an Operational SaaS Product](#9-definition-of-done-for-an-operational-saas-product)
- [10. Execution Entry Point](#10-execution-entry-point)

## 1. Purpose and Product Vision

The product is a unified, cloud-agnostic, plug-and-play observability
SaaS: one guided install turns any conformant Kubernetes cluster (cloud
or on-prem) into a multi-tenant observability platform with logs,
metrics, traces, vector search, a derived service graph, and
AI-assisted incident analysis - all operated from a single management
plane. This document exists because Batches 1-16 produced a validated
blueprint, not an operational service: every capability is proven by
contracts, fixtures, and CI validators, but nothing yet installs
itself, serves a tenant, meters usage, or ships as a versioned release.
Batches 17-26 close exactly that distance.

The vision holds these invariants, inherited from `TR-01` through
`TR-17` and non-negotiable for every new batch:

- One product, one install, one pane. Operators run a guided installer
  and manage everything - configuration, tenants, health, wrapped UIs -
  from a unified portal backed by a single schema-validated
  configuration document (`TR-17`).
- Wrap, never fork. Every bundled system (OpenTelemetry Collector,
  OpenSearch, OpenSearch Dashboards, Grafana, Neo4j, Argo CD, adapters)
  stays upgradable through its own upstream mechanism. Allowed wrap
  methods are `helm-values`, `kubernetes-crd`, `provisioning-api`, and
  `sidecar`; `fork` is rejected by validation.
- Multi-tenant with hard isolation. Cross-tenant access or leakage is a
  hard failure, not a policy preference (`TR-16`). Isolation uses only
  native mechanisms of the wrapped systems, is deny-by-default, and is
  proven by seeded denial fixtures in CI and by live denial evidence
  once Batch 23 lands.
- Cloud-agnostic core. OpenTelemetry is the sole collector, OpenSearch
  the single telemetry and vector store, Neo4j a derived graph tier,
  and delivery is Terraform + Helm + ArgoCD. No provider-specific
  service is mandatory; provider integrations live under
  `adapters/providers/`.
- Contract-first. Runtime code added by Batches 17-26 executes the
  existing contracts; it never bypasses or reinterprets them. Where a
  contract is insufficient, the contract changes first, with samples
  and seeded rejections, then the runtime follows.

## 2. Current State

Batches 1-16 are implemented and validated: all 17 batch smoke wrappers
(1-9, 9A, 10-16) pass, and
`scripts/ci/validate_all_batches_with_report.sh` reports green. The
repository is a complete, internally consistent blueprint. The honest
inventory splits three ways.

What exists as validated contracts and static artifacts:

- Install, compatibility, preflight, and discovery contracts under
  `contracts/install/`, `contracts/compatibility/`, and
  `contracts/discovery/`, with samples and seeded rejections.
- Telemetry pipeline contracts (collector topology, logs, metrics,
  traces), onboarding, security, SLO, visualization, vector, graph,
  risk/RCA, adapter, AI/MCP, and policy contracts - each with its own
  validator and smoke wrapper.
- Tenancy contracts under `contracts/tenancy/` (Batch 15): tenant
  schema, isolation classes, isolation matrix, lifecycle contract, and
  per-tenant overlay generation contract.
- Management-plane contracts under `contracts/management/` (Batch 16):
  wrapped-system registry, unified configuration schema, propagation
  bindings, UI catalog, and drift policy.
- GitOps delivery: the `platform-core` chart renders under every
  overlay, ArgoCD Applications and kustomizations are structurally
  validated, and ops drills exist in `dry-run` mode.

What actually runs today: bash validators with inline Python, `helm
lint` and `helm template` renders, seeded rejection checks, and
plain-`python3` test scripts invoked by their owning validators.
Nothing executes against a live cluster in CI, and every runtime-only
completion check is satisfied by declared fixtures rather than captured
evidence.

What does not exist at all - the subject of this plan: a preflight and
discovery execution engine, an installer, a configuration rendering
runtime, a tenant control-plane service, a management portal, usage
metering and billing, a live-cluster validation harness, a live AI/MCP
runtime deployment, a release pipeline with versioned artifacts, and
product documentation.

> [!IMPORTANT]
> Three wrapped-system versions are recorded as `to-be-pinned` in the
> Batch 16 wrapped-system registry: `opensearch`,
> `opensearch-dashboards`, and `argocd`. The registry carries a fail-if
> rule that blocks production profiles until concrete pins land.
> Grafana (10.5.15), the OpenTelemetry Collector (0.101.0), and Neo4j
> (5.26) are already pinned from repo artifacts. The three open pins
> must be resolved no later than Batch 25 (release engineering) and
> before any production profile ships (see `docs/DECISIONS.md`).

## 3. Gap Analysis

Each operational gap maps to exactly one closing batch. The batch set,
scopes, markers, and dependencies below are fixed.

| Operational gap today | Closing batch | Depends on |
| ---- | ---- | ---- |
| Preflight and discovery contracts have no runtime that executes them against a live cluster | Batch 17 | Batches 2, 3 |
| No installer: a human must hand-assemble preflight, grading, contract, render, and bootstrap | Batch 18 | Batch 17 |
| The Batch 16 propagation contract has no renderer; unified config cannot reach native configs | Batch 19 | Batch 16 |
| The Batch 15 tenant lifecycle is a contract with no executing service or API | Batch 20 | Batches 15, 19 |
| No single-pane UI; wrapped UIs, config, tenants, and health have no unified front door | Batch 21 | Batches 16, 19, 20 |
| No usage metering, plan/tier catalog, or billing; the product cannot charge a tenant | Batch 22 | Batch 20 |
| Runtime-only completion checks are declared, not executed; no live evidence exists | Batch 23 | Batches 17, 18, 19 |
| The AI/MCP layer is validated but has never been deployed or rehearsed live | Batch 24 | Batches 14, 23 |
| No releases: no semver, changelog, packaged charts, upgrade tests, SBOM, or license review | Batch 25 | Batch 23 |
| No product documentation and no GA gate | Batch 26 | Batches 17-25 |

### Batch Charters

#### Batch 17 - Discovery and Preflight Execution Engine [TB-17 | TR-04, TR-05, TR-18]

Runtime that executes preflight checks and discovery probes against
live clusters (Python package under `tools/obskit/`). Dependencies:
Batches 2, 3.

#### Batch 18 - Guided Installation Experience [TB-18 | TR-05, TR-14, TR-19]

Interactive and non-interactive installer wizard: preflight, then
compatibility grading, mode recommendation, install contract, render,
ArgoCD bootstrap, and readiness. Dependencies: Batch 17.

#### Batch 19 - Configuration Rendering Runtime [TB-19 | TR-10, TR-17, TR-20]

Deterministic renderer executing the Batch 16 propagation contract
(unified config to native configs), render-idempotency CI, and drift
tooling. Dependencies: Batch 16.

#### Batch 20 - Tenant Control Plane Service [TB-20 | TR-09, TR-16, TR-21]

API service (OpenAPI contract) executing the Batch 15 tenant lifecycle:
provision, suspend, resume, offboard, and purge, with overlay
generation and approval plus audit integration. Dependencies: Batches
15, 19.

#### Batch 21 - Unified Management Portal [TB-21 | TR-03, TR-17, TR-22]

The single-pane UI: navigation to wrapped UIs per the UI catalog,
unified config editing, tenant management, and a health overview; SSO
via the admin access plane. Dependencies: Batches 16, 19, 20.

#### Batch 22 - Metering, Billing, and Commercial Operations [TB-22 | TR-16, TR-23]

Usage metering from platform telemetry, a plan/tier catalog bound to
tenant tiers, a pluggable billing adapter class (reference adapter
under `adapters/`), and invoice export. Dependencies: Batch 20.

#### Batch 23 - Live-Cluster Validation and Evidence [TB-23 | TR-12, TR-24]

Disposable kind/k3d harness, full install via the Batch 18 installer,
execution of every runtime-only completion check (restore and rollback
drills, GUI smoke, live cross-tenant denials), captured evidence
replacing declared fixtures, and an optional nightly e2e workflow.
Dependencies: Batches 17, 18, 19.

#### Batch 24 - AI/MCP Runtime Activation [TB-24 | TR-13, TR-15, TR-24]

Deploy the AI runtime live (KAgent/KHook, MCP gateway), a pluggable
model-provider adapter, a live trigger-to-approval rehearsal, and
go/no-go signoff execution. Dependencies: Batches 14, 23.

#### Batch 25 - Production Operations and Release Engineering [TB-25 | TR-11, TR-12, TR-25]

Semver plus changelog plus tagged releases, packaged charts and OCI
publication, N-1 upgrade tests, platform SLOs productionized, image
scanning plus SBOM plus OSS license compliance review for commercial
distribution, DR productionization, and a release-gate checklist.
Dependencies: Batch 23.

#### Batch 26 - Product Documentation and GA Readiness [TB-26 | TR-14, TR-26]

Product docs tree (`docs/product/`): getting started, installation,
configuration, tenant admin, API reference from the control-plane
OpenAPI, pricing and packaging, and support playbooks; a docs-coverage
validator; and a GA readiness review. Dependencies: Batches 17-25.

## 4. Execution Methodology

Batches 17-26 run exactly the way Batches 15 and 16 ran in this
session. The methodology is not aspirational; it is the operating
procedure already encoded in `.claude/commands/run-batch.md` and
`docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`.

- Entry point: `/run-batch <ID>` is the canonical hands-off entry for
  every batch. Batch ids are open-ended: a batch is valid when its
  `## Batch <ID> -` section exists in TASKS.md and its smoke wrapper
  `scripts/ci/validate_batch<id>_smoke.sh` exists. Bootstrap exception
  for new batches: if the TASKS.md section exists but the smoke wrapper
  does not, AND creating that wrapper is one of the batch's own tasks,
  the batch is valid - the wrapper is a deliverable of the run. Every
  Batch 17-26 definition includes its smoke wrapper as a task, so first
  runs rely on this exception.
- Per-batch worktree: each batch runs in its own git worktree branched
  off the local `main` (never `origin/main`), named per the repo's
  branch conventions. Feature work never happens on `main` directly.
- Wave-based multi-agent implementation: the orchestrator derives waves
  from intra-batch task dependencies, assigns each task in a wave a
  file scope disjoint from every other task in the wave, and dispatches
  one implementer subagent per task in parallel using the dispatch
  prompt contract (task text verbatim, completion check, `TR-*`
  markers, constraints block, file scope, expected return format).
  Shared hotspot files (`validate_all_batches_with_report.sh`,
  `README.md`, `CLAUDE.md`, CI workflow wiring) are edited only by the
  orchestrator after the final wave.
- Spec review per wave: when a wave returns, the orchestrator runs each
  task's TASKS.md completion check and dispatches a spec-compliance
  review subagent that verifies the wave's diff against the completion
  checks and the batch's `TR-*` markers. Gaps are fixed before the next
  wave starts.
- Verification ladder and gates: per task, the completion check; per
  wave, the spec reviewer; per batch, the batch validator, the smoke
  wrapper, the shared gates (`validate_markdown.sh`,
  `validate_yaml.sh`, `check_no_hardcoded_env_values.sh`), and the
  conditional gates for whatever the batch touched (Helm lint and
  template per overlay, script permissions, runbook links, adapter and
  neutrality validators); pre-merge, the full regression suite
  `scripts/ci/validate_all_batches_with_report.sh` - earlier batches
  must stay green. Gate failures enter the self-correction loop with
  every deviation logged.
- Merge discipline: on success, the batch squash-merges into the local
  `main` as one clean commit, the branch and worktree are removed, and
  `main` is never pushed.
- Decision capture: every non-obvious decision, deviation, or gotcha is
  appended to `docs/DECISIONS.md` in that file's entry format, included
  in the squash-merge commit so it lands atomically with the work.
  Cross-batch gotchas additionally go to auto-memory, because each
  batch runs in a fresh session and anything not written durably is
  lost.
- ADR-first for technology choices: Batches 17-26 introduce real
  technology decisions the contract batches never faced - the Python
  packaging and CLI framework for `tools/obskit/`, the control-plane
  API framework, the portal stack, the billing adapter interface, the
  live-cluster harness, and the model-provider adapter. Every such
  choice gets an architecture decision record (per
  `engineering:architecture`) before implementation, recorded under the
  repo's ADR location and cross-referenced from `docs/DECISIONS.md`.

> [!NOTE]
> Because each batch runs in its own session with cleared context, the
> only carriers of intent between batches are TASKS.md, TECHNICAL.md,
> `docs/DECISIONS.md`, auto-memory, and this plan. Keeping those
> current is part of every batch's exit criteria, not housekeeping.

## 5. Dependency Graph and Sequencing

The default execution order is strictly serial:

```text
17 -> 18 -> 19 -> 20 -> 21 -> 22 -> 23 -> 24 -> 25 -> 26
```

Serial execution is the safe default because every batch's gates
include the full regression suite, and a single in-flight batch keeps
the blame surface small. The underlying dependency edges are looser
than the serial order and allow limited parallelism when session
capacity allows:

```text
Batches 2, 3 --> 17 --> 18 --------------.
Batch 16 -----> 19 ----------------------+--> 23 --> 25
                 |                       |     |
Batch 15 -------+--> 20 --> 21           |     v
                 |    |                  |    26  (needs 17-25)
                 |    +---> 22           |     ^
                 +-----------------------'     |
Batch 14 ----------------------> 24 <-- 23 ----'
```

- Batch 19 may start in parallel with Batch 18: 19 depends only on
  Batch 16, while 18 depends on 17.
- Batches 21 and 22 may run in parallel after Batch 20 completes: 21
  needs 16, 19, and 20; 22 needs only 20.
- All other batches remain serial. Batch 23 requires 17, 18, and 19;
  Batch 24 requires 14 and 23; Batch 25 requires 23; Batch 26 requires
  everything (17-25).

Parallel batches run in separate worktrees and separate sessions, and
both must pass the full regression suite against the then-current local
`main` before their squash-merges land; the second merger rebases its
worktree on the updated `main` and re-runs gates.

### Deployment Stacks

The plan targets three cluster roles, and no run may confuse them:

- **Development stack (laptop).** The OrbStack built-in Kubernetes
  cluster with the `dev` overlay: persistent, reduced sizing, single
  replicas, documented reset procedure. For day-to-day iteration
  only; never an evidence source. The reference development machine
  (OrbStack 2.x, 24 GB RAM, 8 CPUs, kind installed) is sufficient
  for the full dev-sized stack.
- **Evidence harness (disposable).** A kind cluster created on the
  local Docker engine (OrbStack) per Batch 23 run and destroyed
  after evidence capture. The harness uses an isolated kubeconfig
  and refuses contexts it did not create, so shared and cloud
  clusters are structurally unreachable.
- **Production stack.** Any CNCF-conformant multi-node Kubernetes
  cluster (managed or on-prem) that grades `supported` against the
  compatibility matrix and conforms to the production reference
  architecture delivered by Batch 25
  (`contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml`):
  HA topology, sizing tiers, storage and ingress profiles, backup
  and DR posture, `prod` overlay. Production installs use the same
  guided installer with the `prod` overlay - the stack differs by
  profile, never by code path.

> [!IMPORTANT]
> Production-cluster validation is deliberately deferred. Batches
> 17-26 complete entirely on the local stacks; no batch provisions
> cloud infrastructure, and autonomous runs must never create
> billable resources. After GA readiness, the owner initiates a
> separate engagement: provision a short-lived production-grade
> cluster (for example EKS via Terraform), run the guided installer
> with the `prod` overlay, execute the production readiness and
> reference-architecture conformance checks, capture evidence, and
> tear the cluster down. The stale EKS contexts currently present in
> the local kubeconfig belong to a decommissioned cluster and are
> not a target for anything.

## 6. Milestones

Each milestone is complete only when its acceptance evidence exists as
captured artifacts, not declarations.

### M1 - Installable (Batches 17-18)

A conformant cluster goes from empty to a running platform through one
guided flow. Acceptance evidence:

- Preflight report and discovery probe results produced by
  `tools/obskit/` against a live cluster, conforming to the
  `contracts/discovery/` schemas.
- Installer run (interactive and non-interactive) that chains
  preflight, compatibility grading, mode recommendation, install
  contract, render, ArgoCD bootstrap, and readiness, with each stage's
  output captured.
- A readiness report showing the platform healthy after install.

### M2 - Config-Operable (Batch 19)

The unified configuration document actually drives the platform.
Acceptance evidence:

- A unified config edit rendered deterministically to native configs
  per the Batch 16 propagation bindings.
- Render-idempotency CI green: rendering twice produces byte-identical
  output.
- Drift tooling correctly reporting both a clean state and a seeded
  drift.

### M3 - Multi-Tenant Operational (Batches 20-21)

Tenants are managed through an API and a portal, not by hand.
Acceptance evidence:

- Control-plane API (validated OpenAPI contract) executing provision,
  suspend, resume, offboard, and purge with idempotency, approval flow,
  and audit records carrying the tenant id.
- Generated per-tenant GitOps overlays with core charts unmodified.
- Portal reachable via SSO through the admin access plane, navigating
  every wrapped UI per the UI catalog, with unified config editing,
  tenant management, and a health overview.

### M4 - Commercial (Batch 22)

The product can charge for what it serves. Acceptance evidence:

- Usage metering derived from platform telemetry, attributed per
  tenant.
- Plan/tier catalog bound to tenant tiers from the tenancy contract.
- A reference billing adapter (under `adapters/`) exercising the
  pluggable adapter class, and an exported invoice for a sample period.

### M5 - Proven Live (Batches 23-24)

Every claim the blueprint makes is demonstrated on a real cluster.
Acceptance evidence:

- Disposable kind/k3d harness performing a full install via the Batch
  18 installer.
- Every runtime-only completion check executed live - restore and
  rollback drills, GUI smoke, live cross-tenant denials - with captured
  evidence replacing declared fixtures.
- AI runtime deployed live (KAgent/KHook, MCP gateway) with a
  model-provider adapter, a completed trigger-to-approval rehearsal,
  and an executed go/no-go signoff.
- Optional nightly e2e workflow in place.

### M6 - Sellable GA (Batches 25-26)

The product ships as a versioned, documented, license-clean release.
Acceptance evidence:

- A tagged semver release with changelog, packaged charts and OCI
  artifacts, image scans, SBOM, and a completed OSS license compliance
  review.
- N-1 upgrade test green; DR procedures productionized; platform SLOs
  productionized; release-gate checklist executed.
- The three open version pins (`opensearch`, `opensearch-dashboards`,
  `argocd`) resolved to concrete versions in the wrapped-system
  registry, with its fail-if rule passing for production profiles.
- Product docs tree published, docs-coverage validator green, and GA
  readiness review passed.

## 7. Documentation Plan

Two documentation tracks run through Batches 17-26.

Per-batch runbooks, as with every prior batch: each of Batches 17-26
delivers an operator runbook under `docs/runbooks/`, gated by
`validate_runbook_links.sh`, covering what the batch installed or
changed, how to operate it, and how to roll it back.

The Batch 26 product docs tree under `docs/product/` is the
customer-facing documentation set. Every deliverable and its audience:

| Document | Audience | Content |
| ---- | ---- | ---- |
| `docs/product/GETTING_STARTED.md` | Evaluators and first-time operators | What the product is, prerequisites, quickstart path to a running platform |
| `docs/product/INSTALLATION_GUIDE.md` | Platform operators and SREs | Full guided-installer reference: interactive and non-interactive flows, modes, preflight remediation |
| `docs/product/CONFIGURATION_GUIDE.md` | Platform operators | Unified configuration document reference, propagation model, drift handling |
| `docs/product/OPERATIONS_GUIDE.md` | Platform operators and SREs | Day-2 operations: upgrades, drills, drift response, evidence capture |
| `docs/product/TENANT_ADMIN_GUIDE.md` | SaaS operators and tenant administrators | Tenant lifecycle, isolation classes, quotas, overlays, offboarding and purge |
| `docs/product/END_USER_GUIDE.md` | Tenant end users | Using the portal and wrapped UIs: dashboards, queries, alerts |
| `docs/product/API_REFERENCE.md` | Integration engineers | Control-plane API reference, generated from the Batch 20 OpenAPI contract |
| `docs/product/PRICING_AND_PACKAGING.md` | Commercial and sales teams | Plan/tier catalog, metering dimensions, billing adapter options |
| `docs/product/SUPPORT_AND_ONBOARDING.md` | Support engineers | Triage flows, known failure modes, escalation paths, customer onboarding |

These filenames are the Batch 26 task deliverables in `TASKS.md`; that
batch definition is authoritative if the two ever drift.

Batch 26 also delivers a docs-coverage validator (following the
`scripts/ci/` validator pattern) that fails when a shipped capability
lacks its product doc or when a listed doc is missing, and wires it
into CI. All files follow the repo's markdown standards and naming
convention (ALL_CAPS with underscores).

## 8. Risk Register

| Risk | Impact | Mitigation |
| ---- | ---- | ---- |
| Context/window limits during autonomous execution: decisions made mid-batch are lost between sessions | Repeated mistakes, contradictory choices across batches | Durable capture in `docs/DECISIONS.md` and auto-memory as part of every batch's exit criteria; one batch per session; this plan and TASKS.md as the only carriers of intent |
| Live-cluster flakiness in Batches 23-24 (kind/k3d timing, image pulls, resource pressure) | Red gates that do not indicate real defects | Disposable, reproducible harness; deterministic waits over sleeps; retries with captured diagnostics; nightly e2e kept optional and never PR-gating |
| Upstream chart drift (OpenSearch, Dashboards, Argo CD, Grafana, Neo4j) breaking renders or installs | Install and upgrade failures outside our control | Concrete version pins in the wrapped-system registry with its fail-if rule; N-1 upgrade tests in Batch 25; drift surfaced via meta-monitoring per `TR-12` |
| License compliance for commercial bundling (OpenSearch, Neo4j community licensing terms, transitive deps) | Blocked or legally exposed commercial distribution | OSS license compliance review plus SBOM in Batch 25 as a release gate, before any GA claim |
| Billing-adapter vendor lock | Commercial stack coupled to one billing provider | Pluggable billing adapter class with a reference adapter under `adapters/`; the adapter contract, not the vendor API, is the product surface |
| Scope creep, especially in the portal | Batches balloon past session capacity and never merge | Portal v1 kept minimal by charter: navigation, unified config editing, tenant management, health overview - nothing else; any addition requires a TASKS.md change first |

## 9. Definition of Done for an Operational SaaS Product

The product is an operational SaaS when every item below passes as a
runnable check with captured evidence.

1. A fresh conformant Kubernetes cluster reaches a fully running
   platform using only the Batch 18 installer in non-interactive mode,
   with preflight, grading, mode recommendation, install contract,
   render, bootstrap, and readiness artifacts captured.
2. The same flow succeeds interactively, and every blocked preflight
   condition maps to an actionable remediation.
3. A unified configuration change propagates to native configs solely
   through the Batch 19 renderer and GitOps reconciliation; rendering
   is idempotent in CI and seeded drift is detected and reported.
4. A tenant completes the full lifecycle - provision, suspend, resume,
   offboard, purge - through the control-plane API, idempotently, with
   approval and audit records carrying the tenant id and purge
   evidence honoring retention rules.
5. Live cross-tenant denial checks pass on a real cluster for every
   scenario in the isolation matrix (indices, roles, dashboard spaces,
   vector indices, graph databases).
6. A paying tenant is representable end to end: usage metered from
   platform telemetry, tier bound to the plan catalog, and an invoice
   exported through the reference billing adapter.
7. The portal is reachable via SSO, navigates every wrapped UI in the
   UI catalog, and performs unified config editing, tenant management,
   and health overview against the live platform.
8. Every runtime-only completion check from Batches 1-16 has captured
   live evidence replacing its declared fixture, including restore and
   rollback drills and GUI smoke.
9. The AI/MCP runtime is deployed live, a trigger-to-approval rehearsal
   has passed with policy, redaction, and audit intact, and the
   go/no-go signoff is recorded.
10. The release pipeline produces versioned artifacts: a semver tag,
    changelog, packaged charts and OCI publication, image scans, and
    SBOM; the N-1 upgrade test passes; the OSS license review is
    complete.
11. The wrapped-system registry contains concrete version pins for
    `opensearch`, `opensearch-dashboards`, and `argocd`, and its
    fail-if rule passes for production profiles.
12. The complete product docs tree under `docs/product/` is published
    and the docs-coverage validator passes in CI.
13. `scripts/ci/validate_all_batches_with_report.sh` reports green for
    every batch, including 17-26, and the GA readiness review (Batch
    26) is signed off.
14. The production reference architecture is published and a
    production-grade cluster profile grades `supported` against it;
    the development stack and evidence harness roles are documented
    and enforced by the harness contract.

## 10. Execution Entry Point

Execution of this plan is driven by
`docs/auxiliary/task_execution/SAAS_EXECUTION_PROMPT.md` (authored
separately), which packages the per-batch session bootstrap - context
loading, `/run-batch` invocation, and inter-batch handoff - for
Batches 17-26. Each batch is launched in a fresh session with
`/run-batch <ID>`; the prompt document is the only additional context a
session needs beyond the repository itself.
