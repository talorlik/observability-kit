# Operator Experience SLO Operations Guide

This guide defines the Batch 9 operator flow for dashboard taxonomy,
platform health alerting, SLI and SLO operations, and alert-noise tuning.

## Scope

Batch 9 validates:

- dashboard taxonomy for platform, service, and governance views
- platform health alerts for collector drops, ingest lag, and backend health
- SLI and SLO query stability for pilot services
- burn-rate and symptom alerts with runbook link coverage
- tabletop incident drill evidence with timeline and follow-up actions
- alert-noise and false-positive trend reduction across review cycles

## Artifacts

- `contracts/slo_ops/DASHBOARD_TAXONOMY_VALIDATION.json`
- `contracts/slo_ops/PLATFORM_HEALTH_ALERTS_VALIDATION.json`
- `contracts/slo_ops/SLI_SLO_QUERY_STABILITY_VALIDATION.json`
- `contracts/slo_ops/BURN_RATE_SYMPTOM_ALERTS_VALIDATION.json`
- `contracts/slo_ops/INCIDENT_DRILL_EVIDENCE_VALIDATION.json`
- `contracts/slo_ops/ALERT_NOISE_REDUCTION_VALIDATION.json`

## Validation Entry Points

Run focused Batch 9 validation:

```bash
bash scripts/ci/validate_operator_experience_slo.sh
```

Run focused Batch 9 smoke validation:

```bash
bash scripts/ci/validate_batch9_smoke.sh
```

## Expected Outcomes

- dashboards follow required naming prefixes and folder taxonomy
- platform health alerts route to expected channels
- SLI queries remain stable across repeated runs
- burn-rate and symptom alerts include runbook links for operators
- incident drills capture timeline and evidence artifacts
- false-positive rate and alert volume trend down over review cycles
