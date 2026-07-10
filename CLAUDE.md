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
  Kubernetes-resident OpenSearch deployment - provider-managed or self-managed)
- Managed ingest is OpenTelemetry-native; on AWS the default ingest path is
  Amazon OpenSearch Ingestion (OSI) but the architecture does not require it
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform + Helm + ArgoCD Applications
- No provider-specific service is mandatory in the core architecture;
  provider integrations live under `adapters/providers/`
- Cloud-agnostic by design - see `OBSERVABILITY_PLATFORM_V2.plan.md`
  (the v1 plan in `OBSERVABILITY_PLATFORM.plan.md` is AWS-specific and
  retained for historical reference only)

Primary languages: Bash, Python, Terraform, Helm/YAML.

## Common Commands

### Running a Build Batch

`/run-batch <ID>` (defined in `.claude/commands/run-batch.md`) executes one
`TASKS.md` batch end to end: worktree, wave-based multi-agent task
execution, validation gates with self-correction, squash-merge into local
`main`, and decision capture into `docs/DECISIONS.md`. Wave plans and
orchestration rules live in
`docs/auxiliary/task_execution/MULTI_AGENT_BATCH_EXECUTION.md`.

### Setup

```bash
bash scripts/ci/setup_python_env.sh
# creates .venv (VENV_DIR overridable) from requirements-ci.txt.
# requirements-ci.txt is intentionally tiny: yamllint + pymarkdownlnt only.
```

Only ~20 of the `validate_*.sh` scripts need the venv - those whose Python
heredoc does `import yaml` or shells out to `yamllint`/`pymarkdownlnt`. They
`source scripts/ci/setup_python_env.sh` themselves (it is the one shared
helper; there is no `lib/` or `common.sh`). Pure-stdlib JSON validators do
not source it. `scripts/ci/teardown_python_env.sh` removes the venv.

Untracked `setup_python_env.sh.sandbox_bak.*` files are disposable leftovers
from interrupted `sandbox_validate.sh` runs (see below), not real variants.

### Offline / firewalled validation

`scripts/dev/sandbox_validate.sh` wraps any `scripts/ci/validate_*.sh` so it
runs in a sandbox with no PyPI access and no `helm`/`kubectl`:

```bash
bash scripts/dev/sandbox_validate.sh scripts/ci/validate_all_batches_with_report.sh
```

