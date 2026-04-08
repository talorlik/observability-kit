# Core Adapter Integrations Operator Guide

This guide defines Batch 13 implementation and validation scope.

## Scope

- adapter contract schema coverage for provider, backend, identity, secrets,
  network, and CI/CD classes
- profile-driven activation safety with explicit enable and disable controls
- identity, secrets, and network stub metadata requirements
- CI contract gating for adapter definitions and unsafe mutation prevention
- CI/CD neutrality checks while keeping Argo CD as the reference default
- adapter operations lifecycle for enablement, validation, disablement, rollback

## Artifacts

- `install/profiles/adapters/ADAPTER_CONTRACT.schema.json`
- `contracts/adapters/ADAPTER_CONTRACT_SCHEMA_COVERAGE.json`
- `contracts/adapters/PROFILE_ACTIVATION_SAFETY_VALIDATION.json`
- `contracts/adapters/IDENTITY_SECRETS_NETWORK_STUB_METADATA_VALIDATION.json`
- `contracts/adapters/ADAPTER_CI_CONTRACT_GATING_VALIDATION.json`
- `contracts/adapters/CICD_ADAPTER_NEUTRALITY_VALIDATION.json`
- `adapters/identity/STUB_METADATA.json`
- `adapters/secrets/STUB_METADATA.json`
- `adapters/network/STUB_METADATA.json`

## Validation Entry Points

```bash
bash scripts/ci/validate_core_adapter_integrations.sh
```

```bash
bash scripts/ci/validate_batch13_smoke.sh
```

## Lifecycle Operations

1. Enable adapter by explicit profile selection only.
2. Validate contracts and smoke checks before promotion.
3. Disable adapter via profile toggle if a safety check fails.
4. Roll back using adapter fallback behavior and keep core contracts unchanged.

## Expected Outcomes

- adapter schema coverage includes all required adapter classes
- profile-driven activation cannot mutate core contracts
- identity, secrets, and network stubs expose complete metadata
- CI blocks invalid adapter definitions and unsafe mutations
- neutrality checks pass with adapters enabled and disabled
- operations guidance is complete for enable, validate, disable, rollback
