# Observability Kit

A portable, plug-and-play observability intelligence platform for any
conformant Kubernetes cluster — cloud or on-prem. Cloud-agnostic by design;
provider-specific integrations are handled by adapters under `adapters/`.

## Primary Implementation Languages

Primary build and coding languages in this repository are:

- Python
- Bash
- Terraform
- Helm

Supporting formats and languages are used when needed (for example JSON, YAML,
and Markdown).

## Ultimate Goal

Deliver one repeatable platform that can be installed from a personal machine
or any CI runner with consistent outcomes, while enforcing these constraints:

- OpenTelemetry is the sole collector for logs, metrics, and traces
- OpenSearch is the single telemetry and vector store
- Managed ingest is OpenTelemetry-native (e.g., OpenSearch Ingestion where the
  cluster supports it; otherwise the OpenTelemetry collector writes directly)
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform plus Helm plus ArgoCD Applications
- No provider-specific service is mandatory in the core architecture

The platform also provides a phased path from core observability to
AI-assisted incident analysis, with deterministic graph and risk capabilities
before optional LLM-assisted RCA.

## Primary Planning Documents

- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md` (authoritative,
  cloud-agnostic plan)
- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM.plan.md` (deprecated v1,
  AWS-specific; retained for historical reference only)
- `docs/auxiliary/planning/PRD.md`
- `docs/auxiliary/planning/TECHNICAL.md`
- `docs/auxiliary/planning/TASKS.md`

## Batch 1 Delivery Foundation

Batch 1 establishes delivery controls and baseline artifacts mapped to
`TR-10` and `TR-14`.

- Install contract schema:
  `contracts/install/INSTALL_CONTRACT_SCHEMA.json`
- Install contract samples:
  `contracts/install/samples/`
- Batch 1 smoke wrapper:
  `scripts/ci/validate_batch1_smoke.sh`
- GitOps baseline:
  `gitops/README.md`
- Default Argo CD application:
  `gitops/apps/platform-core-application.yaml`
- CI workflow:
  `.github/workflows/ci.yaml`

## Batch 2 Compatibility And Modes

Batch 2 defines environment compatibility, profile catalogs, grading behavior,
mode selection logic, and remediation mappings for `TR-04`, `TR-05`, and
`TR-14`.

- Compatibility and profile artifacts:
  `contracts/compatibility/`
- Batch 2 validation script:
  `scripts/ci/validate_compatibility_and_modes.sh`
- Batch 2 smoke wrapper:
  `scripts/ci/validate_batch2_smoke.sh`
- Operator guide:
  `docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md`

## Batch 3 Preflight And Discovery Engine

Batch 3 adds guided preflight checks, discovery probe outputs, generated
capability and compatibility artifacts, and a readiness scaffold contract for
`TR-04`, `TR-05`, and `TR-10`.

- Preflight and discovery artifacts:
  `contracts/discovery/`
- Batch 3 validation script:
  `scripts/ci/validate_preflight_and_discovery.sh`
- Batch 3 smoke wrapper:
  `scripts/ci/validate_batch3_smoke.sh`
- Operator guide:
  `docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md`

## Batch 4 Collector Core Topology

Batch 4 adds baseline OpenTelemetry collector topology artifacts and validation
for agent and gateway health, required processors, OTLP export checks across
attach and standalone modes, and failure simulation evidence for bounded-loss
behavior.

- Collector topology artifacts:
  `contracts/collector/`
- Batch 4 validation script:
  `scripts/ci/validate_collector_core_topology.sh`
- Operator guide:
  `docs/runbooks/COLLECTOR_CORE_TOPOLOGY_OPERATOR_GUIDE.md`

## Batch 5 Logs Pipeline

Batch 5 adds governed log ingestion validation for CRI and JSON parsing,
multiline grouping, sensitive field redaction, `logs-*` template enforcement,
and trace correlation behavior.

- Logs pipeline artifacts:
  `contracts/logs/`
- Batch 5 validation script:
  `scripts/ci/validate_logs_pipeline.sh`
- Batch 5 smoke wrapper:
  `scripts/ci/validate_batch5_smoke.sh`
- Operator guide:
  `docs/runbooks/LOGS_PIPELINE_OPERATOR_GUIDE.md`

## Batch 6 Metrics And Traces Pipelines

Batch 6 adds metrics and trace contract validation for infrastructure and
application metrics ingestion, scrape onboarding, OTLP ingest behavior,
cardinality guardrails, sampling policy controls, and cross-signal pivots.

- Metrics and traces artifacts:
  `contracts/metrics_traces/`
- Batch 6 validation script:
  `scripts/ci/validate_metrics_traces_pipeline.sh`
- Operator guide:
  `docs/runbooks/METRICS_TRACES_PIPELINE_OPERATOR_GUIDE.md`

