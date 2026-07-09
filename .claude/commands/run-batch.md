---
description: Execute one Observability Kit batch (1-14 or 9A) end to end with multi-agent waves - worktree, tasks, gates, self-correction, squash-merge. Usage /run-batch <ID>
argument-hint: <batch id, e.g. 7 or 9A>
---

# Run Batch

You are executing ONE batch of the Observability Kit build, fully
autonomously, in a fresh session. The batch id is: **$ARGUMENTS**

This command is the canonical hands-off entry point. It is self-contained:
do not assume any prior conversation context. Follow these steps in order.
Do not skip steps. Do not ask the user for confirmation unless a step
explicitly says to stop - this runs unattended.

## Step 0 - Resolve the Batch and Load Context

1. Normalize `$ARGUMENTS` to the id form used in the backlog headings: an
   integer without leading zeros (`07` -> `7`) or `9A` (case-insensitive,
   `9a` -> `9A`). Call it `ID`. Batch ids are open-ended: valid ids are
   exactly the `## Batch <ID> -` sections of
   `docs/auxiliary/planning/TASKS.md`. The batch is valid only if BOTH
   hold: that section exists, AND the smoke wrapper
   `scripts/ci/validate_batch<id>_smoke.sh` exists (id lowercased in the
   filename: `9A` -> `validate_batch9a_smoke.sh`). If `$ARGUMENTS` is
   empty or either check fails, STOP and report - list the batches that DO
   exist (`grep '^## Batch' docs/auxiliary/planning/TASKS.md` and
   `ls scripts/ci/validate_batch*_smoke.sh`). New batches are appended
   over time; do not assume an upper bound. Bootstrap exception: if the
   TASKS.md section exists but the smoke wrapper does not AND creating
   that wrapper is one of the batch's own tasks, the batch is valid -
   the wrapper is a deliverable of this run.
2. Read the batch's section in `docs/auxiliary/planning/TASKS.md`. Its
   numbered tasks, their `Dependencies`, and their `Completion check`
   lines are the canonical work definition - follow them verbatim.
3. Read the technical markers first, as TASKS.md mandates: look up the
   batch in the `Agent Cross-Reference Index` table of TASKS.md and read
   the listed `TR-*` sections of
   `docs/auxiliary/planning/TECHNICAL.md` before implementing.
4. Read the batch's row in
   `docs/auxiliary/task_execution/IMPLEMENTATION_BATCH_COMMAND_SHEET.md`.
   Its `Validation Step (Required)` column defines the evidence the
   final report must show.
5. Read `docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`.
   It holds the wave plan and orchestration rules for Step 3. TASKS.md
   dependencies are authoritative: if the wave plan disagrees with
   TASKS.md, recompute waves with the algorithm in that document.
6. Batch 14 only: also read the AI/MCP sub-plan and tasks under
   `docs/auxiliary/planning/kagent_khook/`.
7. The repository `CLAUDE.md` hard constraints apply to every task; the
   constraints block in Step 3 restates the non-negotiables.

## Step 1 - Preconditions

1. Confirm you are in the primary checkout at
   `/Users/talo/www/observability-kit` on branch `main` with a clean
   working tree (`git status --porcelain` empty). If not clean, STOP and
   report - do not stash or discard the user's uncommitted work.
2. Confirm the batch's dependency batches are green: for each batch named
   in the section's `Dependencies` lines, run its smoke wrapper
   (`scripts/ci/validate_batch<id>_smoke.sh`). A same-day pass recorded in
   `docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md` is
   acceptable evidence instead. If any dependency batch is red, STOP and
   report the gap.
3. Never push `main`. `git fetch` is not required.

## Step 2 - Create the Per-Batch Worktree

Pick the branch prefix by batch nature: `feature/` for new capability
work, `fix/` for regression repair, `docs/` for documentation-only,
`chore/` for CI, config, or dependency work, `refactor/` for
non-behavioral changes. Derive a short slug from the batch title.

