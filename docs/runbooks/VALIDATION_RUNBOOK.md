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
bash scripts/ci/validate_gitops_structure.sh
bash scripts/ci/check_no_hardcoded_env_values.sh
bash scripts/ci/validate_runbook_links.sh
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
- GitOps structure checks
- no hard-coded environment value checks
- runbook baseline checks
- secret scanning with gitleaks

## Exit Criteria

- Local checks complete with exit code `0`.
- CI checks pass in pull request flow.