## Batch 7 Onboarding And Subscription Model

Batch 7 adds low-touch workload onboarding and subscription controls with
validation coverage for one-block onboarding flow, mode behavior, required
metadata policy checks, CI schema checks, and lead-time measurement.

- Onboarding artifacts:
  `contracts/onboarding/`
- Batch 7 validation script:
  `scripts/ci/validate_onboarding_subscription.sh`
- Batch 7 smoke wrapper:
  `scripts/ci/validate_batch7_smoke.sh`
- Operator guide:
  `docs/runbooks/ONBOARDING_SUBSCRIPTION_OPERATOR_GUIDE.md`

## Batch 8 Security Isolation And Resilience

Batch 8 adds security and resilience validation for team and environment
isolation, encryption controls, audit logging, backup and restore drills,
rollback drills, and hardening checklist completion.

- Security and resilience artifacts:
  `contracts/security/`
- Batch 8 validation script:
  `scripts/ci/validate_security_isolation_resilience.sh`
- Batch 8 smoke wrapper:
  `scripts/ci/validate_batch8_smoke.sh`
- Operator guide:
  `docs/runbooks/SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md`

## Batch 9 Operator Experience And SLO Operations

Batch 9 adds operator experience and SLO operations validation for dashboard
taxonomy, platform health alerts, SLI and SLO query stability, burn-rate and
symptom alerts, incident drill evidence capture, and alert-noise reduction
tracking.

- SLO operations artifacts:
  `contracts/slo_ops/`
- Batch 9 validation script:
  `scripts/ci/validate_operator_experience_slo.sh`
- Batch 9 smoke wrapper:
  `scripts/ci/validate_batch9_smoke.sh`
- Operator guide:
  `docs/runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md`

## Batch 9A Visualization And Admin Access Plane

Batch 9A adds multi-tool visualization ownership and admin GUI access-plane
validation for signal-to-UI mapping, mandatory Grafana core posture, UI
provisioning paths, admin access profile contracts, and admin GUI TLS plus
login smoke behavior.

- Visualization artifacts:
  `contracts/visualization/`
- Admin access profile schema:
  `install/profiles/admin-access/PROFILE.schema.json`
- Batch 9A validation script:
  `scripts/ci/validate_visualization_admin_access.sh`
- Batch 9A smoke wrapper:
  `scripts/ci/validate_batch9a_smoke.sh`
- Operator guide:
  `docs/runbooks/VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md`

## Batch 10 Vector Foundations

Batch 10 adds governed semantic retrieval validation for curated operational
evidence ownership, extraction snapshots, `vectors-*` writes, retrieval quality
baselines, governance controls, and vector operations playbook rehearsal.

- Vector foundation artifacts:
  `contracts/vector/`
- Batch 10 validation script:
  `scripts/ci/validate_vector_foundations.sh`
- Batch 10 smoke wrapper:
  `scripts/ci/validate_batch10_smoke.sh`
- Operator guide:
  `docs/runbooks/VECTOR_FOUNDATIONS_OPERATOR_GUIDE.md`

## Batch 11 Graph Foundation

Batch 11 adds optional derived graph intelligence validation for module
enable or disable behavior, graph schema versioning, idempotent sync jobs,
graph freshness alerts, dependency and blast-radius queries, and graph
operations runbook dry-run evidence.

- Graph foundation artifacts:
  `contracts/graph/`
- Batch 11 validation script:
  `scripts/ci/validate_graph_foundation.sh`
- Batch 11 smoke wrapper:
  `scripts/ci/validate_batch11_smoke.sh`
- Operator guide:
  `docs/runbooks/GRAPH_FOUNDATION_OPERATOR_GUIDE.md`

## Batch 12 Risk Scoring And Assisted RCA Readiness

Batch 12 adds deterministic risk scoring and assisted RCA readiness validation
for reproducible feature definitions, scored service outputs, backtesting
evidence, hybrid evidence bundle traceability, human approval gates, and pilot
go or hold decision records.

- Risk scoring and RCA readiness artifacts:
  `contracts/risk_rca/`
- Batch 12 validation script:
  `scripts/ci/validate_risk_scoring_assisted_rca.sh`
- Batch 12 smoke wrapper:
  `scripts/ci/validate_batch12_smoke.sh`
- Operator guide:
  `docs/runbooks/RISK_SCORING_ASSISTED_RCA_READINESS_GUIDE.md`

## Batch 13 Core Adapter Integrations

Batch 13 adds the adapter framework: profile-scoped, additive, reversible
extensions for provider event sources, identity, secrets, storage, network
ingress, and CI/CD. Core contracts remain unchanged whether adapters are
enabled or disabled.

