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
