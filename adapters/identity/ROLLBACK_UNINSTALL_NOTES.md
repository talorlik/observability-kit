# Identity Backend Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
identity backend adapters in `IKAD-02`.

## Scope

- Applies only to `adapters/identity/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps the core platform behavior unchanged when identity adapters are disabled.

## Rollback Procedure

1. Disable identity adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter manifests.
3. Confirm core service account bindings from policy contracts still resolve.
4. Confirm identity adapter resources no longer reconcile in failed loops.

## Uninstall Procedure

1. Remove identity adapter manifests from GitOps desired state.
2. Delete adapter-managed identity bindings and annotations.
3. Verify core AI runtime service accounts still satisfy policy checks.
4. Verify no orphaned identity secrets or stale trust bindings remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_batch2_smoke.sh`.
- Run `bash scripts/ci/validate_core_adapter_integrations.sh`.
- Run `bash scripts/ci/validate_identity_backend_adapters.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
