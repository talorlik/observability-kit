# Validation Runbook

This runbook defines baseline verification entrypoints for Batch 1.

## Local Checks

Create and activate the Python virtual environment first:

```bash
source scripts/ci/setup_python_env.sh
```

Run policy and structure checks:

```bash
bash scripts/ci/validate_markdown.sh
bash scripts/ci/validate_yaml.sh
bash scripts/ci/validate_install_contract.sh
bash scripts/ci/validate_compatibility_and_modes.sh
bash scripts/ci/validate_preflight_and_discovery.sh
bash scripts/ci/validate_collector_core_topology.sh
bash scripts/ci/validate_logs_pipeline.sh
bash scripts/ci/validate_metrics_traces_pipeline.sh
bash scripts/ci/validate_onboarding_subscription.sh
bash scripts/ci/validate_security_isolation_resilience.sh
bash scripts/ci/validate_operator_experience_slo.sh
bash scripts/ci/validate_vector_foundations.sh
bash scripts/ci/validate_graph_foundation.sh
bash scripts/ci/validate_risk_scoring_assisted_rca.sh
bash scripts/ci/validate_gitops_structure.sh
bash scripts/ci/check_no_hardcoded_env_values.sh
bash scripts/ci/validate_runbook_links.sh
```

Run optional project-local Snyk code scan:

```bash
bash scripts/ci/snyk_code_scan_project.sh
```

You can also scan a subdirectory inside this project:

```bash
bash scripts/ci/snyk_code_scan_project.sh scripts/ci
```

Run focused Batch 1 smoke validation:

```bash
bash scripts/ci/validate_batch1_smoke.sh
```

Run focused Batch 2 smoke validation:

```bash
bash scripts/ci/validate_batch2_smoke.sh
```

Run focused Batch 3 smoke validation:

```bash
bash scripts/ci/validate_batch3_smoke.sh
```

Run focused Batch 4 validation:

```bash
bash scripts/ci/validate_collector_core_topology.sh
```

Run focused Batch 4 smoke validation:

```bash
bash scripts/ci/validate_batch4_smoke.sh
```

Run focused Batch 5 validation:

```bash
bash scripts/ci/validate_logs_pipeline.sh
```

Run focused Batch 5 smoke validation:

```bash
bash scripts/ci/validate_batch5_smoke.sh
```

Run focused Batch 6 validation:

```bash
bash scripts/ci/validate_metrics_traces_pipeline.sh
```

Run focused Batch 6 smoke validation:

```bash
bash scripts/ci/validate_batch6_smoke.sh
```

Run focused Batch 7 validation:

```bash
bash scripts/ci/validate_onboarding_subscription.sh
```

Run focused Batch 7 smoke validation:

```bash
bash scripts/ci/validate_batch7_smoke.sh
```

Run focused Batch 8 validation:

```bash
bash scripts/ci/validate_security_isolation_resilience.sh
```

Run focused Batch 8 smoke validation:

```bash
bash scripts/ci/validate_batch8_smoke.sh
```

Run focused Batch 9 validation:

```bash
bash scripts/ci/validate_operator_experience_slo.sh
```

Run focused Batch 9 smoke validation:

```bash
bash scripts/ci/validate_batch9_smoke.sh
```

Run focused Batch 10 validation:

```bash
bash scripts/ci/validate_vector_foundations.sh
```

Run focused Batch 10 smoke validation:

```bash
bash scripts/ci/validate_batch10_smoke.sh
```

Run focused Batch 11 validation:

```bash
bash scripts/ci/validate_graph_foundation.sh
```

Run focused Batch 11 smoke validation:

```bash
bash scripts/ci/validate_batch11_smoke.sh
```

Run focused Batch 12 validation:

```bash
bash scripts/ci/validate_risk_scoring_assisted_rca.sh
```

Run focused Batch 12 smoke validation:

```bash
bash scripts/ci/validate_batch12_smoke.sh
```

Run focused Batch 9A validation (visualization and admin access plane):

```bash
bash scripts/ci/validate_visualization_admin_access.sh
```

Run focused Batch 9A smoke validation:

```bash
bash scripts/ci/validate_batch9a_smoke.sh
```

Run focused Batch 13 validation (core adapter integrations):

```bash
bash scripts/ci/validate_core_adapter_integrations.sh
```

Run focused Batch 13 smoke validation:

```bash
bash scripts/ci/validate_batch13_smoke.sh
```

Run focused Batch 14 validation (AI/MCP layer — boundary, governance,
state, MCP catalog, scaffolding, and release gates):

```bash
bash scripts/ci/validate_ai_boundary_contracts.sh
bash scripts/ci/validate_ai_governance_contracts.sh
bash scripts/ci/validate_ai_state_contracts.sh
bash scripts/ci/validate_mcp_contracts.sh
bash scripts/ci/validate_ai_runtime_base_scaffolding.sh
bash scripts/ci/validate_mcp_read_path_scaffolding.sh
bash scripts/ci/validate_multi_agent_scaffolding.sh
bash scripts/ci/validate_khook_trigger_scaffolding.sh
bash scripts/ci/validate_action_gate_scaffolding.sh
bash scripts/ci/validate_kagent_khook_release.sh
```

Run focused Batch 14 smoke validation (aggregator wrapper for all of the
AI/MCP scripts above):

```bash
bash scripts/ci/validate_batch14_smoke.sh
```

Run the full report-generating aggregator across every batch (1-9, 9A,
10-14):

```bash
bash scripts/ci/validate_all_batches_with_report.sh
# Reports: docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.{md,json}
```

Run chart validation:

```bash
helm lint gitops/charts/platform-core
helm template platform-core gitops/charts/platform-core
```

## CI Checks

The `.github/workflows/ci.yaml` workflow enforces:

- markdown lint
- YAML lint
- Helm lint and template rendering
- install contract schema validation
- compatibility matrix and mode decision validation
- preflight and discovery output validation
- collector core topology validation
- logs pipeline validation
- metrics and traces pipeline validation
- onboarding and subscription validation
- security, isolation, and resilience validation
- operator experience and SLO operations validation
- visualization and admin access plane validation (Batch 9A)
- vector foundations validation
- graph foundation validation
- risk scoring and assisted RCA readiness validation
- core adapter integrations validation (Batch 13)
- AI agent boundary, governance, state, and MCP contract validation (Batch 14)
- AI runtime, MCP read-path, multi-agent, KHook, action-gate, and KAgent
  release scaffolding validation (Batch 14)
- GitOps structure checks
- no hard-coded environment value checks
- runbook baseline checks
- secret scanning with gitleaks

## Exit Criteria

- Local checks complete with exit code `0`.
- CI checks pass in pull request flow.
