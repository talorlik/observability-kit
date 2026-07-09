# Multi-Agent Batch Execution

This document optimizes the batches in
`docs/auxiliary/planning/TASKS.md` for multi-agent-driven development.
It is consumed by the `/run-batch` command (`.claude/commands/run-batch.md`)
and defines how one batch is decomposed into parallel execution waves,
which agent roles run them, and the rules that keep parallel work safe.

TASKS.md is authoritative. The wave plans below are derived from its
`Dependencies` lines as of 2026-07-09. If TASKS.md changes, recompute the
affected batch with the algorithm in this document and update the plan.

## Agent Roles

- **Orchestrator** - the main `/run-batch` session. Resolves the batch,
  builds waves, assigns file scopes, dispatches agents, runs gates,
  merges. It is the only writer of shared hotspot files.
- **Implementer agent** - one per task in a wave. Works only inside its
  assigned file scope in the batch worktree. Returns files changed,
  evidence for the task's completion check, and any deviations.
- **Spec reviewer agent** - after each wave, verifies each task against
  its TASKS.md `Completion check` and the batch's `TR-*` markers in
  `docs/auxiliary/planning/TECHNICAL.md`. Reports gaps, not fixes.
- **Code quality reviewer agent** - once per batch, before merge, per
  `superpowers:requesting-code-review`.

## Wave Derivation Algorithm

1. List the batch's numbered tasks and their `Dependencies` lines from
   TASKS.md.
2. Split dependencies into batch-level (for example `Batch 4`) and
   intra-batch (for example `Tasks 1-2`). Batch-level dependencies are
   preconditions checked in `/run-batch` Step 1; only intra-batch
   dependencies drive waves.
3. Wave N contains every unscheduled task whose intra-batch dependencies
   all sit in waves earlier than N. Repeat until all tasks are placed.
4. Within a wave, assign each task a file scope (directories and files it
   may create or edit) disjoint from every other task in the wave. If two
   tasks need the same file, move the later-numbered task to the next
   wave instead of sharing the file.
5. Shared hotspot files are excluded from every implementer scope; the
   orchestrator edits them after the final wave.

## Shared Hotspot Files

These files are touched by many tasks and are orchestrator-only:

- `scripts/ci/validate_all_batches_with_report.sh` (batch registry:
  `BATCH_IDS`, `BATCH_NAMES`, `VALIDATION_CRITERIA`, `SCRIPT_PATHS`)
- `.github/workflows/ci.yaml`
- `README.md` and `CLAUDE.md`
- `docs/auxiliary/planning/TASKS.md` and the command sheets under
  `docs/auxiliary/task_execution/`
- `docs/DECISIONS.md`

## Dispatch Prompt Contract

Every implementer dispatch prompt contains, in this order:

1. Batch id and task number, with the TASKS.md task text verbatim.
2. The task's `Completion check` verbatim - this is the agent's exit
   criterion and it must return evidence against it.
3. The batch's `TR-*` markers to read first, from the TASKS.md
   `Agent Cross-Reference Index`.
4. The constraints block from `/run-batch` Step 3, verbatim.
5. The assigned file scope: paths the agent may create or edit, and an
   instruction to stop and report instead of editing outside it.
6. The expected return format: files changed, completion-check evidence,
   commands run with observed output, deviations or "none".

## Wave Plans

Notation: `[a, b]` is one wave whose tasks run in parallel; `->`
separates consecutive waves. Task numbers are the TASKS.md numbering.

- Batch 1: `[1, 2] -> [3, 4] -> [5, 6]`
- Batch 2: `[1, 2] -> [3] -> [4, 5] -> [6]`
- Batch 3: `[1] -> [2, 3, 4] -> [5] -> [6]`
- Batch 4: `[1] -> [2] -> [3, 4] -> [5] -> [6]`
- Batch 5: `[1] -> [2, 3, 4] -> [5] -> [6]`
- Batch 6: `[1] -> [2, 3] -> [4, 5] -> [6]`
- Batch 7: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 8: `[1, 2, 5] -> [3, 4] -> [6]`
- Batch 9: `[1, 2, 3] -> [4] -> [5] -> [6]`
- Batch 9A: `[1, 4, 5] -> [2] -> [3] -> [6]`
- Batch 10: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 11: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 12: `[1, 4] -> [2, 5] -> [3] -> [6]`
- Batch 13: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 14: `[1] -> [2, 3] -> [4] -> [5] -> [6] -> [7, 8] -> [9] -> [10]`
- Batch 15: `[1] -> [2, 3, 4] -> [5] -> [6]`
- Batch 16: `[1] -> [2, 4] -> [3] -> [5] -> [6]`
- Batch 17: `[1] -> [2, 3] -> [4] -> [5] -> [6]`
- Batch 18: `[1] -> [2, 3] -> [4] -> [5] -> [6]`
- Batch 19: `[1] -> [2] -> [3, 4] -> [5] -> [6]`
- Batch 20: `[1] -> [2] -> [3, 4] -> [5] -> [6]`
- Batch 21: `[1] -> [2] -> [3, 4] -> [5] -> [6]`
- Batch 22: `[1] -> [2, 3] -> [4] -> [5] -> [6]`
- Batch 23: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 24: `[1] -> [2] -> [3] -> [4] -> [5] -> [6]` (single lane)
- Batch 25: `[1] -> [2, 4] -> [3] -> [5] -> [6]`
- Batch 26: `[1] -> [2, 3, 4] -> [5] -> [6]`

Single-lane batches gain nothing from parallel implementers: run them
inline in the orchestrator session and keep only the reviewer agents.
Waves of one task are also executed inline - an agent dispatch is only
worth its context cost when at least two tasks run concurrently or the
task is large enough to need a dedicated context window.

## Verification Ladder

1. Per task: the TASKS.md `Completion check`, run by the orchestrator
   when the wave returns.
2. Per wave: spec reviewer agent over the wave's diff.
3. Per batch: the batch validator and smoke wrapper, the shared gates,
   and the conditional gates listed in `/run-batch` Step 4.
4. Pre-merge: `scripts/ci/validate_all_batches_with_report.sh` as the
   full regression suite - earlier batches must stay green.

## Failure Handling

- An implementer that cannot meet its completion check returns a report;
  the orchestrator either re-dispatches with a corrected prompt (max 2
  re-dispatches per task) or executes the task inline.
- Two agents reporting edits to the same file is an orchestration bug:
  re-derive scopes, keep the earlier-numbered task's change, re-run the
  later task against the updated tree.
- Gate failures follow the `/run-batch` self-correction loop and its
  3-attempts-per-gate cap.
