# Compatibility And Mode Operator Guide

This guide defines how to evaluate environment compatibility and choose a
deployment mode for Batch 2 (`TB-02`).

## Inputs

- Compatibility matrix:
  `contracts/compatibility/COMPATIBILITY_MATRIX.json`
- Profile catalog:
  `contracts/compatibility/PROFILE_CATALOG.json`
- Grading rules and sample outputs:
  `contracts/compatibility/GRADING_RULES.json`
- Mode decision table and deterministic samples:
  `contracts/compatibility/MODE_DECISION_TABLE.json`
- Remediation catalog:
  `contracts/compatibility/REMEDIATION_CATALOG.json`

## Decision Process

1. Collect cluster facts:
   - Kubernetes version
   - Kubernetes distribution
   - selected profile values
   - missing prerequisite list
2. Apply compatibility grading:
   - `supported` when no conditional or blocked conditions are present
   - `conditional` when only conditional conditions are present
   - `blocked` when any blocked condition is present
3. Apply the mode decision table using ordered rule priority.
4. Generate remediations for each blocked condition and conditional reason.

## Validation

Run the Batch 2 validation script:

```bash
bash scripts/ci/validate_compatibility_and_modes.sh
```

This script validates:

- compatibility matrix coverage
- profile catalog coverage and defaults
- grading outputs from sample cluster evaluations
- deployment mode deterministic outputs from sample inputs
- remediation mapping coverage for blocked and conditional paths

## Operator Notes

- Use `quickstart` for low-friction evaluation.
- Use `attach` when a compatible existing stack must be reused.
- Use `standalone` when full in-cluster deployment is required.
- Use `hybrid` when in-cluster collectors are required with shared services.
