# Adapter Enablement Guide

This guide defines how to safely enable, validate, disable, and roll back core
adapter integrations.

## Scope

- Identity adapters
- Secrets adapters
- Network adapters
- Provider adapters
- Storage and backend adapters
- CI/CD adapters

## Preconditions

- Adapter profile contract passes schema validation.
- Core contract mutation is explicitly blocked.
- Required adapter stub metadata is present.
- CI neutrality checks are configured and passing.

## Enablement Flow

1. Select adapter through explicit profile activation only.
2. Render generated values for the adapter scope.
3. Run contract validations before rollout.
4. Execute batch smoke validations and verify pass status.

## Validation Commands

```bash
bash scripts/ci/validate_core_adapter_integrations.sh
```

```bash
bash scripts/ci/validate_gitops_neutrality.sh
```

```bash
bash scripts/ci/validate_batch13_smoke.sh
```

## Disable and Rollback Flow

1. Toggle adapter profile to disabled mode.
2. Reconcile manifests and preserve core defaults.
3. Run validation scripts to confirm core behavior.
4. Use adapter fallback behavior when rollback is required.

## Safety Guarantees

- Adapter activation is profile-driven and reversible.
- Core contracts remain authoritative and unchanged.
- Invalid adapter definitions are rejected in CI.
- Argo CD remains the reference default while CI/CD stays neutral.
