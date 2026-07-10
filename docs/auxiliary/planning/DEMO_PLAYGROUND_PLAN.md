# Demo Playground Plan (Batch 27)

This plan defines the post-GA demo and playground batch. It follows
the same methodology as
`docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` (Batches
17-26): a fixed charter here, the executable task list in
`docs/auxiliary/planning/TASKS.md` (Batch 27), technical requirements
in `docs/auxiliary/planning/TECHNICAL.md` (`TR-27`), wave-based
multi-agent execution via `/run-batch 27`, ADR-gated technology
choices, validators plus a smoke wrapper, and decision capture in
`docs/DECISIONS.md`.

## 1. Purpose

Batches 17-26 delivered an operational, GA-reviewed platform, but an
operator evaluating it has nothing to observe: no workloads, no
traffic, no incidents. Batch 27 closes that gap with a deployable
demo package that generates realistic telemetry and exercises every
product surface - dashboards, tenancy, metering, and the AI layer -
so the platform can be "played with" end to end on the local stacks.

## 2. Scope and Constraints

The batch inherits every hard constraint of the platform:

- OpenTelemetry is the sole collector; demo services never write to
  OpenSearch or Neo4j directly.
- The package is optional, additive, and removable: nothing in the
  core charts, contracts, or the ArgoCD bootstrap changes when it is
  deployed or torn down. It lives under `demo/`.
- Demo workloads onboard through the Batch 7 one-block subscription
  contract and deploy tenant-scoped, so isolation and metering are
  exercised on demo data.
- Sizing fits the OrbStack development stack and the disposable kind
  harness. The persistent dev stack remains never-an-evidence-source.
- Technology choices (workload sourcing, load tooling) are ADR-gated;
  wrap-never-fork applies to any upstream demo application.
- No cloud resources; everything runs on the local stacks.

## 3. Deliverables

Each operator need maps to exactly one TASKS.md Batch 27 task:

| Need | Task | Deliverable |
| ---- | ---- | ---- |
| Sample services of different kinds emitting real data | Task 2 | HTTP API, async worker, scheduled job, and datastore-backed service, all OpenTelemetry-instrumented, with a signal inventory |
| Simulated traffic, communication, and load | Task 3 | Declarative scenarios: steady baseline, burst, error-injection, latency-injection, plus a deployable load generator |
| Everything deployable as one easy package | Tasks 1, 2, 3 | `demo/` package with one-command deploy and teardown and a package README |
| Useful dashboards with the usual filters | Task 4 | Service overview, logs explorer, latency and traces, errors-and-alerts dashboards as code, filtered by time, tenant, service, namespace, and severity |
| A way to test the AI on captured data | Task 5 | Prompt pack bound to actual MCP catalog tools, per-scenario |
| Simple step-by-step setup instructions | Task 6 | `docs/product/PLAYGROUND_GUIDE.md` in the product docs tree |

Task 1 (ADR plus skeleton) precedes them all; Task 6 also delivers
the validators (`validate_demo_playground.sh`,
`validate_batch27_smoke.sh`), registration, and the runbook.

## 4. Execution Methodology

Identical to Batches 17-26: `/run-batch 27` is the canonical entry
point; per-batch worktree off the local `main`; waves per
`docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`
(Batch 27: `[1] -> [2, 3] -> [4, 5] -> [6]`); spec review per wave;
batch validator, smoke wrapper, shared gates, and the full
all-batches regression before merge; squash-merge into the local
`main` from the primary checkout; worktree and branch cleanup;
decision capture. The bootstrap exception applies: the batch creates
its own smoke wrapper and registers itself.

## 5. Definition of Done

Every item passes as a runnable check or a documented walkthrough:

1. `demo/` deploys with one command onto the development stack (and
   the disposable harness), and tears down with one command, leaving
   the platform unchanged.
2. All four workload kinds emit logs, metrics, and traces that are
   visible in the platform UIs under the demo tenant.
3. Each traffic scenario runs by name; the error-injection and
   latency-injection scenarios visibly change dashboards and produce
   risk-scoring or RCA-consumable data.
4. The four demo dashboards render from provisioning paths and carry
   the standard filters.
5. Every prompt in the AI prompt pack names real MCP catalog tools
   and returns grounded answers against captured demo data.
6. `docs/product/PLAYGROUND_GUIDE.md` takes an operator from a fresh
   or existing local platform to dashboards and AI answers without
   consulting any other document, and the product docs validator
   stays green with the guide registered.
7. `validate_demo_playground.sh`, `validate_batch27_smoke.sh`, and
   the full all-batches report (28 batches) are green.

## 6. Execution Entry Point

Run Batch 27 in a fresh session by pasting the kick-off prompt below
(same shape as
`docs/auxiliary/task_execution/SAAS_EXECUTION_PROMPT.md`).

```text
Continue the Observability Kit build. This session executes Batch 27
and ONLY Batch 27, fully autonomously. I pre-approve all actions; do
not ask for permissions or decisions - record judgment calls in
docs/DECISIONS.md.

First read docs/auxiliary/planning/DEMO_PLAYGROUND_PLAN.md for
context, then invoke /run-batch 27 and follow it end to end:
per-batch worktree off local main; multi-agent waves where the wave
plan in docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md
allows, sequential otherwise; spec review per wave; an ADR before any
technology choice; batch validator + smoke wrapper + shared gates +
full all-batches regression; squash-merge into local main from the
primary checkout (never from inside a worktree); worktree and branch
cleanup; decision capture. The bootstrap exception applies: the batch
creates its own smoke wrapper and registers itself in
validate_all_batches_with_report.sh, both command sheets, CI, and the
runbook link validator where its tasks say so.

Standing rules:
- Do NOT push main without my explicit instruction. Push the feature
  branch only.
- NEVER provision, modify, or delete cloud resources or clusters
  (anything billable). Live work uses the OrbStack dev stack for
  iteration and the disposable local kind harness (isolated
  kubeconfig, Batch 23 harness contract) for anything captured as
  evidence.
- Never fork or modify wrapped open-source code. Persistent
  configuration flows GitOps-only.
- Tenant isolation must never weaken; rerun
  scripts/ci/validate_tenancy_contracts.sh after any change touching
  isolation surfaces.
- Gates: 3 fix attempts per gate, then up to 2 root-cause repair
  cycles. If still red, follow the /run-batch failure path (WIP
  commit, worktree preserved, STOPPED report) - never merge red work.

End the session with exactly three things:
1. The /run-batch Step 7 report for this batch.
2. Handoff verification, each item confirmed with evidence: main is
   clean and carries this batch's squash commit; the all-batches
   report is green including this batch; the worktree and branch are
   removed; docs/DECISIONS.md carries this batch's entry (or "no new
   decisions to capture").
3. The completion report against the Definition of Done in
   docs/auxiliary/planning/DEMO_PLAYGROUND_PLAN.md section 5. If the
   batch STOPPED, print this prompt again for Batch 27 instead,
   prefixed with a one-line note of what must be fixed before the
   rerun.
```