- Adapter contracts:
  `contracts/adapters/`
- Adapter implementations:
  `adapters/identity/`, `adapters/secrets/`, `adapters/storage/`,
  `adapters/network/`, `adapters/providers/`, `adapters/cicd/`
- Batch 13 validation script:
  `scripts/ci/validate_core_adapter_integrations.sh`
- Per-adapter sub-validators:
  `scripts/ci/validate_identity_backend_adapters.sh`,
  `scripts/ci/validate_secrets_backend_adapters.sh`,
  `scripts/ci/validate_storage_backend_adapters.sh`,
  `scripts/ci/validate_network_ingress_adapters.sh`,
  `scripts/ci/validate_cicd_adapter_templates.sh`,
  `scripts/ci/validate_provider_event_source_adapters.sh`
- Batch 13 smoke wrapper:
  `scripts/ci/validate_batch13_smoke.sh`
- Operator guide:
  `docs/runbooks/CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md`
- Adapter enablement guide:
  `docs/adapters/ADAPTER_ENABLEMENT_GUIDE.md`

## Batch 14 AI/MCP Runtime Validation And Productization

Batch 14 covers the AI/MCP layer that builds on the core platform: agent
boundary contracts, governance and approval flow, casefile state, MCP catalog
and tool response contracts, KAgent/KHook/KMcp scaffolding, and action-gate
release readiness.

- AI contracts:
  `contracts/ai/`
- Policy contracts:
  `contracts/policy/`
- MCP contracts:
  `contracts/mcp/`
- Batch 14 smoke wrapper (aggregates all 10 AI/MCP validators):
  `scripts/ci/validate_batch14_smoke.sh`
- Per-area validators:
  `scripts/ci/validate_ai_boundary_contracts.sh`,
  `scripts/ci/validate_ai_governance_contracts.sh`,
  `scripts/ci/validate_ai_state_contracts.sh`,
  `scripts/ci/validate_mcp_contracts.sh`,
  `scripts/ci/validate_ai_runtime_base_scaffolding.sh`,
  `scripts/ci/validate_mcp_read_path_scaffolding.sh`,
  `scripts/ci/validate_multi_agent_scaffolding.sh`,
  `scripts/ci/validate_khook_trigger_scaffolding.sh`,
  `scripts/ci/validate_action_gate_scaffolding.sh`,
  `scripts/ci/validate_kagent_khook_release.sh`
- Operator runbooks:
  `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md`,
  `docs/runbooks/KHOOK_TROUBLESHOOTING_RUNBOOK.md`,
  `docs/runbooks/MCP_GATEWAY_OPERATIONS_RUNBOOK.md`,
  `docs/runbooks/CASEFILE_REVIEW_RUNBOOK.md`

## Unified Validation Reporting

Run all implemented batch smoke tests and generate developer and QA friendly
reports:

`bash scripts/ci/validate_all_batches_with_report.sh`

Report outputs:

- `docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.md`
- `docs/reports/validation/BATCH_VALIDATION_REPORT_LATEST.json`

## Baseline Runbooks

- `docs/runbooks/INSTALL_RUNBOOK.md`
- `docs/runbooks/VALIDATION_RUNBOOK.md`
- `docs/runbooks/ROLLBACK_RUNBOOK.md`
- `docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md`
- `docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md`
- `docs/runbooks/COLLECTOR_CORE_TOPOLOGY_OPERATOR_GUIDE.md`
- `docs/runbooks/LOGS_PIPELINE_OPERATOR_GUIDE.md`
- `docs/runbooks/METRICS_TRACES_PIPELINE_OPERATOR_GUIDE.md`
- `docs/runbooks/ONBOARDING_SUBSCRIPTION_OPERATOR_GUIDE.md`
- `docs/runbooks/SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md`
- `docs/runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md`
- `docs/runbooks/VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md`
- `docs/runbooks/VECTOR_FOUNDATIONS_OPERATOR_GUIDE.md`
- `docs/runbooks/GRAPH_FOUNDATION_OPERATOR_GUIDE.md`
- `docs/runbooks/RISK_SCORING_ASSISTED_RCA_READINESS_GUIDE.md`
- `docs/runbooks/CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md`
- `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md`
- `docs/runbooks/KHOOK_TROUBLESHOOTING_RUNBOOK.md`
- `docs/runbooks/MCP_GATEWAY_OPERATIONS_RUNBOOK.md`
- `docs/runbooks/CASEFILE_REVIEW_RUNBOOK.md`

## Project-Local Snyk Path

Use this project-local wrapper to keep Snyk scans scoped to this repository:

`bash scripts/ci/snyk_code_scan_project.sh`

Optional subpath (must stay inside this repo):

`bash scripts/ci/snyk_code_scan_project.sh scripts/ci`
