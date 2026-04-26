# Documentation

Documentation for the Observability Kit platform is organized into three
top-level areas. If you do not know where to start, the planning docs orient
you on the project as a whole; the runbooks tell you how to operate it; and
the validation reports tell you what currently passes.

## Areas

| Area                           | What lives there                                                                                  |
| ------------------------------ | ------------------------------------------------------------------------------------------------- |
| `docs/auxiliary/planning/`     | PRD, technical design, task plan, batch tasks, AI/MCP marker coverage, plan history (V1, V2)      |
| `docs/runbooks/`               | Operator guides (one per batch) and cross-cutting incident, rollback, install, validation runbooks |
| `docs/operations/`             | Production activation sign-off workflow and other process-only documents                          |
| `docs/onboarding/`             | Workload onboarding guide and worked examples                                                     |
| `docs/adapters/`               | Adapter enablement guide                                                                          |
| `docs/reports/validation/`     | Latest and historical validation report output (markdown + JSON) from `validate_all_batches_with_report.sh` |

## Quick links

- New to the project? Start at `auxiliary/planning/PRD.md` and
  `auxiliary/planning/TECHNICAL.md`.
- Looking for the authoritative platform plan? `auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md`
  (the V1 plan is retained for historical context only).
- Operating the platform? Start at `runbooks/README.md` for the runbook
  index, then drill into the per-batch guide you need.
- Verifying a release? Run `bash scripts/ci/validate_all_batches_with_report.sh`
  and read the latest report under `reports/validation/`.

## Change conventions

- When a new batch ships, add the per-batch runbook to `docs/runbooks/` AND
  to `docs/runbooks/README.md` AND to `scripts/ci/validate_runbook_links.sh`
  (which also expects the runbook path to appear in the top-level
  `README.md`).
- When a contract is renamed, update every reference under `docs/` in the
  same change so planning docs and runbooks do not drift from the
  contracts they describe.
- When a batch's task plan changes materially, update both
  `auxiliary/planning/TASKS.md` AND `auxiliary/planning/IMPLEMENTATION_TASKS.md`
  in the same change.
