# CLAUDE.md

This file provides guidance to Claude Code (`claude.ai/code`) when working
with code in this repository.

## Project Overview

Observability Kit is a portable, plug-and-play observability intelligence
platform for AWS EKS clusters. It delivers a phased path from core
observability to AI-assisted incident analysis, structured as sequential
"Batches" (currently 13+).

Hard constraints:

- OpenTelemetry is the sole collector for logs, metrics, and traces
- Amazon OpenSearch is the single telemetry and vector store
- Amazon OpenSearch Ingestion (OSI) is the managed ingest path
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform + Helm + ArgoCD Applications

Primary languages: Bash, Python, Terraform, Helm/YAML.

## Common Commands

### Setup

```bash
bash scripts/ci/setup_python_env.sh
# creates .venv with CI dependencies
```

### Linting

```bash
bash scripts/ci/validate_markdown.sh
bash scripts/ci/validate_yaml.sh
helm lint gitops/charts/platform-core
bash scripts/ci/check_no_hardcoded_env_values.sh
```

### Running All Validation Batches

```bash
bash scripts/ci/validate_all_batches_with_report.sh
# Reports written to docs/reports/validation/
```

### Running a Single Batch

Each batch has its own script:

```bash
bash scripts/ci/validate_install_contract.sh           # Batch 1
bash scripts/ci/validate_compatibility_and_modes.sh    # Batch 2
bash scripts/ci/validate_preflight_and_discovery.sh    # Batch 3
bash scripts/ci/validate_collector_core_topology.sh    # Batch 4
bash scripts/ci/validate_logs_pipeline.sh              # Batch 5
bash scripts/ci/validate_metrics_traces_pipeline.sh    # Batch 6
bash scripts/ci/validate_onboarding_subscription.sh    # Batch 7
bash scripts/ci/validate_security_isolation_resilience.sh # Batch 8
bash scripts/ci/validate_operator_experience_slo.sh    # Batch 9
bash scripts/ci/validate_visualization_admin_access.sh # Batch 9A
bash scripts/ci/validate_vector_foundations.sh         # Batch 10
bash scripts/ci/validate_graph_foundation.sh           # Batch 11
bash scripts/ci/validate_risk_scoring_assisted_rca.sh  # Batch 12
bash scripts/ci/validate_core_adapter_integrations.sh  # Batch 13
```

Each batch also has a smoke wrapper: `scripts/ci/validate_batch<N>_smoke.sh`.

The following scripts validate AI/MCP and adapter layers and are run by CI
outside the numbered batch structure:

```bash
# AI layer contracts
bash scripts/ci/validate_ai_boundary_contracts.sh
bash scripts/ci/validate_ai_governance_contracts.sh
bash scripts/ci/validate_ai_state_contracts.sh
bash scripts/ci/validate_mcp_contracts.sh

# AI/MCP scaffolding
bash scripts/ci/validate_ai_runtime_base_scaffolding.sh
bash scripts/ci/validate_mcp_read_path_scaffolding.sh
bash scripts/ci/validate_multi_agent_scaffolding.sh
bash scripts/ci/validate_khook_trigger_scaffolding.sh
bash scripts/ci/validate_action_gate_scaffolding.sh
bash scripts/ci/validate_kagent_khook_release.sh

# Adapter sub-validators (also called by validate_core_adapter_integrations.sh)
bash scripts/ci/validate_identity_backend_adapters.sh
bash scripts/ci/validate_secrets_backend_adapters.sh
bash scripts/ci/validate_storage_backend_adapters.sh
bash scripts/ci/validate_network_ingress_adapters.sh
bash scripts/ci/validate_cicd_adapter_templates.sh
bash scripts/ci/validate_provider_event_source_adapters.sh
```

### Helm

```bash
helm template platform-core gitops/charts/platform-core
```

## Architecture

### Contract System

`contracts/` is the source of truth for each batch's correctness.
Every major capability has a JSON schema and sample artifacts:

- `contracts/install/` - install contract schema and samples
- `contracts/compatibility/` - environment compatibility, profile catalogs,
  and grading
- `contracts/discovery/` - preflight checks and capability probes
- `contracts/collector/` - OpenTelemetry collector topology
- `contracts/logs/`, `contracts/metrics/`, `contracts/traces/`,
  `contracts/metrics_traces/`, `contracts/telemetry/` - pipeline contracts
- `contracts/onboarding/`, `contracts/security/`, `contracts/slo_ops/` -
  operational contracts
- `contracts/visualization/`, `contracts/vector/`, `contracts/graph/` -
  higher-order tiers
- `contracts/risk_rca/` - risk scoring and RCA contracts
- `contracts/adapters/` - adapter integration contracts
- `contracts/ai/` - AI agent boundary, protocol, state, and casefile contracts
- `contracts/policy/` - OPA policy, approval flow, audit, and tool risk
  classification
- `contracts/mcp/` - MCP catalog, tool response schema, and gateway contracts

### Adapters Framework

`adapters/` provides profile-scoped, additive, reversible extensions:

- `adapters/identity/` - identity provider integration
- `adapters/network/` - network ingress configuration
- `adapters/providers/` - cloud vendor / event source extensions
  (see `adapters/providers/README.md`)
- `adapters/secrets/` - secrets management
- `adapters/storage/` - backend-specific storage
  (see `adapters/storage/README.md`)
- `adapters/cicd/` - CI/CD pipeline adapter templates

### GitOps Delivery

`gitops/` contains everything needed for Helm + ArgoCD + Terraform delivery:

- `gitops/charts/platform-core/` - main Helm chart
- `gitops/apps/` - ArgoCD Application definitions
- `gitops/overlays/` - environment overlays
- `gitops/dashboards/` - Grafana provisioning
- `gitops/alerts/` - alert rules

### Validation Scripts Pattern

All CI scripts in `scripts/ci/` follow this structure:

- Inline Python (heredoc `<<'PY'`) for schema/JSON validation
- Exit 0 on pass, non-zero on failure
- No external test framework (pytest etc.) - all validation is bespoke

### CI Pipeline

`.github/workflows/ci.yaml` runs all batch validations plus AI/MCP and
adapter contract checks on PRs and pushes to main. Includes Gitleaks secret
scanning. Note: `validate_all_batches_with_report.sh` covers only the 14
numbered smoke wrappers (1–9A, 10–13); run the AI/MCP scripts separately if
needed.

## Key Planning Documents

For context on goals and technical decisions:

- `docs/auxiliary/planning/PRD.md`
- `docs/auxiliary/planning/TECHNICAL.md`
- `docs/auxiliary/planning/TASKS.md`
- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM.plan.md`

Operator guides per batch live in `docs/runbooks/`.
