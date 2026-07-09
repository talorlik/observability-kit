# SaaS Execution Prompt

Session-based execution of
`docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` (Batches 17-26):
ONE batch per fresh Claude Code session, multi-agent waves inside each
batch where the wave plan allows, strictly in numeric order. Batches
the plan marks parallel-eligible (19 alongside 18; 21 and 22 after 20)
are still run one per session - determinism over wall-clock.

The chain is self-perpetuating: every session ends by verifying
handoff prep and printing the continuation prompt for the next batch.
You normally never edit a prompt by hand - you paste what the previous
session printed. To regenerate one manually, take the kick-off prompt
below and replace the batch number.

Session flow:

1. Open a fresh session at the repository root, `main` checked out,
   clean tree.
2. Paste the prompt for the current batch (kick-off for 17, or the
   prompt the previous session printed).
3. The session runs the batch end to end, then prints the report,
   handoff verification, and the next prompt.
4. Clear context or close the session; repeat with the printed prompt.

## Kick-Off Prompt (Session 1 - Batch 17)

```text
Continue the Observability Kit SaaS productization plan. This session
executes Batch 17 and ONLY Batch 17, fully autonomously. I pre-approve
all actions; do not ask for permissions or decisions - record judgment
calls in docs/DECISIONS.md.

First read docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md for
product context, then invoke /run-batch 17 and follow it end to end:
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
- NEVER push main. Push the feature branch only.
- NEVER provision, modify, or delete cloud resources or clusters
  (anything billable). Live-cluster work uses only the disposable
  local kind harness with its isolated kubeconfig per the Batch 23
  harness contract; the OrbStack built-in cluster is the persistent
  dev stack only. Production-cluster validation is a deferred,
  user-initiated post-GA engagement.
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
3. The continuation prompt for the next batch in the sequence
   17, 18, 19, 20, 21, 22, 23, 24, 25, 26: print THIS ENTIRE PROMPT
   verbatim inside a text code fence with the batch number replaced.
   If this batch is 26, print the final completion report per
   SAAS_PRODUCTIZATION_PLAN.md section 9 (Definition of Done)
   instead. If this batch STOPPED, print this prompt again for the
   SAME batch, prefixed with a one-line note of what must be fixed
   before the rerun.
```

## Continuation Prompts (Sessions 2-10)

Each session prints the next session's prompt as its final output -
the same text as the kick-off with the batch number advanced. Paste it
into a fresh session as-is. If a session was interrupted before
printing its handoff, check
`docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md` and
`git log --oneline` on `main`: rerun the first batch in the sequence
that has no squash commit, by regenerating its prompt from the
kick-off block.

## After the Final Session

- Verify `docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md`
  shows all 27 batches passing.
- Verify the Batch 26 session printed the Definition of Done
  completion report and `docs/product/GA_READINESS_REVIEW.md` is
  signed.
- Review `docs/DECISIONS.md` for judgment calls made across the runs.
- `main` is intentionally unpushed; review and push it (or open PRs
  from the feature branches) on your own schedule.
- Production-cluster validation remains deliberately open: when you
  choose, provision a short-lived production-grade cluster, install
  with the `prod` overlay, run the readiness and
  reference-architecture conformance checks, capture evidence, and
  tear it down.
