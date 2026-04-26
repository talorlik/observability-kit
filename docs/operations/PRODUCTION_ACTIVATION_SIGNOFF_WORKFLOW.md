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

## Activation Decision Outcomes

- `approved`: all gates pass, production activation can proceed.
- `hold`: one or more gates fail, remediation required before activation.
- `rejected`: critical safety or governance blockers remain unresolved.
