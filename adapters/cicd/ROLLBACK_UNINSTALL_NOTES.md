# CI CD Adapter Template Rollback And Uninstall Notes

This runbook describes reversible rollback and uninstall actions for optional
CI/CD adapter templates in `IKAD-06`.

## Scope

- Applies only to `adapters/cicd/` artifacts and derived adapter overlays.
- Does not modify core contracts, core CI gates, or core runtime ownership.
- Keeps core release and validation gate behavior authoritative.

## Rollback Procedure

1. Disable CI/CD adapter overlay references in GitOps applications.
2. Reconcile to the last known good revision for adapter template manifests.
3. Confirm core validation scripts remain unchanged and executable.
4. Confirm adapter-managed pipeline template resources stop reconciling.

## Uninstall Procedure

1. Remove CI/CD adapter manifests from GitOps desired state.
2. Delete adapter-managed pipeline templates and runner bindings.
3. Verify core batch validation commands still pass from default paths.
4. Verify no orphaned tokens, webhooks, or runner secrets remain.

## Validation After Rollback Or Uninstall

- Run `bash scripts/ci/validate_core_adapter_integrations.sh`.
- Run `bash scripts/ci/validate_gitops_neutrality.sh`.
- Run `bash scripts/ci/validate_cicd_adapter_templates.sh`.

## Core Contract Safety Statement

Core contracts remain unchanged by this optional adapter batch. The adapter
layer is additive, profile-driven, and reversible.
