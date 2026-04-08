# Implementation Batch Command Sheet

Use these commands to run implementation in controlled batches aligned to
`docs/auxiliary/planning/IMPLEMENTATION_TASKS.md`.
Run one batch at a time and require validation before moving forward.

## Batch Commands

| Batch | Command To Send | Validation Step (Required) |
| ---- | ---- | ---- |
| 1 | `Do batch 1: delivery foundation.` | Validate contract tests in CI, invalid fixture failure behavior, render checks for stubs, CI rejection of seeded invalid YAML or secrets, and runbook link validation. |
| 2 | `Do batch 2: compatibility and modes.` | Validate matrix grade mapping tests, profile fixture schema checks, and deterministic mode output tests. |
| 3 | `Do batch 3: preflight and discovery engine.` | Validate preflight test coverage for all check classes, full expected file generation from sample run, and smoke bundle pass on reference cluster profile. |
| 4 | `Do batch 4: collector core topology.` | Validate helm template plus cluster dry-run apply, required collector chains and export checks, and bounded-loss simulation metrics. |
| 5 | `Do batch 5: logs pipeline.` | Validate single-line and multiline fixture tests, sensitive fixture redaction or drop behavior, and clean template and policy install with dashboard render checks. |
| 6 | `Do batch 6: metrics and traces pipelines.` | Validate opted-in workload metrics indexing, trace ingest with sampling targets matching policy, and synthetic plus pilot correlation tests. |
| 7 | `Do batch 7: onboarding and subscription model.` | Validate one-block onboarding chart rendering, non-compliant onboarding rejection with clear output, and one-block onboarding CI smoke pass. |
| 8 | `Do batch 8: security, isolation, and resilience.` | Validate expected cross-team access denials, CI security contract and audit tests, and successful non-production restore plus rollback drills. |
| 9 | `Do batch 9: operator experience and SLO operations.` | Validate saved object import on test cluster, synthetic event alert routing, and drill evidence plus alert-noise trend checks. |
| 9A | `Do batch 9A: visualization and admin access plane.` | Validate signal-to-UI ownership contract linting, core UI provisioning path rendering, admin-access profile schema checks, and admin GUI TLS plus login smoke results. |
| 10 | `Do batch 10: vector foundations.` | Validate versioned extraction snapshot bundle output, OpenSearch vector write and queryability, and quality baseline plus governance checks. |
| 11 | `Do batch 11: graph foundation.` | Validate healthy core platform behavior with graph on and off, convergent repeated sync runs, and stale-data freshness alert triggering. |
| 12 | `Do batch 12: risk scoring and assisted RCA readiness.` | Validate deterministic score reruns, backtest and evidence bundle contracts, and approval evidence before RCA suggestion release. |
| 13 | `Do batch 13: core adapter integrations.` | Validate adapter contract schema coverage, profile-driven activation safety, identity and secrets and network stub metadata, CI contract gating, CI/CD neutrality checks, and adapter operations guide completeness. |

## Optional Strict Commands

Use these when explicit evidence is always required.

1. `Do batch X and include validation evidence only when all checks pass.`
2. `Do batch X, stop before merge, and show failed validations first if any.`
3. `Do batch X and produce a short validation report with pass/fail per check.`

## Stop/Resume Commands

- `Stop after current task and summarize status.`
- `Pause after batch X validation and wait for approval.`
- `Proceed to next batch.`

## Example

```markdown
REFERENCE: @docs/auxiliary/planning/IMPLEMENTATION_TASKS.md
TASKS:
- Do batch 8: security, isolation, and resilience.
- Validate expected cross-team access denials, CI security contract and audit tests, and successful non-production restore plus rollback drills.
```
