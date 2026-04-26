# Production Activation Signoff Workflow

This workflow defines final production activation criteria for the Kagent +
Khook extension.

## Signoff Scope

- Install mode contract readiness.
- Compatibility and discovery determinism.
- Release validation suite coverage.
- Operator runbook completeness.
- Security and governance gates.

## Required Evidence Inputs

- `contracts/install/INSTALL_CONTRACT.schema.json`
- `install/profiles/ai-runtime/INSTALL_MODE_CONTRACTS_V1.json`
- `install/discovery-engine/mode_recommendation_rules.yaml`
- `install/profiles/compatibility/COMPATIBILITY_MATRIX.yaml`
- `tests/safety/RELEASE_VALIDATION_SUITE_V1.json`
- `tests/perf/ai_runtime/PERF_UPGRADE_SUITE_V1.json`

## Signoff Checklist

1. Validate install and compatibility contracts:

```bash
bash scripts/ci/validate_install_contract.sh
bash scripts/ci/validate_compatibility_and_modes.sh
```

1. Validate discovery and overlay determinism:

```bash
bash scripts/ci/validate_preflight_and_discovery.sh
```

1. Validate release gates:

```bash
bash scripts/ci/validate_kagent_khook_release.sh
```

1. Confirm runbook set is complete:

- `docs/runbooks/INSTALL_RUNBOOK.md`
- `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md`
- `docs/runbooks/ROLLBACK_UNINSTALL_RUNBOOK.md`

1. Record final signoff in release ticket:

- release version
- approver
- signoff timestamp
- evidence artifact links
- residual risk statement

## Go / No-Go Quantitative Thresholds

For activation to be `approved`, the release evidence must satisfy the
following thresholds. A single threshold breach forces `hold`; an
unresolved breach across two consecutive review windows forces `rejected`.

| Gate                                | Source                                                          | Threshold                                |
| ----------------------------------- | --------------------------------------------------------------- | ---------------------------------------- |
| MCP tool latency (p95)              | `tests/perf/ai_runtime/PERF_UPGRADE_SUITE_V1.json`              | `<= 750 ms`                              |
| MCP tool latency (p99)              | same                                                            | `<= 1500 ms`                             |
| Approval acceptance rate            | `gitops/platform/search/dashboards/saved-objects/RCA_AUDIT_OVERVIEW.ndjson` (`rca-approval-decision-trail`) | `>= 90 %` over the last 100 decisions    |
| Approval rejection rate (rolling)   | same                                                            | `<= 25 %` over the last 100 decisions    |
| Approval p95 latency                | `RCA_AUDIT_OVERVIEW.ndjson` (`rca-reviewer-latency-distribution`) | `<= 30 minutes` for write.high-risk      |
| Backtesting evidence pass rate      | `RCA_AUDIT_OVERVIEW.ndjson` (`rca-backtesting-evidence-pass-rate`) | `>= 95 %`                                |
| Action-gate scenario coverage       | `tests/safety/action_gates/ACTION_GATE_SCENARIOS_V1.json`       | All declared scenarios `expected_outcome` matched |
| Staging action-gate test pass rate  | `tests/staging/action_gates/STAGING_ACTION_GATE_RESULTS_V1.json` | `100 %` (>= 5 results, all `pass`)       |
| Release validation suite pass rate  | `tests/safety/RELEASE_VALIDATION_SUITE_V1.json`                 | `100 %`                                  |
| Restore drill recency               | `KAGENT_PERSISTENCE_CONTRACT_V1.yaml.backups.restore_drill_cadence_days` | `<= 90 days`                     |
| Approval flow contract presence     | `contracts/policy/APPROVAL_FLOW_V1.yaml`                        | `timeout_rules` and `escalation_rules` present |

If any quantitative threshold cannot be measured (e.g., dashboard data
unavailable), treat that gate as failed for signoff purposes.

## Activation Decision Outcomes

- `approved`: all gates pass and all quantitative thresholds above are
  met; production activation can proceed.
- `hold`: one or more gates fail or one or more thresholds breached;
  remediation required before activation.
- `rejected`: critical safety or governance blockers remain unresolved
  across two consecutive review windows.
