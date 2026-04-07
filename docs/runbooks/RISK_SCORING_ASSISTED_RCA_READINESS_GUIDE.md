# Risk Scoring And Assisted RCA Readiness Guide

This operator guide covers Batch 12 validation scope for deterministic risk
scoring and assisted RCA readiness.

## Scope

- Deterministic feature definitions for risk scoring inputs.
- Risk scoring job outputs and dashboard query readiness.
- Backtesting evidence with threshold tuning results.
- Hybrid retrieval evidence bundle integrity and traceability.
- Human approval and audit controls for recommendation flow.
- Controlled pilot go or hold decision evidence.

## Evidence Artifacts

- `contracts/risk_rca/DETERMINISTIC_RISK_FEATURES_VALIDATION.json`
- `contracts/risk_rca/RISK_SCORING_OUTPUTS_VALIDATION.json`
- `contracts/risk_rca/BACKTESTING_EVIDENCE_VALIDATION.json`
- `contracts/risk_rca/HYBRID_RETRIEVAL_EVIDENCE_BUNDLES_VALIDATION.json`
- `contracts/risk_rca/HUMAN_APPROVAL_WORKFLOW_VALIDATION.json`
- `contracts/risk_rca/PILOT_GO_HOLD_DECISION_VALIDATION.json`

## Validation Commands

Run full Batch 12 validation:

```bash
bash scripts/ci/validate_risk_scoring_assisted_rca.sh
```

Run Batch 12 smoke validation wrapper:

```bash
bash scripts/ci/validate_batch12_smoke.sh
```

## Operator Decision Checklist

- Risk features remain deterministic and reproducible across runs.
- Risk scores are generated per service and visible in dashboard views.
- Backtesting metrics satisfy minimum precision and recall thresholds.
- Evidence bundles contain both vector and graph links with lineage.
- No assisted recommendation can execute before explicit human approval.
- Pilot decision is documented as go or hold with stakeholder sign-off.