It temporarily stubs `setup_python_env.sh` to a no-op, installs throwaway
`helm`/`kubectl` shims on `PATH` (forcing validators into their offline
structural-fallback path), runs the target, then restores everything on exit.
Use it only when firewalled; real CI has working pip and Helm.

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
# Covers every batch registered in its BATCH_IDS array (currently
# 1-9A, 10-27; new batches register themselves when implemented).
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
bash scripts/ci/validate_tenancy_contracts.sh          # Batch 15
bash scripts/ci/validate_management_plane_contracts.sh # Batch 16
bash scripts/ci/validate_discovery_executor.sh         # Batch 17
bash scripts/ci/validate_guided_installer.sh           # Batch 18
bash scripts/ci/validate_config_renderer.sh            # Batch 19
bash scripts/ci/validate_tenant_control_plane.sh      # Batch 20
bash scripts/ci/validate_portal_contracts.sh          # Batch 21
bash scripts/ci/validate_commercial_contracts.sh      # Batch 22
bash scripts/ci/validate_live_evidence.sh             # Batch 23
bash scripts/ci/validate_ai_activation.sh             # Batch 24
bash scripts/ci/validate_release_engineering.sh       # Batch 25
bash scripts/ci/validate_product_docs.sh              # Batch 26
bash scripts/ci/validate_demo_playground.sh           # Batch 27
```

Batch 17 delivers the `obskit` executor runtime under `tools/obskit/`
(stdlib-only core, optional `[k8s]` extra for live mode, own
`pyproject.toml` - never added to `requirements-ci.txt`). Its offline
tests live in `tests/executor/`; the live kind probe is
`scripts/validate/discovery_executor_kind_integration.sh` (never
CI-gated).

Batch 18 adds the guided installer on top of it: the `obskit install`
subcommand (`tools/obskit/obskit/install/`) executes the seven-step
flow fixed by `contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml`
(ADR-0002), emits GitOps-only rendered output, and is tested offline
in `tests/installer/`.

Batch 19 adds the configuration rendering runtime: the `obskit
render`, `obskit drift`, and `obskit rollback` subcommands
(`tools/obskit/obskit/configrender/`, ADR-0003) execute the Batch 16
propagation contract - unified document (JSON) to native configs at
each binding's `render_target`, deterministic and idempotent, with
the drift diff surface and rollback re-render on top. The strategy
catalog lives in
`contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`; the
rollback drill is `scripts/ops/run_config_rollback_drill.sh`
(dry-run default); offline tests live in `tests/configrender/`.

Batch 20 adds the tenant control plane service under
`services/tenancy/` (package `tenantctl`, ADR-0004): a typed,
stdlib-core service (FastAPI is an optional `[api]` extra; own
`pyproject.toml`, never added to `requirements-ci.txt`) that executes
the Batch 15 tenant lifecycle contract as GitOps renders through the
Batch 19 renderer. The API surface is fixed by
`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`; isolation
provisioning renders follow
`contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`; destructive
transitions honor `contracts/policy/APPROVAL_FLOW_V1.yaml` timeout
and escalation rules. Offline tests and seeded denial fixtures live
in `tests/controlplane/`.

Batch 21 adds the unified management portal under `services/portal/`
(package `portalsvc`, ADR-0005): a typed, stdlib-core service
(FastAPI is an optional `[api]` extra; own `pyproject.toml`, never
added to `requirements-ci.txt`) with a server-rendered no-JS HTML
frontend. It aggregates the UI catalog of
`contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`, executes
unified config edits GitOps-only through the Batch 19 renderer,
delegates tenant management to the Batch 20 control plane API
(binding the authenticated principal to `caller_scope`), and serves a
TR-12 health summary. Its scope is fixed by
`contracts/management/PORTAL_CONTRACT_V1.yaml`; SSO follows the admin
access plane profile (which gains an optional `endpoints.portal`
key). Offline tests live in `tests/portal/`.

Batch 22 adds the commercial layer (ADR-0006): usage metering derived
from telemetry already in OpenSearch (no new collection path) via the
`commercialsvc` collector job under `services/commercial/` (typed,
stdlib-only, own `pyproject.toml`, never added to
`requirements-ci.txt`), writing per-tenant usage records to
control-plane `control-tenancy-usage-v1-*` indices per the TR-16
plane separation. Contracts live in `contracts/commercial/` (metering
contract, usage record schema, plan catalog bound bijectively to the
tenant `tier` enum with quota bounds, vendor-neutral invoice export
contract and schema); the billing adapter boundary is
`adapters/billing/` (house pattern, Stripe reference stub,
`file-export` fallback; fork wrap method rejected). Offline tests
live in `tests/commercial/`; the runbook is
`docs/runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md`.

Batch 23 adds live-cluster validation and evidence (ADR-0007): the
disposable kind harness (`scripts/dev/live_cluster_harness.sh`,
contract `contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`,
two stack profiles: `evidence-disposable` kind cluster per run,
`dev-persistent` OrbStack built-in - never an evidence source),
isolated kubeconfig with foreign-context refusal, the full guided
install executed live (`kind` is now a `conditional` compatibility
matrix distribution, condition `disposable_evidence_harness_only`),
live drills, GUI smoke, and the SDN-B15 denial scenarios captured as
committed evidence under `artifacts/evidence/batch23/`.
`validate_live_evidence.sh` checks the evidence structurally without a
cluster; `.github/workflows/e2e-nightly.yaml` ships disabled by
default and never PR-gates. The runbook is
`docs/runbooks/LIVE_VALIDATION_RUNBOOK.md`.

Batch 24 activates the AI/MCP runtime live (ADR-0008, ADR-0009): the
product-owned `obskit-ai-runtime` image (package `airuntime` under
`services/ai/`, stdlib core, `[postgres]` extra for the
KAGENT_PERSISTENCE store, own `pyproject.toml` - never added to
`requirements-ci.txt`; four entrypoints kagent/khook/gateway/
mcpserver) deploys from `gitops/platform/ai/` via the harness checks
`ai-deploy`, `ai-rehearsal`, `ai-signoff` with the MCP catalog and
governance contracts enforced unmodified. The LLM provider is
pluggable behind `adapters/providers/model/`
(`contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml`; Anthropic
reference adapter, `local-stub` on the harness; keys via the secrets
backend only, never in Git). Live evidence (deployment, rehearsal
with human-surrogate approval honoring APPROVAL_FLOW_V1 timeout and
escalation rules, executed go/no-go signoff with all thresholds
measured) is committed under `artifacts/evidence/batch24/`;
`validate_ai_activation.sh` checks it structurally without a cluster
and cross-checks the runtime's embedded contract constants against
the governing YAML contracts. Offline tests live in
`tests/ai_activation/`.

Batch 25 turns the repository into a releasable product (ADR-0010,
renumbered from the 0009 the backlog budgeted - Batch 24 consumed
two ADRs): `contracts/release/` fixes release engineering (semver,
Keep a Changelog `CHANGELOG.md`, tag-driven publication via
`.github/workflows/release.yaml` - tags and `workflow_dispatch`
only, never PR-gating - packaged chart plus OCI publication with a
neutral `REGISTRY_HOST`, cosign-keyless signing posture, syft SBOM
and trivy CRITICAL scan gates), OSS license compliance (inventory
bijective with the wrapped-system registry and
`THIRD_PARTY_NOTICES.md`), and the production reference architecture
(HA topology, sizing tiers bound to the tenancy tier enum, storage
and ingress via the Batch 2 compatibility profiles, backup and DR
posture, `prod` overlay mapping). The three open wrapped-system pins
(`opensearch` 2.19.1, `opensearch-dashboards` 2.19.1, `argocd`
v3.1.0) are resolved to the harness-proven versions, so
`fail_if_production_pin_missing` now passes for production profiles.
`contracts/slo_ops/PLATFORM_PRODUCT_SLO_V1.yaml` declares the
platform's own product SLOs (declared-for-ga; the isolation SLO has
a zero violation budget). The chart is 0.3.0 and pod templates carry
`app.kubernetes.io/version`, so version bumps are observable rolling
updates. Live evidence under `artifacts/evidence/batch25/` comes
from the harness checks `release-pins` and `upgrade-drill` (compose
on a completed `install`; the harness publishes committed state
only, so commit before capturing). `validate_release_engineering.sh`
checks everything structurally without a cluster, including two
seeded rejections (unpinned production profile, missing license
inventory entry) with fixtures in `tests/release/`. The operator
flow is `docs/runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md`.

Batch 26 closes the SaaS productization arc
(`docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md`) with the
customer-facing product documentation set and the GA readiness
review. The `docs/product/` tree (indexed by `docs/product/INDEX.md`
with a five-audience map) carries nine guides plus
`docs/product/GA_READINESS_REVIEW.md`, a signed checklist walking
the plan's definition of done with an evidence link per item.
`docs/product/API_REFERENCE.md` is generated from
`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` by
`scripts/dev/generate_api_reference.py` (deterministic; `--check`
fails on hand edits - regenerate, never edit). The docs-coverage
matrix `contracts/docs/DOCS_COVERAGE_MATRIX_V1.yaml` maps every
Batch 17-25 capability to a product doc section;
`validate_product_docs.sh` (PR-gated in CI, unlike the
evidence-backed Batch 23-25 validators) enforces the tree, the
matrix, cross-tree links, API reference freshness, and the GA review
structure. The operator flow is
`docs/runbooks/PRODUCT_DOCUMENTATION_RUNBOOK.md`.

Batch 27 delivers the demo playground (ADR-0011, plan
`docs/auxiliary/planning/DEMO_PLAYGROUND_PLAN.md`): an optional,
additive, removable package under `demo/` - four house-built sample
services plus a scenario-driven load generator in one stdlib-only
image (`ghcr.io/obskit/demo:0.1.0`, five entrypoints, hand-rolled
OTLP/HTTP JSON emitter targeting `otel-gateway:4318`; the gateway
Service gained the additive `otlp-http` port), deployed tenant-scoped
(tenant `demo`, namespace `tenant-demo`) through the Batch 7
one-block onboarding contract via `demo/deploy.sh` /
`demo/teardown.sh` (both refuse `ENVIRONMENT=production`; core
charts, contracts, and bootstrap untouched). Traffic scenarios
(steady-baseline, burst, error-injection, latency-injection) are
declarative under `demo/gitops/base/scenarios/` against
`contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json` with seeded-invalid
samples; demo dashboards ship as `DEMO_*.ndjson` under the platform
provisioning path; the AI prompt pack
(`demo/prompts/AI_PROMPT_PACK.md`) binds read-path MCP catalog tools
with a single approval-gated write prompt. Offline tests live in
`tests/demo/`; the operator walkthrough is
`docs/product/PLAYGROUND_GUIDE.md` and the drill runbook is
`docs/runbooks/DEMO_PLAYGROUND_RUNBOOK.md`.

Each batch also has a smoke wrapper: `scripts/ci/validate_batch<N>_smoke.sh`.

### Batch 14 - AI/MCP layer

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

Naming is a hard convention (see `contracts/CONTRACTS_NAMING_CONVENTION.md`):
files directly under `contracts/*/` use loud `UPPERCASE_SNAKE_CASE` with an
explicit version suffix (`*_SCHEMA_V<N>.json`, `*_V<N>.yaml`,
`*_VALIDATION.json`), while `contracts/install/profiles/` uses lowercase
dotted `<title>.schema.json` to match JSON-Schema `$id` tooling. When both
forms are needed for one schema (only in `contracts/install/`), the canonical
file is `UPPERCASE` and a thin `<title>.schema.json` alias `$ref`s it. Never
rename an existing schema - validators, CI, and runbooks reference paths by
name, so renames are breaking.

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

- `agents/` - agent catalog, role definitions, prompt fragments, and policy
  bindings consumed by the multi-agent scaffolding validator
- `pipelines/` - risk scoring and vector retrieval pipeline definitions
- `services/mcp/` - MCP service contracts (`SERVICE_CONTRACT_V1.yaml`) and
  per-service action journals
- `triggers/` - KHook trigger scaffolding, dedupe/burst control, and
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

### Tests

`tests/` holds plain `python3` scripts with `test_*` functions and bare
`assert` statements - pytest-style names but **not run under pytest**. There
is no test runner. Each test is invoked directly by the `scripts/ci/`
validator that owns it (e.g. `validate_preflight_and_discovery.sh` runs
`python3 tests/discovery/test_preflight_checks.py`; adapter validators run
`python3 tests/integration/adapters/...`). The `.json` files under `tests/`
are fixtures those tests load. To run a test, run its validator - not the
file alone.

Because several adapter validators (`validate_*_backend_adapters.sh`,
`validate_network_ingress_adapters.sh`, `validate_provider_event_source_adapters.sh`)
are not gated in CI, the tests they own only execute when you run them
locally or via the Batch 13 parent / the all-batches report.

### Script directories

There are four `scripts/` subdirectories, each with a distinct scope:

- `scripts/ci/` - repository-only validators; PRs gate on these. See
  `scripts/ci/README.md` for the "add a validator" workflow.
- `scripts/validate/` - live-runtime probes needing a cluster or GUI
  (`admin_gui_smoke.sh`, `post_install_readiness.sh`); never run in CI
  because the runner has no deployed instance.
- `scripts/ops/` - operational drills (`run_uninstall_validation.sh`,
  `run_rollback_drill.sh`, `run_restore_drill.sh`), mode-parameterized
  (`dry-run` default). The restore drill hard-refuses when
  `ENVIRONMENT=production`.
- `scripts/dev/` - developer tooling; currently just `sandbox_validate.sh`.

### Validation Scripts Pattern

All CI scripts in `scripts/ci/` follow this structure:

- Inline Python (heredoc `<<'PY'`) for schema/JSON validation
- Exit 0 on pass, non-zero on failure
- No external test framework (pytest etc.) - all validation is bespoke
- The only shared dependency is `setup_python_env.sh`, `source`d by the
  ~20 scripts whose heredoc needs PyYAML or the linters

### CI Pipeline

`.github/workflows/ci.yaml` has two jobs: `lint-and-validate` and
`secret-scan` (Gitleaks via Docker), on PRs and pushes to `main`. CI invokes
the underlying validator scripts **directly, not the batch smoke wrappers**.
`lint-and-validate` runs, in addition to the per-batch validators (1-13) and
the individual AI/MCP scripts: `check_script_permissions.sh`,
`validate_markdown.sh`, `validate_yaml.sh`, `validate_stub_renders.sh`,
`validate_seeded_rejection_checks.sh`, inline `helm lint` + `helm template`,
`validate_gitops_structure.sh`, `check_no_hardcoded_env_values.sh`, and
`validate_runbook_links.sh`.

Not everything is CI-gated. `validate_gitops_neutrality.sh`, the adapter
sub-validators (`validate_*_backend_adapters.sh` etc.), and
`validate_cicd_adapter_templates.sh` run only manually or via their Batch 13
parent / the all-batches report - so a green PR does not by itself prove the
adapter and neutrality contracts pass. Run them (or the all-batches report)
before trusting adapter/neutrality changes.

`scripts/ci/validate_all_batches_with_report.sh` runs every batch smoke
wrapper (currently 1-9, 9A, and 10-27) and writes a
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
