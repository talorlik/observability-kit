# Onboarding Subscription Operator Guide

This guide defines the Batch 7 operator flow for workload onboarding and
subscription controls.

## Scope

Batch 7 validates:

- one-block onboarding through `observability-lib` contract
- subscription mode behavior for `passive`, `low-touch`, and `instrumentation`
- metadata policy enforcement for required ownership and environment fields
- CI schema checks for onboarding contract drift prevention
- onboarding lead-time measurement and friction reduction

## Artifacts

- `contracts/onboarding/ONE_BLOCK_ONBOARDING_VALIDATION.json`
- `contracts/onboarding/SUBSCRIPTION_MODES_VALIDATION.json`
- `contracts/onboarding/METADATA_POLICY_VALIDATION.json`
- `contracts/onboarding/ONBOARDING_SCHEMA.json`
- `contracts/onboarding/CI_SCHEMA_VALIDATION.json`
- `contracts/onboarding/ONBOARDING_LEAD_TIME_VALIDATION.json`

## Validation Entry Points

Run focused Batch 7 validation:

```bash
bash scripts/ci/validate_onboarding_subscription.sh
```

Run focused Batch 7 smoke validation:

```bash
bash scripts/ci/validate_batch7_smoke.sh
```

## Expected Outcomes

- one values block is sufficient for pilot onboarding
- each subscription mode shows expected telemetry behavior
- non-compliant metadata is denied with clear errors
- onboarding schema violations fail CI checks
- onboarding cycle time improves relative to baseline
