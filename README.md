# Observability Kit

A portable, plug-and-play observability intelligence platform for existing
AWS EKS clusters.

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
or GitHub Actions with consistent outcomes, while enforcing these constraints:

- OpenTelemetry is the sole collector for logs, metrics, and traces
- Amazon OpenSearch is the single telemetry and vector store
- Amazon OpenSearch Ingestion (OSI) is the managed ingest path
- Neo4j is a derived graph tier, not a raw telemetry store
- Delivery is Terraform plus Helm plus ArgoCD Applications

The platform also provides a phased path from core observability to
AI-assisted incident analysis, with deterministic graph and risk capabilities
before optional LLM-assisted RCA.

## Primary Planning Documents

- `docs/auxiliary/planning/OBSERVABILITY_PLATFORM.plan.md`
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

## Project-Local Snyk Path

Use this project-local wrapper to keep Snyk scans scoped to this repository:

`bash scripts/ci/snyk_code_scan_project.sh`

Optional subpath (must stay inside this repo):

`bash scripts/ci/snyk_code_scan_project.sh scripts/ci`
