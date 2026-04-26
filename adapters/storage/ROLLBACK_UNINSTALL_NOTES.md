# Storage Backend Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
storage backend adapters in `IKAD-04`.

## Scope

- Applies only to `adapters/storage/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps core OpenSearch index and lifecycle policies authoritative.

## Rollback Procedure

1. Disable storage adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter manifests.
3. Confirm default OpenSearch index template and lifecycle policies stay active.
4. Confirm adapter-managed snapshot or template overrides stop reconciling.

## Uninstall Procedure

1. Remove storage adapter manifests from GitOps desired state.
2. Delete adapter-managed snapshot repositories and override templates.
3. Verify core logs index template and rollover policies still pass checks.
4. Verify no orphaned credentials, repository refs, or custom templates remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_logs_pipeline.sh`.
- Run `bash scripts/ci/validate_core_adapter_integrations.sh`.
- Run `bash scripts/ci/validate_storage_backend_adapters.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
