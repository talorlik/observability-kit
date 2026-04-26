# Provider Event-Source Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
provider event-source adapters in `IKAD-01`.

## Scope

- Applies only to `adapters/providers/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps the core platform behavior unchanged when adapters are disabled.

## Rollback Procedure

1. Disable provider adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter manifests.
3. Confirm Khook hooks continue receiving normalized core events.
4. Confirm no provider adapter resources remain in degraded state.

## Uninstall Procedure

1. Remove provider adapter manifests from GitOps desired state.
2. Delete provider adapter namespace resources if created.
3. Verify core Khook dispatch and case-file attachments still pass validation.
4. Verify no orphaned secrets or service accounts remain for adapter components.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_khook_trigger_scaffolding.sh`.
- Run `bash scripts/ci/validate_batch8_smoke.sh`.
- Run `bash scripts/ci/validate_provider_event_source_adapters.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
