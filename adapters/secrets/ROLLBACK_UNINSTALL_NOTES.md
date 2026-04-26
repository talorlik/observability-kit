# Secrets Backend Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
secrets backend adapters in `IKAD-03`.

## Scope

- Applies only to `adapters/secrets/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps the core platform behavior unchanged when secrets adapters are disabled.

## Rollback Procedure

1. Disable secrets adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter manifests.
3. Confirm runtime references resolve to core defaults after adapter disablement.
4. Confirm adapter-managed secret mapping resources stop reconciling.

## Uninstall Procedure

1. Remove secrets adapter manifests from GitOps desired state.
2. Delete adapter-managed external secret mapping resources.
3. Verify core runtime workloads keep stable startup behavior.
4. Verify no orphaned secret bindings or stale auth references remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_batch2_smoke.sh`.
- Run `bash scripts/ci/validate_core_adapter_integrations.sh`.
- Run `bash scripts/ci/validate_secrets_backend_adapters.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
