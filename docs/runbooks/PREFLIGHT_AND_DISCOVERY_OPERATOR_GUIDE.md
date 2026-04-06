# Preflight And Discovery Operator Guide

This guide defines how to validate Batch 3 (`TB-03`) preflight and discovery
artifacts for `TR-04`, `TR-05`, and `TR-10`.

## Inputs

Batch 3 sample artifacts are stored in:

- `contracts/discovery/PREFLIGHT_REPORT_SAMPLE.json`
- `contracts/discovery/DISCOVERY_PROBES_SAMPLE.json`
- `contracts/discovery/GENERATED_CAPABILITY_MATRIX.json`
- `contracts/discovery/GENERATED_COMPATIBILITY_RESULT.json`
- `contracts/discovery/READINESS_REPORT_SCAFFOLD.json`

## What Is Validated

1. Preflight includes pass and fail check reporting.
1. Discovery probes include:
   - storage classes and default
   - ingress or gateway capability
   - GitOps controller detection
   - secret integration detection
   - workload inventory with onboardable candidates
1. Generated outputs include:
   - capability matrix with detected defaults
   - compatibility result grade and reasons
   - recommended deployment mode
   - remediation list contract
1. Readiness report scaffold is emitted with `dry-run-install` trigger.

## Command

Run the Batch 3 validation script:

```bash
bash scripts/ci/validate_preflight_and_discovery.sh
```

Expected success output:

```bash
Batch 3 preflight and discovery checks passed.
```

## Failure Handling

- If preflight summary counts mismatch checks, regenerate the preflight output.
- If probe defaults are missing, update discovery probe generation.
- If compatibility reasons have no remediation mapping, update:
  `contracts/compatibility/REMEDIATION_CATALOG.json`.
- If readiness scaffold trigger differs, enforce `dry-run-install` emission in
  generator logic.
