# SaaS Execution Prompt

Copy the prompt below verbatim into a fresh Claude Code session opened
at the repository root, with `main` checked out and a clean tree. It
drives the full execution of
`docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` (Batches 17-26)
without stopping for confirmation.

> [!NOTE]
> The run is long. Each batch squash-merges to local `main` and captures
> decisions durably, so the session survives context compaction and can
> also be split: running `/run-batch <N>` per batch in separate sessions
> follows the identical method and is the lower-risk variant.

## The Prompt

```text
Execute the Observability Kit SaaS productization plan end to end,
fully autonomously. I pre-approve all actions; do not ask for
permissions or decisions - follow the plan's recommendations and record
every judgment call in docs/DECISIONS.md.

Load context first, in order:
1. CLAUDE.md
2. docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md (authoritative
   for scope, sequencing, milestones, and the Definition of Done)
3. .claude/commands/run-batch.md (the batch execution method)
4. docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md (wave
   plans, agent roles, file-scope rules)

Then execute Batches 17, 18, 19, 20, 21, 22, 23, 24, 25, 26 strictly in
that order. For EACH batch follow the /run-batch methodology in full:
per-batch worktree off local main; wave-based multi-agent
implementation with disjoint file scopes; spec-review subagent per
wave; an ADR before any technology choice; batch validator + smoke
wrapper + shared gates + full all-batches regression before merge;
squash-merge into local main from the primary checkout (never from
inside a worktree); remove the worktree and branch; append decisions to
docs/DECISIONS.md. The bootstrap exception applies: each new batch
creates its own smoke wrapper and registers itself in
validate_all_batches_with_report.sh, both command sheets, CI, and the
runbook link validator.

Rules that override everything else:
- NEVER push main. Push feature branches only.
- Never modify wrapped open-source code; wrap via Helm values, CRDs, or
  provisioning APIs. `fork` is a forbidden wrap method.
- Persistent configuration flows GitOps-only per
  contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml.
- Tenant isolation must never weaken; rerun
  scripts/ci/validate_tenancy_contracts.sh after any change touching
  isolation surfaces.
- Live-cluster work (Batches 23-24) uses a DISPOSABLE local cluster
  only (kind or k3d). Never target a shared or production cluster.
  Tear the cluster down after evidence capture.
- Gates: 3 fix attempts per gate, then up to 2 root-cause repair cycles
  per batch. If still red: commit WIP on the branch, leave the worktree
  intact, record the exact blocker in docs/DECISIONS.md, and continue
  with the next batch ONLY if it does not depend on the stopped one;
  otherwise stop and produce the failure report.
- Do not stop between batches for confirmation, and do not stop because
  the session is long. Durable state (merged main, docs/DECISIONS.md,
  docs/reports/validation/) survives context compaction: if you lose
  track, reload the four context documents plus
  docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md and resume
  from the first unmerged batch.

Done means the plan's Definition of Done (section 9) holds in full,
including: one squash commit per batch 17-26 on local main;
validate_all_batches_with_report.sh green across all 27 registered
batches; a fresh disposable cluster taken from empty to an onboarded
tenant using only the shipped tooling and documented flows; every
runtime-only completion check backed by captured evidence; the complete
docs/product/ tree published; versioned release artifacts produced; the
three to-be-pinned versions resolved.

Final output: a completion report with per-batch status and commit ids,
the final all-batches summary, links to every product document,
evidence locations, and residual risks with owners.
```

## After the Run

- Verify `docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md`
  shows all 27 batches passing.
- Review `docs/DECISIONS.md` for judgment calls made during the run.
- `main` is intentionally unpushed; review and push it (or open PRs
  from the feature branches) on your own schedule.
