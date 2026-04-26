# DR Restore Runbook

## Scope

This runbook defines non-production restore drills for observability indices and
associated rollback validation steps.

## Restore Drill Preconditions

- Confirm target environment is non-production.
- Confirm latest backup snapshot is available.
- Confirm drill execution window is approved.

## Restore Drill Procedure

- Run `scripts/ops/run_restore_drill.sh dry-run` for CI smoke validation.
- Run real restore workflow during scheduled drills.
- Capture evidence artifacts: snapshot status, restore log, index health.

## Rollback Drill Procedure

- Run `scripts/ops/run_rollback_drill.sh dry-run` for CI smoke validation.
- Validate GitOps revision rollback and exporter route rollback scenarios.

## Uninstall Validation

- Run `scripts/ops/run_uninstall_validation.sh dry-run`.
- Verify no orphaned resources remain after uninstall simulation.
