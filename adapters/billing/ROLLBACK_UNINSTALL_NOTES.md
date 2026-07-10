# Billing Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
billing adapters in `TB-22`.

## Scope

- Applies only to `adapters/billing/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps the vendor-neutral invoice-export contract and the metering core
  authoritative.

## Rollback Procedure

1. Disable the vendor billing backend (e.g. `stripe-reference`) in GitOps
   applications.
2. Fall back to the `file-export` backend so invoice export documents keep
   flowing with no vendor dependency.
3. Reconcile to the last known good revision for adapter manifests.
4. Confirm the core exporter still produces schema-conformant export
   documents and that no vendor push targets remain active.

## Uninstall Procedure

1. Remove billing adapter values from the GitOps desired state.
2. Delete adapter-managed secret references from the secrets backend
   configuration (never literal keys; only references exist).
3. Verify the metering collector, plan catalog, and invoice exporter still
   pass validation unchanged.
4. Verify no orphaned vendor credentials, account references, or push
   endpoints remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_commercial_contracts.sh`.
- Run `bash scripts/ci/validate_tenancy_contracts.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. Uninstalling
a billing adapter never touches metering records, the plan catalog, or the
tenant contracts; the core stays vendor-neutral throughout. The adapter
layer is additive, profile-driven, and reversible.