```bash
git worktree add ../obs-kit-batch<ID>-<slug> -b <prefix>/batch<ID>-<slug> main
```

Branch from the LOCAL `main` ref, never `origin/main`. Do all subsequent
work inside that worktree. Invoke the `superpowers:using-git-worktrees`
skill to set this up correctly.

## Step 3 - Execute the Tasks in Waves (Multi-Agent)

Execution is wave-based: tasks whose intra-batch dependencies are all
satisfied run in parallel, one implementer subagent per task, all inside
the batch worktree. The wave plan and full orchestration rules live in
`docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`. The core
loop:

1. Take the batch's wave plan (or recompute it from TASKS.md
   dependencies). Assign each task in the current wave a file scope that
   is disjoint from every other task in the wave. If two tasks need the
   same file, move the later task to the next wave. Files on the shared
   hotspot list are edited only by you (the orchestrator), after the
   waves finish.
2. Dispatch one implementer subagent per task in the wave, in parallel,
   using the dispatch prompt contract from the orchestration document
   (task text verbatim, completion check, TR markers, constraints block,
   file scope, expected return format). A wave with a single small task
   is done inline - do not spawn an agent to edit one file.
3. When a wave returns, run each task's `Completion check` from TASKS.md
   and dispatch a spec-compliance review subagent following
   `superpowers:subagent-driven-development`. Fix gaps before starting
   the next wave.
4. After the final wave, make the orchestrator-only edits (shared hotspot
   files such as `scripts/ci/validate_all_batches_with_report.sh`,
   `README.md`, `CLAUDE.md`, CI workflow wiring), then request a code
   quality review via `superpowers:requesting-code-review`.

Every implementer prompt MUST carry this constraints block:

- OpenTelemetry is the sole collector; OpenSearch is the single telemetry
  and vector store; Neo4j is a derived graph tier, never a raw telemetry
  store.
- Delivery is Terraform + Helm + ArgoCD. The core is cloud-agnostic; no
  provider-specific service is mandatory. Provider integrations live
  under `adapters/providers/` only.
- Contract naming follows `contracts/CONTRACTS_NAMING_CONVENTION.md`.
  Never rename an existing schema file - validators, CI, and runbooks
  reference paths by name.
- Tenant and team isolation contracts (Batch 8, security policies) must
  never be weakened by later batches.
- Bash scripts use `set -euo pipefail`. Python uses type hints. Tests are
  plain `python3` scripts owned by their `scripts/ci/` validator - no
  pytest, no new test frameworks.
- Markdown files are `UPPERCASE_WITH_UNDERSCORES.md`, 80-column, and must
  pass `scripts/ci/validate_markdown.sh`.
- No hardcoded environment values
  (`scripts/ci/check_no_hardcoded_env_values.sh` must stay green).

## Step 4 - Gates With Self-Correction

Run the batch gates inside the worktree:

```bash
bash scripts/ci/validate_<batch-specific>.sh   # the batch's own validator
bash scripts/ci/validate_batch<id>_smoke.sh    # the batch smoke wrapper
bash scripts/ci/validate_markdown.sh
bash scripts/ci/validate_yaml.sh
bash scripts/ci/check_no_hardcoded_env_values.sh
```

Conditional gates, by what the batch touched:

- Helm chart changes: `helm lint gitops/charts/platform-core` and
  `helm template` with each overlay under `gitops/overlays/`.
- New or changed scripts: `scripts/ci/check_script_permissions.sh`.
- Runbook changes: `scripts/ci/validate_runbook_links.sh`.
- Adapter or neutrality changes (Batch 13 especially): the adapter
  sub-validators and `validate_gitops_neutrality.sh`. These are NOT
  CI-gated - a green PR does not prove them, so run them here.
- Before merge, always run
  `bash scripts/ci/validate_all_batches_with_report.sh` as the full
  regression suite: earlier batches must stay green.

