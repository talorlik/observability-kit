# CLAUDE.md

This file provides guidance to Claude Code (`claude.ai/code`) when working
with code in this repository.

## Project Overview

Observability Kit is a portable, plug-and-play observability intelligence
platform for any conformant Kubernetes cluster (cloud or on-prem). It
delivers a phased path from core observability to AI-assisted incident
analysis, structured as sequential "Batches" (currently 14, with the
AI/MCP layer formalized as Batch 14).

Hard constraints:

- OpenTelemetry is the sole collector for logs, metrics, and traces
- OpenSearch is the single telemetry and vector store (any conformant,
  Kubernetes-resident OpenSearch deployment — provider-managed or self-managed)
- Managed ingest is OpenTelemetry-native; on AWS the default ingest path is
  Amazon OpenSearch Ingestion (OSI) but the architecture does not require it
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform + Helm + ArgoCD Applications
- No provider-specific service is mandatory in the core architecture;
  provider integrations live under `adapters/providers/`
- Cloud-agnostic by design — see `OBSERVABILITY_PLATFORM_V2.plan.md`
  (the v1 plan in `OBSERVABILITY_PLATFORM.plan.md` is AWS-specific and
  retained for historical reference only)

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
# Covers Batches 1-14 (1-9A then 10-14).
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
bash scripts/ci/validate_batch14_smoke.sh              # Batch 14 (AI/MCP)
```

Each batch also has a smoke wrapper: `scripts/ci/validate_batch<N>_smoke.sh`.

### Batch 14 — AI/MCP layer

Batch 14 is the AI/MCP runtime tier. Its smoke wrapper aggregates the AI
agent boundary, governance, state, MCP catalog, and scaffolding/release
validators:

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
```

### Adapter sub-validators

These run for Batch 13. They are also invoked from the Batch 13 parent
script `validate_core_adapter_integrations.sh`, so adapter contract drift
is caught both individually and via the batch entry point.

```bash
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
helm template platform-core gitops/charts/platform-core \
  -f gitops/overlays/dev/platform-core-values.yaml      # dev overlay
helm template platform-core gitops/charts/platform-core \
  -f gitops/overlays/prod/platform-core-values.yaml     # prod overlay
```

## Architecture

### Contract System

`contracts/` is the source of truth for each batch's correctness.
Every major capability has a JSON schema and sample artifacts:

- `contracts/install/` - install contract schema and samples
- `contracts/compatibility/` - environment compatibility, profile catalogs,
  and grading
- `contracts/discovery/` - preflight checks, capability probes, and explicit
  schemas for both probes and preflight reports
- `contracts/collector/` - OpenTelemetry collector topology
- `contracts/logs/`, `contracts/metrics/`, `contracts/traces/`,
  `contracts/metrics_traces/`, `contracts/telemetry/` - pipeline contracts
- `contracts/onboarding/`, `contracts/security/`, `contracts/slo_ops/` -
  operational contracts
- `contracts/visualization/`, `contracts/vector/`, `contracts/graph/` -
  higher-order tiers
- `contracts/risk_rca/` - risk scoring and RCA contracts
- `contracts/adapters/` - adapter integration contracts
- `contracts/ai/` - AI agent boundary, protocol, state, casefile, and
  KAgent persistence contracts
- `contracts/policy/` - OPA policy, approval flow (with timeout and
  escalation rules), audit, action preconditions, identity-access matrix,
  and tool risk classification
- `contracts/mcp/` - MCP catalog, tool response schema, and gateway
  discovery contract (with heartbeat, timeout, and failover policy)

### Adapters Framework

`adapters/` provides profile-scoped, additive, reversible extensions:

- `adapters/identity/` - identity provider integration
- `adapters/network/` - network ingress configuration
- `adapters/providers/` - vendor / event source extensions
  (see `adapters/providers/README.md`)
- `adapters/secrets/` - secrets management
- `adapters/storage/` - backend-specific storage
  (see `adapters/storage/README.md`)
- `adapters/cicd/` - CI/CD pipeline adapter templates

Each adapter directory contains a `*_COMPATIBILITY_V1.yaml`, a
`STUB_METADATA.json`, a `ROLLBACK_UNINSTALL_NOTES.md`, and a `README.md`.

### AI/MCP Runtime Components

The AI/MCP layer (Batch 14) is implemented across these top-level
directories, all cloud-agnostic and Kubernetes-resident:

- `agents/` — agent catalog, role definitions, prompt fragments, and policy
  bindings consumed by the multi-agent scaffolding validator
- `pipelines/` — risk scoring and vector retrieval pipeline definitions
- `services/mcp/` — MCP service contracts (`SERVICE_CONTRACT_V1.yaml`) and
  per-service action journals
- `triggers/` — KHook trigger scaffolding, dedupe/burst control, and
  read-only dispatch policies

These are validated by the AI/MCP scripts above and exercised by tests under
`tests/safety/`, `tests/staging/`, and `tests/integration/`.

### GitOps Delivery

`gitops/` contains everything needed for Helm + ArgoCD + Terraform delivery:

- `gitops/charts/platform-core/` - main Helm chart with `values.schema.json`
- `gitops/apps/` - ArgoCD Application definitions, one per major component
  (platform-core, observability-pipelines, search-stack, graph-stack,
  ai-runtime, access-layer, security-policies, storage-backups)
- `gitops/bootstrap/argocd/` - ArgoCD self-bootstrap kustomization
- `gitops/overlays/` - per-environment overlays (`base`, `dev`, `staging`,
  `prod`, `quickstart`) for the platform-core chart
- `gitops/platform/ai/` - AI/MCP runtime kustomizations (deployments,
  network policies, namespaces, per-environment overlays)
- `gitops/platform/observability/` - OpenTelemetry collector pipeline values
- `gitops/platform/search/` - OpenSearch index templates, ILM policies,
  saved-object dashboards, and alert rules
- `gitops/platform/graph/` - Neo4j module
- `gitops/dashboards/`, `gitops/alerts/` - top-level READMEs that point at
  the actual saved-object dashboards and alert rules under
  `gitops/platform/search/dashboards/`

### Validation Scripts Pattern

All CI scripts in `scripts/ci/` follow this structure:

- Inline Python (heredoc `<<'PY'`) for schema/JSON validation
- Exit 0 on pass, non-zero on failure
- No external test framework (pytest etc.) - all validation is bespoke

### CI Pipeline

`.github/workflows/ci.yaml` runs the per-batch validators (1-13) and the
individual AI/MCP scripts on PRs and pushes to main, plus Gitleaks secret
scanning. The Batch 14 smoke wrapper aggregates the same AI/MCP scripts for
local development and the unified report.

`scripts/ci/validate_all_batches_with_report.sh` runs every batch smoke
wrapper (1, 2, 3, 4, 5, 6, 7, 8, 9, 9A, 10, 11, 12, 13, 14) and writes a
markdown + JSON report under `docs/reports/validation/`. It is intended for
developer / QA use and is not part of the CI workflow itself.

## Key Planning Documents

For context on goals and technical decisions:

- `docs/auxiliary/planning/PRD.md`
- `docs/auxiliary/planning/TECHNICAL.md`
- `docs/auxiliary/planning/TASKS.md`
- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md` (authoritative)
- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM.plan.md` (deprecated v1)
- `docs/auxiliary/planning/AI_MCP_MARKER_COVERAGE.md` (KK-C marker
  cross-reference for the AI/MCP layer)
- `docs/auxiliary/planning/kagent_khook/` (AI/MCP layer sub-plan and tasks)

Operator guides per batch live in `docs/runbooks/`.
