# Network And Ingress Adapter Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
network and ingress adapters in `IKAD-05`.

## Scope

- Applies only to `adapters/network/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps core network policy defaults and namespace boundaries authoritative.

## Rollback Procedure

1. Disable network adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter manifests.
3. Confirm core namespace allowlists and deny-by-default policy still apply.
4. Confirm adapter-managed ingress and route resources stop reconciling.

## Uninstall Procedure

1. Remove network adapter manifests from GitOps desired state.
2. Delete adapter-managed ingress, gateway, and route resources.
3. Verify core service exposure remains reachable only through approved paths.
4. Verify no orphaned load balancer rules or stale TLS references remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_batch2_smoke.sh`.
- Run `bash scripts/ci/validate_core_adapter_integrations.sh`.
- Run `bash scripts/ci/validate_network_ingress_adapters.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