If the environment is firewalled (no PyPI, no `helm`/`kubectl`), wrap any
validator with `bash scripts/dev/sandbox_validate.sh <validator>`; real
gates still must pass in a networked run before merge.

**Self-correction loop (full autonomy to pass gates):** if any gate
fails, invoke `superpowers:systematic-debugging`, fix the cause, and
re-run that gate. You have full autonomy to make gates green, including
reasonable scope adjustments. BUT: log every deviation from the TASKS.md
literal tasks in the final report (Step 7) so the user has an audit
trail. Do not silently drift.

**Retry cap: 3 attempts per gate.** If a gate still fails after 3 fix
attempts, go to Step 5b (failure path). Do not loop indefinitely. Do not
force a merge of red work onto `main`.

## Step 5a - Success Path: Commit, Squash-Merge, Clean Up

1. Commit in the worktree with a Conventional Commits message:
   `<type>(batch-<id>): <subject>` (e.g.
   `feat(batch-9a): admin access plane profile contract`).
2. Optionally push the feature branch to the remote (allowed by policy).
3. Squash-merge into local `main` in the primary checkout:
   `git merge --squash <branch>`, then commit with the same message.
   NEVER push `main`.
4. Remove the worktree and delete the merged branch. Invoke
   `superpowers:finishing-a-development-branch` to do this cleanly.
5. Go to Step 6.

## Step 5b - Failure Path: Preserve and Stop

If gates cannot pass within the retry cap, or you hit a genuine blocker
(missing capability, ambiguous requirement TASKS.md does not resolve):

1. Commit work-in-progress on the feature branch with message
   `WIP(batch-<id>): <one-line reason for stop>`.
2. Leave the worktree INTACT. Do NOT squash-merge. `main` must stay
   clean.
3. Go to Step 6, then Step 7 with status STOPPED.

## Step 6 - Capture Decisions and Insights

The user runs each batch in its own session and clears context between
batches, so any ad-hoc decision or insight not written to a durable store
is LOST. Capture before reporting - this is part of the batch contract,
not optional. Capture on BOTH the success and failure paths; insights
from a STOPPED batch are especially valuable.

Decide whether anything non-obvious occurred: a design decision made
mid-batch, a deviation from TASKS.md and why, a gotcha or constraint
discovered, a workaround, or a follow-up the next batch must know. If
genuinely nothing non-obvious happened, state "no new decisions to
capture" and skip. Do not invent entries to fill the log.

When there is something to capture:

1. **Repo-durable log:** append a dated entry to `docs/DECISIONS.md`
   following the format in that file's header. On the SUCCESS path,
   include this append in the batch's squash-merge commit so it lands on
   `main` atomically with the work. On the FAILURE path, commit it on the
   WIP branch.
2. **Auto-memory (only for cross-batch gotchas the next session must
   load):** if the insight changes how a FUTURE batch should behave,
   also write it to auto-memory: create or update a fact file under the
   project memory directory and add a one-line pointer to `MEMORY.md`.
   Prefer updating an existing related file over creating duplicates.
   Skip this for purely historical notes - those belong in DECISIONS.md
   only.

## Step 7 - Report

Produce the required output:

1. Status: COMPLETED (merged to `main`) or STOPPED (worktree preserved).
2. Files changed.
3. Waves executed and which subagents ran per wave (or "inline" and why).
4. Key implementation decisions.
5. **Deviations from the TASKS.md literal tasks** (the audit trail), or
   "none".
6. Completion-check and gate evidence: commands run and observed results
   (output, not assertion), covering the command sheet's required
   validation step.
7. Remaining risk or follow-up; for STOPPED, exactly what the human must
   do next.
8. What was captured to `docs/DECISIONS.md` and auto-memory (or "no new
   decisions to capture").

Keep the report concise. If COMPLETED, end by stating the next batch to
run (`/run-batch <next ID>`). The user can now safely clear context -
everything durable is already written.
