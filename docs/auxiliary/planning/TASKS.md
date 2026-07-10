# Observability Platform Incremental Tasks

This backlog is aligned with `PRD.md` and `TECHNICAL.md`.
It is cloud agnostic, Kubernetes-native, and open-source-first.
All tasks are incremental and sized small to medium.

## How To Use This Backlog

- Execute batches in order.
- Run one batch at a time (`do batch 1`, `do batch 2`, and so on).
- Start a task only after its dependencies are complete.
- Close a task only when its completion check passes.

## Technical Marker Mapping

Use these markers to trace each batch to `TECHNICAL.md`.

| Batch | Primary Marker Coverage |
| ---- | ---- |
| Batch 1 | `TR-10`, `TR-14` |
| Batch 2 | `TR-04`, `TR-05`, `TR-14` |
| Batch 3 | `TR-04`, `TR-05`, `TR-10` |
| Batch 4 | `TR-06`, `TR-11` |
| Batch 5 | `TR-06`, `TR-07` |
| Batch 6 | `TR-06`, `TR-07` |
| Batch 7 | `TR-06`, `TR-09`, `TR-12` |
| Batch 8 | `TR-07`, `TR-09`, `TR-12` |
| Batch 9 | `TR-06`, `TR-10`, `TR-12` |
| Batch 9A | `TR-03`, `TR-09`, `TR-12` |
| Batch 10 | `TR-08`, `TR-09` |
| Batch 11 | `TR-08`, `TR-11` |
| Batch 12 | `TR-08`, `TR-09`, `TR-13` |
| Batch 13 | `TR-03`, `TR-09`, `TR-10` |
| Batch 14 | `TR-03`, `TR-08`, `TR-09`, `TR-13`, `TR-15` |
| Batch 15 | `TR-03`, `TR-07`, `TR-09`, `TR-16` |
| Batch 16 | `TR-03`, `TR-09`, `TR-10`, `TR-17` |
| Batch 17 | `TR-04`, `TR-05`, `TR-18` |
| Batch 18 | `TR-05`, `TR-14`, `TR-19` |
| Batch 19 | `TR-10`, `TR-17`, `TR-20` |
| Batch 20 | `TR-09`, `TR-16`, `TR-21` |
| Batch 21 | `TR-03`, `TR-17`, `TR-22` |
| Batch 22 | `TR-16`, `TR-23` |
| Batch 23 | `TR-12`, `TR-24` |
| Batch 24 | `TR-13`, `TR-15`, `TR-24` |
| Batch 25 | `TR-11`, `TR-12`, `TR-25` |
| Batch 26 | `TR-14`, `TR-26` |
| Batch 27 | `TR-06`, `TR-15`, `TR-27` |

## Agent Cross-Reference Index

Use this index first when actioning tasks so the correct section in
`TECHNICAL.md` is always consulted before implementation.

| Task Batch Marker | Batch | Read These Technical Markers First |
| ---- | ---- | ---- |
| `TB-01` | Batch 1 - Delivery Foundation | `TR-10`, `TR-14` |
| `TB-02` | Batch 2 - Compatibility and Modes | `TR-04`, `TR-05`, `TR-14` |
| `TB-03` | Batch 3 - Preflight and Discovery Engine | `TR-04`, `TR-05`, `TR-10` |
| `TB-04` | Batch 4 - Collector Core Topology | `TR-06`, `TR-11` |
| `TB-05` | Batch 5 - Logs Pipeline | `TR-06`, `TR-07` |
| `TB-06` | Batch 6 - Metrics and Traces Pipelines | `TR-06`, `TR-07` |
| `TB-07` | Batch 7 - Onboarding and Subscription Model | `TR-06`, `TR-09`, `TR-12` |
| `TB-08` | Batch 8 - Security, Isolation, and Resilience | `TR-07`, `TR-09`, `TR-12` |
| `TB-09` | Batch 9 - Operator Experience and SLO Operations | `TR-06`, `TR-10`, `TR-12` |
| `TB-09A` | Batch 9A - Visualization and Admin Access Plane | `TR-03`, `TR-09`, `TR-12` |
| `TB-10` | Batch 10 - Vector Foundations | `TR-08`, `TR-09` |
| `TB-11` | Batch 11 - Graph Foundation | `TR-08`, `TR-11` |
| `TB-12` | Batch 12 - Risk Scoring and Assisted RCA Readiness | `TR-08`, `TR-09`, `TR-13` |
| `TB-13` | Batch 13 - Core Adapter Integrations | `TR-03`, `TR-09`, `TR-10` |
| `TB-14` | Batch 14 - AI/MCP Runtime Validation and Productization | `TR-03`, `TR-08`, `TR-09`, `TR-13`, `TR-15` |
| `TB-15` | Batch 15 - SaaS Multi-Tenancy and Customer Isolation | `TR-03`, `TR-07`, `TR-09`, `TR-16` |
| `TB-16` | Batch 16 - Unified Configuration and Management Plane | `TR-03`, `TR-09`, `TR-10`, `TR-17` |
| `TB-17` | Batch 17 - Discovery and Preflight Execution Engine | `TR-04`, `TR-05`, `TR-18` |
| `TB-18` | Batch 18 - Guided Installation Experience | `TR-05`, `TR-14`, `TR-19` |
| `TB-19` | Batch 19 - Configuration Rendering Runtime | `TR-10`, `TR-17`, `TR-20` |
| `TB-20` | Batch 20 - Tenant Control Plane Service | `TR-09`, `TR-16`, `TR-21` |
| `TB-21` | Batch 21 - Unified Management Portal | `TR-03`, `TR-17`, `TR-22` |
| `TB-22` | Batch 22 - Metering, Billing, and Commercial Operations | `TR-16`, `TR-23` |
| `TB-23` | Batch 23 - Live-Cluster Validation and Evidence | `TR-12`, `TR-24` |
| `TB-24` | Batch 24 - AI/MCP Runtime Activation | `TR-13`, `TR-15`, `TR-24` |
| `TB-25` | Batch 25 - Production Operations and Release Engineering | `TR-11`, `TR-12`, `TR-25` |
| `TB-26` | Batch 26 - Product Documentation and GA Readiness | `TR-14`, `TR-26` |
| `TB-27` | Batch 27 - Demo Workloads and Observability Playground | `TR-06`, `TR-15`, `TR-27` |

## Batch 1 - Delivery Foundation [TB-01 | TR-10, TR-14]

Goal: establish repeatable delivery controls and artifact structure.

1. Define install contract schema file with required inputs from `TR-05`.
   - Dependencies: none.
   - Completion check: schema validates sample install contract documents.
2. Create GitOps directory baseline for charts, overlays, dashboards, and alerts.
   - Dependencies: none.
   - Completion check: structure exists and is documented in repository docs.
3. Add default GitOps application manifest for platform core components.
   - Dependencies: Task 2.
   - Completion check: manifest renders and references correct repository paths.
4. Add CI checks for linting, template validation, and policy checks.
   - Dependencies: Tasks 1-2.
   - Completion check: CI pipeline passes on valid change and fails on bad input.
5. Add secret scanning and "no hard-coded environment values" checks in CI.
   - Dependencies: Task 4.
   - Completion check: seeded policy violation is blocked in pull request flow.
6. Create baseline runbook set for install, validation, and rollback entrypoints.
   - Dependencies: Tasks 1-3.
   - Completion check: runbooks are linked from main project documentation.

## Batch 2 - Compatibility and Modes [TB-02 | TR-04, TR-05, TR-14]

Goal: define supported environments and mode selection logic.

1. Build compatibility matrix template for Kubernetes versions and distributions.
   - Dependencies: Batch 1.
   - Completion check: matrix includes supported and conditional support states.
2. Define profile catalogs for storage, object storage, identity, secrets, ingress.
   - Dependencies: Batch 1 Task 1.
   - Completion check: profiles are documented with prerequisites and defaults.
3. Implement compatibility grading rules (`supported`, `conditional`, `blocked`).
   - Dependencies: Tasks 1-2.
   - Completion check: sample clusters produce expected grading outcomes.
4. Define deployment mode decision table (`quickstart`, `attach`, `standalone`,
   `hybrid`).
   - Dependencies: Task 3.
   - Completion check: mode recommendations are deterministic for test inputs.
5. Create remediation catalog for unsupported prerequisites and profile gaps.
   - Dependencies: Tasks 2-3.
   - Completion check: each blocked condition maps to an actionable remediation.
6. Publish compatibility and mode-selection operator guide.
   - Dependencies: Tasks 1-5.
   - Completion check: guide is complete and cross-linked from backlog docs.

## Batch 3 - Preflight and Discovery Engine [TB-03 | TR-04, TR-05, TR-10]

Goal: implement guided preflight checks and discovery reports.

1. Implement preflight checks for cluster access, API readiness, and CRDs.
   - Dependencies: Batch 2.
   - Completion check: preflight report includes pass/fail results per check.
2. Implement discovery probes for storage classes and ingress or gateway support.
   - Dependencies: Task 1.
   - Completion check: probe output lists available capabilities and defaults.
3. Implement discovery probes for GitOps controllers and secret integrations.
   - Dependencies: Task 1.
   - Completion check: report captures detected controllers and integration types.
4. Implement workload discovery for namespaces, controllers, services, and ports.
   - Dependencies: Task 1.
   - Completion check: report includes onboardable workload candidate inventory.
5. Generate discovery outputs: capability matrix, compatibility result, mode
   recommendation, remediation list.
   - Dependencies: Tasks 2-4.
   - Completion check: all four output artifacts are generated for a test cluster.
6. Add post-install readiness check scaffold tied to discovery output contracts.
   - Dependencies: Task 5.
   - Completion check: readiness report template is emitted after dry-run install.

## Batch 4 - Collector Core Topology [TB-04 | TR-06, TR-11]

Goal: deploy stable OpenTelemetry agent and gateway baseline.

1. Create agent DaemonSet collector profile for passive logs and node metrics.
   - Dependencies: Batch 3.
   - Completion check: agent is scheduled on all eligible nodes.
2. Create gateway Deployment profile with retry, batch, and memory controls.
   - Dependencies: Task 1.
   - Completion check: gateway health checks are green under normal load.
3. Add mandatory processors (`k8sattributes`, `resource`, `memory_limiter`,
   `batch`).
   - Dependencies: Task 2.
   - Completion check: collector configuration validation succeeds.
4. Configure OTLP export path with profile-driven backend endpoint settings.
   - Dependencies: Task 2.
   - Completion check: telemetry export succeeds in attach and standalone tests.
5. Add collector self-observability metrics and baseline health dashboard.
   - Dependencies: Tasks 1-4.
   - Completion check: queue depth, retries, and drop metrics are queryable.
6. Run failure simulation (gateway restart and temporary backend outage).
   - Dependencies: Tasks 1-5.
   - Completion check: bounded-loss behavior is observed and documented.

## Batch 5 - Logs Pipeline [TB-05 | TR-06, TR-07]

Goal: establish reliable, governed log ingestion.

1. Configure CRI log parsing and JSON field extraction defaults.
   - Dependencies: Batch 4.
   - Completion check: parsed logs include required base fields.
2. Add multiline parsing rules for common stack trace formats.
   - Dependencies: Task 1.
   - Completion check: multiline events are grouped correctly in test data.
3. Add sensitive field redaction and never-index processors.
   - Dependencies: Task 1.
   - Completion check: test events show redaction for prohibited field patterns.
4. Define log mapping templates and rollover naming strategy for `logs-*`.
   - Dependencies: Task 1.
   - Completion check: new indices follow naming and mapping policy.
5. Add log correlation requirements for `trace_id` and `span_id` when present.
   - Dependencies: Tasks 1-3.
   - Completion check: trace-linked log queries work in pilot services.
6. Create logs operations dashboard and ingestion quality checks.
   - Dependencies: Tasks 1-5.
   - Completion check: parsing, redaction, and lag indicators are visible.

## Batch 6 - Metrics and Traces Pipelines [TB-06 | TR-06, TR-07]

Goal: complete metric and trace contracts with correlation controls.

1. Enable cluster and workload metrics collection baseline.
   - Dependencies: Batch 4.
   - Completion check: infrastructure metrics are visible for all test namespaces.
2. Add annotation and label based scrape onboarding path.
   - Dependencies: Task 1.
   - Completion check: opted-in service metrics appear in target indices.
3. Add OTLP metrics and trace ingest paths for instrumented services.
   - Dependencies: Task 1.
   - Completion check: OTLP metrics and traces are accepted end-to-end.
4. Implement label cardinality budgets and prohibited label policy.
   - Dependencies: Tasks 1-3.
   - Completion check: high-cardinality violations are blocked or dropped.
5. Add trace sampling policy defaults and environment overrides.
   - Dependencies: Task 3.
   - Completion check: sampling behavior matches configured policies.
6. Create metrics and trace dashboards with trace-log pivot validation.
   - Dependencies: Tasks 1-5.
   - Completion check: operators can pivot across metrics, traces, and logs.

## Batch 7 - Onboarding and Subscription Model [TB-07 | TR-06, TR-09, TR-12]

Goal: make workload onboarding low-touch and policy controlled.

1. Build `observability-lib` Helm library for one-block onboarding.
   - Dependencies: Batch 1 Task 2.
   - Completion check: pilot service onboards through single values block.
2. Add onboarding toggles for passive, low-touch, and instrumentation modes.
   - Dependencies: Task 1.
   - Completion check: each mode produces expected telemetry behavior.
3. Add required metadata policy checks (`service.name`, environment, ownership).
   - Dependencies: Tasks 1-2.
   - Completion check: non-compliant onboarding fails with clear error output.
4. Add onboarding schema validation in CI and pre-merge checks.
   - Dependencies: Batch 1 Task 4, Task 3.
   - Completion check: invalid onboarding config fails in pull request checks.
5. Publish service onboarding playbook and troubleshooting guide.
   - Dependencies: Tasks 1-4.
   - Completion check: one new team self-onboards without platform code changes.
6. Measure onboarding lead time and remove top two friction points.
   - Dependencies: Task 5.
   - Completion check: measured onboarding cycle time improves in next iteration.

## Batch 8 - Security, Isolation, and Resilience [TB-08 | TR-07, TR-09, TR-12]

Goal: harden runtime, enforce isolation, and prove recovery.

1. Implement environment and team isolation for indices, roles, and dashboard
   spaces.
   - Dependencies: Batches 5-7.
   - Completion check: cross-team access attempts fail by policy.
2. Validate encryption in transit and at rest for telemetry and backup paths.
   - Dependencies: Batch 4.
   - Completion check: encryption controls are verifiable in runtime settings.
3. Add audit logging for access, config changes, and onboarding actions.
   - Dependencies: Tasks 1-2.
   - Completion check: audit records are queryable and retained as configured.
4. Configure backup, snapshot, and restore workflows with evidence capture.
   - Dependencies: Task 2.
   - Completion check: restore drill succeeds in non-production environment.
5. Execute rollback drills for GitOps revision and exporter routing changes.
   - Dependencies: Batch 4.
   - Completion check: rollback procedures are tested and timed.
6. Publish production hardening checklist and residual risk notes.
   - Dependencies: Tasks 1-5.
   - Completion check: checklist is complete and used in release gate reviews.

## Batch 9 - Operator Experience and SLO Operations [TB-09 | TR-06, TR-10, TR-12]

Goal: make telemetry actionable and reduce incident response effort.

1. Create dashboard taxonomy for platform, service, and governance views.
   - Dependencies: Batches 5-8.
   - Completion check: naming and folder structure are consistent.
2. Add platform health alerts for collector drops, ingest lag, and backend health.
   - Dependencies: Batch 4 Task 5.
   - Completion check: alert test events route to expected channels.
3. Define baseline SLIs and SLO targets for pilot services.
   - Dependencies: Batches 5-6.
   - Completion check: SLI queries are stable and repeatable.
4. Add burn-rate and symptom alerts with runbook links.
   - Dependencies: Task 3.
   - Completion check: simulated events trigger expected alert behavior.
5. Run tabletop incident drill using dashboards, alerts, and runbooks.
   - Dependencies: Tasks 1-4.
   - Completion check: drill output captures response timeline and follow-ups.
6. Tune alert noise and false-positive rate based on pilot feedback.
   - Dependencies: Task 5.
   - Completion check: alert noise trend improves over two review cycles.

## Batch 9A - Visualization and Admin Access Plane [TB-09A | TR-03, TR-09, TR-12]

Goal: make visualization explicitly multi-tool and deliver secure external admin
GUI access.

1. Define and publish signal-to-UI ownership model for logs, metrics, traces,
   graph workflows, and executive views.
   - Dependencies: Batch 9.
   - Completion check: ownership matrix is published and cross-linked in runbooks.
2. Make Grafana a mandatory core component in baseline deployment profiles.
   - Dependencies: Task 1.
   - Completion check: baseline profile installs Grafana with no optional flag.
3. Define OpenSearch Dashboards and Grafana provisioning paths as code.
   - Dependencies: Tasks 1-2.
   - Completion check: saved objects and dashboards render from versioned assets.
4. Define Neo4j Browser exposure and auth requirements for graph-enabled mode.
   - Dependencies: Batch 11 Task 1 may remain pending for rollout, but
     requirements and placeholders are created in this batch.
   - Completion check: graph-enabled profile has clear UI endpoint and RBAC plan.
5. Implement admin access plane profile contract (ingress/gateway, TLS, authn,
   role mapping, break-glass path).
   - Dependencies: Batch 3, Batch 8.
   - Completion check: profile schema and operator guidance are published.
6. Add admin GUI smoke tests for endpoint reachability and login flow checks.
   - Dependencies: Tasks 2-5.
   - Completion check: readiness suite reports pass or fail by enabled UI.

## Batch 10 - Vector Foundations [TB-10 | TR-08, TR-09]

Goal: add governed semantic retrieval on curated operational evidence.

1. Define curated artifact set for embedding (incidents, summaries, runbooks).
   - Dependencies: Batch 9.
   - Completion check: artifact list has owners and refresh rules.
2. Build extraction pipeline from telemetry stores to curated artifact dataset.
   - Dependencies: Task 1.
   - Completion check: extraction run outputs versioned artifact snapshots.
3. Add embedding generation and `vectors-*` index write pipeline.
   - Dependencies: Task 2.
   - Completion check: vector index is populated and queryable.
4. Implement semantic retrieval endpoint with relevance scoring output.
   - Dependencies: Task 3.
   - Completion check: retrieval quality baseline is documented.
5. Add governance controls for PII filtering and retrieval audit events.
   - Dependencies: Tasks 1-4.
   - Completion check: governance checks pass in CI and runtime validation.
6. Publish vector operations playbook (quality checks, reindex, rollback).
   - Dependencies: Tasks 3-5.
   - Completion check: playbook is validated in one controlled rehearsal.

## Batch 11 - Graph Foundation [TB-11 | TR-08, TR-11]

Goal: build optional derived graph intelligence tier.

1. Define graph module deployment profile and connectivity contract.
   - Dependencies: Batch 10.
   - Completion check: module can be enabled or disabled without core disruption.
2. Define versioned graph schema for services, dependencies, ownership, incidents.
   - Dependencies: Task 1.
   - Completion check: schema definition is reviewed and approved.
3. Build idempotent sync jobs from telemetry artifacts to graph store.
   - Dependencies: Task 2.
   - Completion check: repeated runs converge to consistent graph state.
4. Add graph freshness and sync quality metrics with alert thresholds.
   - Dependencies: Task 3.
   - Completion check: stale graph conditions trigger expected alerts.
5. Implement dependency and blast-radius query set for operators.
   - Dependencies: Tasks 2-4.
   - Completion check: replayed incidents return expected dependency paths.
6. Publish graph operations runbook (rebuild, repair, fallback).
   - Dependencies: Tasks 3-5.
   - Completion check: runbook is validated through one dry-run scenario.

## Batch 12 - Risk Scoring and Assisted RCA Readiness [TB-12 | TR-08, TR-09, TR-13]

Goal: deliver deterministic risk scoring before controlled RCA assistance.

1. Define deterministic risk features from graph and telemetry evidence.
   - Dependencies: Batch 11.
   - Completion check: feature definitions are versioned and reproducible.
2. Implement risk scoring job and risk dashboard views.
   - Dependencies: Task 1.
   - Completion check: risk scores are generated and queryable by service.
3. Backtest scoring against historical incidents and tune thresholds.
   - Dependencies: Task 2.
   - Completion check: backtest report includes precision and recall trends.
4. Build hybrid retrieval orchestrator combining vector and graph evidence.
   - Dependencies: Batches 10-11.
   - Completion check: output bundles include traceable evidence links.
5. Add human approval and audit workflow for assisted RCA suggestions.
   - Dependencies: Task 4.
   - Completion check: no recommendation can execute without explicit approval.
6. Run controlled pilot and decide go or hold for full assisted RCA release.
   - Dependencies: Tasks 1-5.
   - Completion check: pilot decision record is signed off by stakeholders.

## Batch 13 - Core Adapter Integrations [TB-13 | TR-03, TR-09, TR-10]

Goal: finalize adapter extension points while preserving core contract stability.

1. Define adapter contract for provider, backend, identity, secrets, and network
   classes.
   - Dependencies: Batch 2 Task 2, Batch 3 Task 5.
   - Completion check: adapter schema validates supported and invalid examples.
2. Implement adapter registration and profile activation model.
   - Dependencies: Task 1.
   - Completion check: profile-driven activation enables adapters without changing
     core contracts.
3. Add adapter stubs for identity, secrets, and network integrations.
   - Dependencies: Task 2.
   - Completion check: stubs expose required metadata, prerequisites, and fallback
     behavior.
4. Add CI contract checks for adapter definitions and activation safety.
   - Dependencies: Tasks 1-3.
   - Completion check: CI blocks invalid adapter definitions and unsafe mutations.
5. Add CI/CD neutrality checks to keep Argo CD as reference while remaining
   tool-neutral.
   - Dependencies: Task 4.
   - Completion check: core manifests remain vendor-neutral with and without
     adapters enabled.
6. Publish adapter enablement, validation, disablement, and rollback guide.
   - Dependencies: Tasks 1-5.
   - Completion check: operator guide is complete and linked from platform docs.

## Batch 14 - AI/MCP Runtime Validation and Productization [TB-14 | TR-03, TR-08, TR-09, TR-13, TR-15]

Goal: formalize the AI/MCP runtime layer that builds on the core platform.
Batch 14 covers agent boundary contracts, governance and approval flow,
casefile state, MCP catalog and tool response contracts, KAgent / KHook /
KMcp scaffolding, and action-gate release readiness. This batch is
cloud-agnostic: it depends only on Kubernetes-resident components.

The AI/MCP sub-plan and detailed tasks live in
`docs/auxiliary/planning/kagent_khook/`.

1. Establish AI agent boundary, governance, and shared-state contracts.
   - Dependencies: Batch 8 Task 4, Batch 9 Task 1.
   - Completion check: `validate_ai_boundary_contracts.sh`,
     `validate_ai_governance_contracts.sh`, and `validate_ai_state_contracts.sh`
     pass.
2. Establish MCP catalog, tool response, and gateway-discovery contracts.
   - Dependencies: Task 1.
   - Completion check: `validate_mcp_contracts.sh` passes; gateway discovery
     contract enforces heartbeat, timeout, and failover policy.
3. Land AI runtime base scaffolding (KAgent, persistence backing store).
   - Dependencies: Task 1, Batch 13 Task 6.
   - Completion check: `validate_ai_runtime_base_scaffolding.sh` passes;
     `KAGENT_PERSISTENCE_CONTRACT_V1.yaml` defines schema namespaces,
     retention, backups, and restore-drill cadence.
4. Land MCP read-path and multi-agent scaffolding.
   - Dependencies: Tasks 2-3.
   - Completion check: `validate_mcp_read_path_scaffolding.sh` and
     `validate_multi_agent_scaffolding.sh` pass; agent catalog and tool
     bindings cover triage director, investigation manager, and action
     governor roles.
5. Land KHook trigger scaffolding with dedupe and burst control.
   - Dependencies: Task 4.
   - Completion check: `validate_khook_trigger_scaffolding.sh` passes;
     read-only dispatch policy enforced.
6. Land action-gate scaffolding with approval flow timeouts and escalation.
   - Dependencies: Tasks 4-5; Batch 12 Task 5.
   - Completion check: `validate_action_gate_scaffolding.sh` passes;
     `APPROVAL_FLOW_V1.yaml` `timeout_rules` and `escalation_rules`
     reflected in `gitops/platform/search/dashboards/alerts/approval_flow_rules.ndjson`.
7. Add AI/MCP smoke wrapper and unified-report wiring.
   - Dependencies: Tasks 1-6.
   - Completion check: `scripts/ci/validate_batch14_smoke.sh` exists and is
     executable; Batch 14 entry present in
     `validate_all_batches_with_report.sh` (BATCH_IDS, BATCH_NAMES,
     VALIDATION_CRITERIA, SCRIPT_PATHS).
8. Add AI/MCP GitOps artifacts.
   - Dependencies: Tasks 1-6.
   - Completion check: `gitops/apps/ai-runtime-application.yaml`,
     `gitops/platform/ai/base/namespaces/namespaces.yaml`,
     `gitops/platform/search/dashboards/saved-objects/AI_RUNTIME_HEALTH.ndjson`
     and `MCP_GATEWAY_HEALTH.ndjson`, and the `approval_flow_rules.ndjson`
     and `mcp_health_rules.ndjson` alert files are present.
9. Land KAgent/KHook release readiness.
   - Dependencies: Tasks 1-8.
   - Completion check: `validate_kagent_khook_release.sh` passes;
     production activation signoff workflow has documented go/no-go
     thresholds.
10. Publish AI/MCP operator runbooks.
    - Dependencies: Tasks 1-9.
    - Completion check: `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md`,
      `KHOOK_TROUBLESHOOTING_RUNBOOK.md`,
      `MCP_GATEWAY_OPERATIONS_RUNBOOK.md`, and `CASEFILE_REVIEW_RUNBOOK.md`
      are linked from `README.md` and `docs/auxiliary/planning/AI_MCP_MARKER_COVERAGE.md`.

## Batch 15 - SaaS Multi-Tenancy and Customer Isolation [TB-15 | TR-03, TR-07, TR-09, TR-16]

Goal: serve multiple customers from one platform with zero cross-tenant
leakage. Customer-level isolation is stricter than the team-level
isolation delivered in Batch 8 and must never weaken it.

1. Define tenant contract schema, isolation classes, and sample
   descriptors.
   - Dependencies: Batch 8 Task 1, Batch 13 Task 2.
   - Completion check: schema validates valid tenant samples and rejects
     seeded invalid samples.
2. Define per-tenant data isolation matrix for indices, roles, dashboard
   spaces, vector indices, and graph databases.
   - Dependencies: Task 1.
   - Completion check: matrix covers logs, metrics, traces, vectors, and
     graph stores with deny-by-default cross-tenant rules.
3. Define tenant lifecycle contract: provision, suspend, offboard, and
   purge with evidence.
   - Dependencies: Task 1.
   - Completion check: lifecycle transitions are idempotent and purge
     defines evidence capture and retention rules.
4. Define per-tenant GitOps overlay generation and control-plane versus
   data-plane separation contract.
   - Dependencies: Task 1.
   - Completion check: overlay generation renders per-tenant values
     without modifying core charts; control-plane data never mixes with
     tenant telemetry.
5. Add tenancy validators, seeded cross-tenant rejection fixtures, smoke
   wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_tenancy_contracts.sh` and
     `validate_batch15_smoke.sh` pass; seeded cross-tenant fixture is
     rejected; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish SaaS tenancy operator runbook.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/SAAS_TENANCY_RUNBOOK.md` covers
     onboarding, isolation verification, and purge drill and is linked
     from `README.md` and the runbook index.

## Batch 16 - Unified Configuration and Management Plane [TB-16 | TR-03, TR-09, TR-10, TR-17]

Goal: wrap every bundled open-source system behind one configuration and
management plane without forking any of them.

1. Define wrapped-system registry contract with upgrade mechanism and
   wrap method per system.
   - Dependencies: Batch 9A Task 3.
   - Completion check: registry lists every bundled system with upstream
     source, version, upgrade mechanism, config surface, and an allowed
     wrap method; `fork` is rejected.
2. Define unified configuration schema with per-system propagation
   bindings.
   - Dependencies: Task 1.
   - Completion check: every unified key maps to at least one binding
     that targets a registered system; unbound keys and unregistered
     targets are rejected.
3. Define propagation and reconciliation contract covering render,
   commit, reconcile, drift detection, and rollback.
   - Dependencies: Task 2.
   - Completion check: propagation is GitOps-only with drift detection
     and a rollback path; direct mutable API writes for persistent
     configuration are forbidden.
4. Define single-pane access contract: UI catalog, SSO role mapping, and
   tenant scoping.
   - Dependencies: Task 1.
   - Completion check: UI catalog covers every wrapped UI with auth
     mapping consistent with the admin access plane contract.
5. Add management-plane validators, seeded rejection fixtures, smoke
   wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_management_plane_contracts.sh` and
     `validate_batch16_smoke.sh` pass; seeded fork-method and
     unbound-key fixtures are rejected; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish unified configuration operator runbook.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/UNIFIED_CONFIGURATION_RUNBOOK.md`
     covers the config change flow, drift response, and per-system
     upstream upgrade procedure and is linked from `README.md` and the
     runbook index.

## Batch 17 - Discovery and Preflight Execution Engine [TB-17 | TR-04, TR-05, TR-18]

Goal: implement the runtime that executes the already-contracted
preflight checks and discovery probes against a live cluster. Batches 2
and 3 defined the contracts and expected outputs; this batch makes them
executable without weakening their read-only guarantees.

1. Publish the executor ADR and executor architecture contract.
   - Dependencies: Batch 2, Batch 3.
   - Completion check:
     `docs/adr/ADR_0001_DISCOVERY_EXECUTOR_ARCHITECTURE.md` records the
     decision: a Python 3.11+ package under `tools/obskit/` with its
     own `pyproject.toml` and pinned requirements (never added to
     `requirements-ci.txt`), type hints mandatory and dataclasses for
     structured data, a CLI entry point plus an optional in-cluster Job
     mode, and a read-only RBAC manifest limited to get, list, and
     watch verbs;
     `contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml`
     captures the same boundaries machine-readably.
2. Implement the preflight execution engine.
   - Dependencies: Task 1.
   - Completion check: `obskit preflight` executes every contracted
     preflight check class and emits a report that validates against
     `contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json`; exit code is 0
     when all blocking checks pass and non-zero otherwise.
3. Implement the discovery probes.
   - Dependencies: Task 1.
   - Completion check: `obskit discover` probes storage and ingress,
     GitOps and secrets integrations, and workload inventory using
     read-only API verbs only, and emits output that validates against
     `contracts/discovery/DISCOVERY_PROBES_SCHEMA.json`.
4. Generate capability, compatibility, mode, and remediation outputs.
   - Dependencies: Tasks 2-3.
   - Completion check: from one preflight-plus-discovery run the
     executor emits a capability matrix, a compatibility result graded
     via `contracts/compatibility/GRADING_RULES.json`, a mode
     recommendation resolved via
     `contracts/compatibility/MODE_DECISION_TABLE.json`, and a
     remediation list drawn from
     `contracts/compatibility/REMEDIATION_CATALOG.json`; identical
     inputs produce byte-identical outputs.
5. Add executor test harness, validators, smoke wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_discovery_executor.sh` runs the
     offline fixture-driven tests and passes;
     `validate_batch17_smoke.sh` passes; a kind-cluster integration
     mode exists and is documented as not CI-gated; batch is registered
     in `validate_all_batches_with_report.sh`.
6. Publish the executor operator runbook.
   - Dependencies: Tasks 1-5.
   - Completion check:
     `docs/runbooks/DISCOVERY_EXECUTOR_OPERATOR_GUIDE.md` covers CLI
     and in-cluster runs, RBAC setup, report interpretation, and
     remediation follow-up and is linked from `README.md` and the
     runbook index.

## Batch 18 - Guided Installation Experience [TB-18 | TR-05, TR-14, TR-19]

Goal: a guided installer that takes an operator from an empty
conformant cluster to a verified installation in one flow, interactive
or fully unattended.

1. Publish the installer ADR and install flow contract.
   - Dependencies: Batch 17.
   - Completion check: `docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md`
     records the decision: the installer lives in `tools/obskit/` as
     typed Python 3.11+ with dataclasses for structured data and never
     modifies wrapped open-source systems;
     `contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml` fixes the step
     order: preflight, grading, mode recommendation, install contract
     capture, render, Argo CD bootstrap, post-install readiness.
2. Implement the interactive CLI wizard.
   - Dependencies: Task 1.
   - Completion check: `obskit install` walks the contracted steps
     interactively; `obskit install --answers <file>` runs the
     identical flow with no prompts; both paths validate the captured
     contract against `contracts/install/INSTALL_CONTRACT_SCHEMA.json`
     and reject invalid answers with a non-zero exit code.
3. Implement the render step.
   - Dependencies: Task 1.
   - Completion check: the render step turns a valid install contract
     into an environment overlay plus Argo CD bootstrap manifests with
     no direct cluster API writes, consistent with
     `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`;
     re-rendering the same contract produces byte-identical manifests.
4. Implement installation finalization and summary.
   - Dependencies: Tasks 2-3.
   - Completion check: the finalization step invokes
     `scripts/validate/post_install_readiness.sh` and emits an install
     summary listing readiness results and next steps; a failed
     readiness check yields a non-zero installer exit code.
5. Add installer validators, seeded rejection fixtures, smoke wrapper,
   and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_guided_installer.sh` and
     `validate_batch18_smoke.sh` pass; seeded invalid-answers fixtures
     are rejected; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish the product-level installation guide.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/GUIDED_INSTALLATION_GUIDE.md`
     covers interactive and non-interactive installs, resume after
     failure, and readiness verification, is linked from `README.md`
     and the runbook index, and states that the full product doc tree
     arrives in Batch 26.

## Batch 19 - Configuration Rendering Runtime [TB-19 | TR-10, TR-17, TR-20]

Goal: implement the deterministic renderer that executes the
propagation and reconciliation contract defined in Batch 16. The
unified configuration document becomes committed native configuration
through Git only, never through live writes.

1. Publish the renderer ADR and renderer architecture contract.
   - Dependencies: Batch 16.
   - Completion check:
     `docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md` records the
     decision: a Python 3.11+ package under `tools/obskit/` with its
     own dependency manifest (never added to `requirements-ci.txt`),
     type hints mandatory and dataclasses for structured data, and
     GitOps-only output per
     `contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml`;
     `contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml`
     captures the same boundaries machine-readably.
2. Implement the unified configuration renderer.
   - Dependencies: Task 1.
   - Completion check: `obskit render` consumes a unified document plus
     bindings validated against
     `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json` and writes
     native configs at each binding's `render_target`; identical inputs
     produce byte-identical outputs; every rendered file carries the
     generated-file header marker and every propagation commit carries
     the required commit trailers from the propagation contract.
3. Add render-idempotency check and drift-detection helper tooling.
   - Dependencies: Task 2.
   - Completion check: the idempotency check re-renders an unchanged
     document and proves a no-diff, no-commit result; the drift helper
     diffs rendered against live state and emits the
     rendered-versus-live diff surface consumed by the `TR-12` drift
     alert path.
4. Add rollback and re-render tooling.
   - Dependencies: Task 2.
   - Completion check: rollback re-renders from a prior unified
     document revision through the same render-and-commit pipeline,
     never a separate apply channel, and follows the mode-parameterized
     conventions of `scripts/ops/run_rollback_drill.sh` with `dry-run`
     as the default mode.
5. Add renderer validators, smoke wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_config_renderer.sh` runs the offline
     fixture-driven tests and passes; `validate_batch19_smoke.sh`
     passes; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Extend the unified configuration runbook to executable steps.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/UNIFIED_CONFIGURATION_RUNBOOK.md`
     turns the contract-described config change flow into executable
     renderer steps covering render, commit, drift response, and
     rollback, and stays linked from `README.md` and the runbook
     index.

## Batch 20 - Tenant Control Plane Service [TB-20 | TR-09, TR-16, TR-21]

Goal: implement the service that executes the tenant lifecycle
contract defined in Batch 15. Every lifecycle transition materializes
as a GitOps render, never a direct cluster write.

1. Publish the control-plane ADR and control-plane API contract.
   - Dependencies: Batch 15, Batch 19.
   - Completion check:
     `docs/adr/ADR_0004_TENANT_CONTROL_PLANE_SERVICE.md` records the
     decision: a FastAPI service in typed Python 3.11+ under
     `services/tenancy/` with its own dependency manifest (never added
     to `requirements-ci.txt`);
     `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` is an OpenAPI
     document covering tenant CRUD and lifecycle transitions with
     exactly the state machine and idempotent-replay semantics of
     `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`.
2. Implement the tenant control plane service.
   - Dependencies: Task 1.
   - Completion check: the service executes provision, suspend, resume,
     offboard, and purge as GitOps renders, generating per-tenant
     overlays per
     `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`
     through the Batch 19 renderer; re-running a completed transition
     is an audited no-op replay; no direct mutable API writes for
     persistent configuration.
3. Implement isolation provisioning renders.
   - Dependencies: Task 2.
   - Completion check: provisioning renders per-tenant OpenSearch
     roles, role mappings, and dashboard spaces, one Neo4j database per
     tenant in graph-enabled mode, and per-tenant vector index
     artifacts exactly as defined in
     `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`.
4. Integrate approval gating and audit.
   - Dependencies: Task 2.
   - Completion check: destructive transitions are blocked without an
     approval record per `contracts/policy/APPROVAL_FLOW_V1.yaml`,
     honoring its timeout and escalation rules; every transition audit
     record carries `tenant_id`.
5. Add control-plane validators, seeded denial fixtures, smoke
   wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_tenant_control_plane.sh` exercises
     seeded denial fixtures against the service logic offline and
     passes; `validate_batch20_smoke.sh` passes; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish the tenant administration runbook.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/TENANT_ADMINISTRATION_RUNBOOK.md`
     covers lifecycle operations, approval handling, and purge evidence
     verification and is linked from `README.md` and the runbook
     index.

## Batch 21 - Unified Management Portal [TB-21 | TR-03, TR-17, TR-22]

Goal: deliver the single-pane portal that fronts every wrapped UI, the
unified configuration flow, and tenant management without forking any
wrapped system.

1. Publish the portal ADR and portal contract.
   - Dependencies: Batch 16, Batch 19, Batch 20.
   - Completion check: `docs/adr/ADR_0005_MANAGEMENT_PORTAL_STACK.md`
     records and justifies the frontend and backend stack choice and
     keeps v1 minimal;
     `contracts/management/PORTAL_CONTRACT_V1.yaml` defines the portal
     views, API surface, and authentication via the admin access
     plane.
2. Implement the portal backend.
   - Dependencies: Task 1.
   - Completion check: the backend under `services/portal/` (typed
     Python 3.11+ with its own dependency manifest, never added to
     `requirements-ci.txt`) aggregates the UI catalog from
     `contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`,
     unified config read and edit through the Batch 19 renderer flow
     (edits become Git commits, never live writes), tenant management
     through the Batch 20 API, and a platform health summary.
3. Implement the portal frontend.
   - Dependencies: Task 2.
   - Completion check: the frontend navigates to every cataloged
     wrapped UI, provides a unified config editor with schema
     validation against
     `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`, and renders
     tenant views backed by the Batch 20 API.
4. Integrate SSO and role mapping.
   - Dependencies: Task 2.
   - Completion check: portal login follows the admin access plane
     profile with role mapping consistent with
     `contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`; tenant
     scoping enforces `TR-16` so a tenant-scoped role never sees
     another tenant's views.
5. Add portal validators, smoke wrapper, admin GUI smoke extension,
   and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_portal_contracts.sh` and
     `validate_batch21_smoke.sh` pass;
     `scripts/validate/admin_gui_smoke.sh` gains a portal endpoint
     check; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish the portal operator and user guide.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/MANAGEMENT_PORTAL_GUIDE.md`
     covers operator setup, SSO configuration, the config editing
     flow, and tenant views and is linked from `README.md` and the
     runbook index.

## Batch 22 - Metering, Billing, and Commercial Operations [TB-22 | TR-16, TR-23]

Goal: meter tenant usage from telemetry already in OpenSearch, bind
tenants to commercial plans, and export billing through a
vendor-neutral adapter boundary.

1. Publish the metering ADR and metering contract.
   - Dependencies: Batch 20.
   - Completion check: `docs/adr/ADR_0006_METERING_ARCHITECTURE.md`
     records the decision;
     `contracts/commercial/METERING_CONTRACT_V1.yaml` defines the
     usage dimensions - ingest GB per day per signal, retention days,
     active tenants, and query volume - sourced from platform
     telemetry already in OpenSearch.
2. Implement the metering collector job.
   - Dependencies: Task 1.
   - Completion check: the collector job (typed Python 3.11+ under
     `services/commercial/` with its own dependency manifest, never
     added to `requirements-ci.txt`) writes usage records to
     control-plane indices named `control-tenancy-*` per the plane
     separation rules of
     `contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`;
     every usage record carries `tenant_id`.
3. Define the plan and tier catalog contract.
   - Dependencies: Task 1.
   - Completion check: `contracts/commercial/PLAN_CATALOG_V1.yaml`
     binds every plan to the `tier` enum of
     `contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json` with quota
     bounds that hook into the Batch 15 tenant quotas; a plan without
     quota bounds is rejected.
4. Add the billing adapter class and reference adapter.
   - Dependencies: Tasks 2-3.
   - Completion check: `adapters/billing/` follows the house adapter
     pattern (`*_COMPATIBILITY_V1.yaml`, `STUB_METADATA.json`,
     `ROLLBACK_UNINSTALL_NOTES.md`, `README.md`) with a Stripe
     reference adapter stub and an invoice-export contract; vendor
     logic stays adapter-scoped and the core stays vendor-neutral.
5. Add commercial validators, seeded rejection fixtures, smoke
   wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_commercial_contracts.sh` and
     `validate_batch22_smoke.sh` pass; seeded rejection fixtures - a
     usage record without `tenant_id`, a plan without quota bounds,
     and a billing adapter with a fork-like core mutation - are
     rejected; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish the commercial operations runbook.
   - Dependencies: Tasks 1-5.
   - Completion check:
     `docs/runbooks/COMMERCIAL_OPERATIONS_RUNBOOK.md` covers pricing
     configuration, the invoicing flow, and quota breach handling and
     is linked from `README.md` and the runbook index.

## Batch 23 - Live-Cluster Validation and Evidence [TB-23 | TR-12, TR-24]

Goal: prove every declared runtime behavior on a real, disposable
cluster and replace declared fixture evidence with captured evidence,
without ever gating pull requests on a live cluster.

1. Publish the harness ADR and disposable-cluster harness contract.
   - Dependencies: Batch 17, Batch 18, Batch 19.
   - Completion check:
     `docs/adr/ADR_0007_DISPOSABLE_CLUSTER_HARNESS.md` records the
     decision: live validation runs only on disposable kind (or k3d)
     clusters created on the local Docker engine - OrbStack on the
     reference development machine - never on shared or long-lived
     clusters, and is never CI-gated on pull requests;
     `contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`
     fixes the kind/k3d profile, node sizing, teardown guarantees,
     and two local stack profiles: `evidence-disposable` (kind
     cluster, created and destroyed per run) and `dev-persistent`
     (the OrbStack built-in Kubernetes cluster with the dev overlay
     and a documented reset procedure, for day-to-day iteration -
     never used for evidence capture); the harness writes and uses
     an ISOLATED kubeconfig and refuses to operate on any context it
     did not create (cloud and shared contexts, e.g. EKS/GKE/AKS
     ARNs, are structurally unreachable);
     `scripts/dev/live_cluster_harness.sh` is the single
     mode-parameterized entry point for create, run, and teardown.
2. Run the full end-to-end install on the harness.
   - Dependencies: Task 1.
   - Completion check: a harness cluster reaches a running platform
     using only the Batch 18 installer (`obskit install`), with no
     hand-assembled steps; the install summary and the
     `scripts/validate/post_install_readiness.sh` readiness report
     are captured under `artifacts/evidence/`.
3. Execute every runtime-only completion check live.
   - Dependencies: Task 2.
   - Completion check: every runtime-only completion check from
     Batches 4-12 executes against the harness - the restore drill
     (`scripts/ops/run_restore_drill.sh`), the rollback drills
     (`scripts/ops/run_rollback_drill.sh`), GUI smoke
     (`scripts/validate/admin_gui_smoke.sh`) including the portal
     endpoint, and the live cross-tenant denial scenarios
     `SDN-B15-001` through `SDN-B15-009` from
     `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml` - and each
     check writes an evidence artifact under `artifacts/evidence/`.
4. Reference captured evidence from the validation contracts.
   - Dependencies: Tasks 2-3.
   - Completion check: every affected `*_VALIDATION.json` contract
     gains an additive `captured_evidence` reference to its
     `artifacts/evidence/` artifact while keeping its declared blocks
     unchanged; no schema file is renamed.
5. Add the live-evidence validator, smoke wrapper, and nightly
   workflow stub.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_live_evidence.sh` and
     `validate_batch23_smoke.sh` pass structurally - evidence files
     exist and match their contracts - without requiring a cluster;
     the live run itself stays a manual or nightly flow:
     `.github/workflows/e2e-nightly.yaml` ships disabled by default,
     is documented as orchestrator-owned, and is never wired into PR
     gating; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Publish the live validation runbook.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/LIVE_VALIDATION_RUNBOOK.md`
     covers harness lifecycle, the evidence capture flow, re-running
     a single check, and teardown verification and is linked from
     `README.md` and the runbook index.

## Batch 24 - AI/MCP Runtime Activation [TB-24 | TR-13, TR-15, TR-24]

Goal: take the validated AI/MCP layer from scaffolding to a live,
rehearsed runtime with an executed go/no-go signoff, keeping every
governance contract enforced.

1. Publish the model-provider ADR and model-provider adapter
   contract.
   - Dependencies: Batch 14, Batch 23.
   - Completion check: `docs/adr/ADR_0008_MODEL_PROVIDER_ADAPTER.md`
     records the decision: the LLM provider is pluggable behind an
     adapter under `adapters/providers/` following the house adapter
     pattern (`*_COMPATIBILITY_V1.yaml`, `STUB_METADATA.json`,
     `ROLLBACK_UNINSTALL_NOTES.md`, `README.md`), with the Anthropic
     API as the reference adapter;
     `contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml` requires
     provider keys to resolve through the secrets backend adapter and
     never appear in configuration or Git.
2. Deploy the AI runtime live on the harness.
   - Dependencies: Task 1.
   - Completion check: KAgent, KHook, and the MCP gateway deploy from
     `gitops/platform/ai/` onto a Batch 23 harness cluster with the
     MCP catalog (`contracts/mcp/`) and the governance contracts
     (`contracts/policy/`) enforced unmodified; deployment evidence
     is captured under `artifacts/evidence/`.
3. Rehearse the live end-to-end investigation flow.
   - Dependencies: Task 2.
   - Completion check: a KHook trigger produces a casefile, a
     read-path investigation, and an action-gate approval flow with a
     human-surrogate approval step, honoring the timeout and
     escalation rules of `contracts/policy/APPROVAL_FLOW_V1.yaml`;
     policy, redaction, and audit stay intact and the rehearsal
     evidence is captured under `artifacts/evidence/`.
4. Execute the production activation go/no-go signoff.
   - Dependencies: Task 3.
   - Completion check: the signoff runs per
     `docs/operations/PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md` with
     every quantitative threshold measured and captured as evidence;
     an unmeasurable threshold is recorded as a failed gate.
5. Add the AI activation validator, smoke wrapper, and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_ai_activation.sh` and
     `validate_batch24_smoke.sh` pass structurally - adapter
     contract, deployment evidence, rehearsal evidence, and signoff
     record exist and match their contracts - without requiring a
     cluster; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Extend the AI runbooks with live activation.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/runbooks/AI_MCP_LAYER_OPERATOR_GUIDE.md`
     and `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md` gain live
     activation, rehearsal, and rollback-to-scaffolding sections; no
     new duplicate runbook is created and the extended runbooks stay
     linked from `README.md` and the runbook index.

## Batch 25 - Production Operations and Release Engineering [TB-25 | TR-11, TR-12, TR-25]

Goal: turn the repository into a releasable product: versioned,
pinned, upgrade-tested, supply-chain hardened, and license-clean for
commercial distribution.

1. Publish the release engineering ADR and release contract.
   - Dependencies: Batch 23.
   - Completion check: `docs/adr/ADR_0010_RELEASE_ENGINEERING.md`
     (renumbered from 0009, which Batch 24 consumed) records the
     decision;
     `contracts/release/RELEASE_ENGINEERING_CONTRACT_V1.yaml` fixes
     semver versioning, the `CHANGELOG.md` convention, tag-driven
     releases, the packaged Helm chart and OCI artifact publication
     path, and the artifact signing posture.
2. Resolve the open wrapped-system version pins.
   - Dependencies: Task 1.
   - Completion check: the three `to-be-pinned` entries in
     `contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml` -
     `opensearch`, `opensearch-dashboards`, and `argocd` - are
     resolved to concrete versions verified against upstream
     releases; the `fail_if_production_pin_missing` rule passes for
     production profiles and the pinned set installs cleanly on the
     Batch 23 harness with evidence captured under
     `artifacts/evidence/`.
3. Prove the N-1 to N upgrade path and productionize platform SLOs.
   - Dependencies: Tasks 1-2.
   - Completion check: on the harness, the previous tagged state
     installs, upgrades to the current state, and data and
     configuration survive, with evidence captured under
     `artifacts/evidence/`; `contracts/slo_ops/` gains a
     `PLATFORM_PRODUCT_SLO_V1.yaml` extension defining the platform's
     own SLOs as a product.
4. Add supply-chain hardening and the license compliance contract.
   - Dependencies: Task 1.
   - Completion check: CI gains image scanning and SBOM generation
     for release artifacts;
     `contracts/release/LICENSE_COMPLIANCE_CONTRACT_V1.yaml` defines
     the OSS license compliance review for commercial distribution of
     all bundled systems - a license inventory, per-license
     obligations, and an attribution file requirement.
5. Add release validators, seeded rejection fixtures, smoke wrapper,
   and CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_release_engineering.sh` and
     `validate_batch25_smoke.sh` pass; seeded rejection fixtures - a
     production profile with an unpinned wrapped system and a bundled
     system missing from the license inventory - are rejected; batch
     is registered in `validate_all_batches_with_report.sh`.
6. Publish the production release-gate runbook.
   - Dependencies: Tasks 1-5.
   - Completion check:
     `docs/runbooks/PRODUCTION_RELEASE_GATE_RUNBOOK.md` covers the
     tag-to-publication flow, pin bumps, upgrade testing, and the
     license and SBOM gates and is linked from `README.md` and the
     runbook index.
7. Publish the production stack reference architecture.
   - Dependencies: Tasks 1-2.
   - Completion check:
     `contracts/release/PRODUCTION_REFERENCE_ARCHITECTURE_V1.yaml`
     defines the production-grade stack for any conformant
     Kubernetes cluster (cloud or on-prem): multi-node HA topology
     with anti-affinity, sizing tiers mapped to tenant scale,
     storage class and ingress requirements expressed through the
     Batch 2 compatibility profiles, backup and DR posture, and the
     mapping to the `prod` overlay under `gitops/overlays/`; a
     compliant cluster grades `supported` in the compatibility
     matrix; `validate_release_engineering.sh` asserts the
     document's required sections; the Batch 26 `OPERATIONS_GUIDE.md`
     consumes it as its production deployment source.

## Batch 26 - Product Documentation and GA Readiness [TB-26 | TR-14, TR-26]

Goal: publish the customer-facing product documentation set and close
the productization arc with a signed, evidence-backed GA readiness
review.

1. Establish the product documentation information architecture.
   - Dependencies: Batches 17-25.
   - Completion check: `docs/product/INDEX.md` establishes the
     `docs/product/` tree and maps every document to its audience -
     evaluator, installer and operator, tenant administrator, end
     user, and commercial administrator; every later task's document
     slots into this index.
2. Write the core product documents.
   - Dependencies: Task 1.
   - Completion check: `docs/product/GETTING_STARTED.md`,
     `docs/product/INSTALLATION_GUIDE.md` (product-level, derived
     from the Batch 18 install flow),
     `docs/product/CONFIGURATION_GUIDE.md` (derived from the Batch 19
     unified configuration flow), and
     `docs/product/OPERATIONS_GUIDE.md` exist and match the delivered
     behavior they document.
3. Write the tenant, end-user, and API documents.
   - Dependencies: Task 1.
   - Completion check: `docs/product/TENANT_ADMIN_GUIDE.md` and
     `docs/product/END_USER_GUIDE.md` exist;
     `docs/product/API_REFERENCE.md` is generated from
     `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` and carries
     a generated-file marker so hand edits are detectable.
4. Write the commercial documents and refresh the landing surface.
   - Dependencies: Task 1.
   - Completion check: `docs/product/PRICING_AND_PACKAGING.md` (bound
     to the Batch 22 plan catalog) and the
     `docs/product/SUPPORT_AND_ONBOARDING.md` playbook exist;
     `README.md` is refreshed to present the product and link the
     `docs/product/` tree.
5. Add product docs validators, coverage matrix, smoke wrapper, and
   CI wiring.
   - Dependencies: Tasks 1-4.
   - Completion check: `validate_product_docs.sh` and
     `validate_batch26_smoke.sh` pass, including a docs-coverage
     matrix check proving every Batch 17-25 capability maps to a
     product doc section, plus link validation across the
     `docs/product/` tree; batch is registered in
     `validate_all_batches_with_report.sh`.
6. Execute the GA readiness review.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/product/GA_READINESS_REVIEW.md` is a
     signed checklist walking every item of the definition of done in
     `docs/auxiliary/planning/SAAS_PRODUCTIZATION_PLAN.md` with an
     evidence link per item; no item is marked complete without a
     link.

## Batch 27 - Demo Workloads and Observability Playground [TB-27 | TR-06, TR-15, TR-27]

Goal: give operators a deployable demo package - realistic sample
services, scenario-driven traffic and fault simulation, demo
dashboards, and an AI prompt pack - plus a step-by-step playground
guide, so every product surface can be exercised on "real" data
without instrumenting a production fleet.

1. Record the demo architecture ADR and establish the package
   skeleton.
   - Dependencies: Batches 7, 9A, 18, 24, 26.
   - Completion check: an ADR under `docs/adr/` records the demo
     workload sourcing and load-generation technology choices
     (wrap-never-fork enforced, development-stack sizing budget
     stated, tenant scoping decided); `demo/README.md` establishes
     the package layout and one-command deploy and teardown entry
     points; the package's onboarding values block validates against
     the Batch 7 onboarding contract.
2. Deliver the sample services.
   - Dependencies: Task 1.
   - Completion check: the package deploys at minimum an HTTP API
     service, an asynchronous worker, a scheduled job, and a
     datastore-backed service, each emitting logs, metrics, and
     traces through OpenTelemetry to the platform collector (no
     direct store writes); all manifests render cleanly offline; a
     signal inventory file enumerates, per service, the emitted
     signal types and key attributes the dashboards and AI prompts
     rely on.
3. Deliver traffic, load, and fault simulation.
   - Dependencies: Task 1.
   - Completion check: declarative scenario definitions exist for
     steady baseline, burst, error-injection, and latency-injection,
     with a schema and a seeded-invalid rejection; the load generator
     deploys from the same package with documented scenario
     selection; each fault scenario documents the dashboard panels
     and AI surfaces it is expected to light up.
4. Deliver the demo dashboards as code.
   - Dependencies: Tasks 2, 3.
   - Completion check: demo dashboards covering a service overview, a
     logs explorer, latency and traces, and an errors-and-alerts view
     live under the platform dashboard provisioning paths, carry the
     standard filters (time range, tenant, service, namespace,
     severity or status), and pass the visualization validation path.
5. Deliver the AI playground prompt pack.
   - Dependencies: Tasks 2, 3.
   - Completion check: a prompt pack document provides ready-to-use
     prompts bound to actual MCP catalog tools, covering service
     health, log and trace investigation, and fault RCA over the
     demo scenarios; every prompt names the tools it exercises and
     the demo scenario that produces the data it needs; read-path by
     default, with any write-path prompt routed through the approval
     flow unchanged.
6. Deliver the playground guide, validators, and registration.
   - Dependencies: Tasks 1-5.
   - Completion check: `docs/product/PLAYGROUND_GUIDE.md` walks setup
     end to end (platform install or dev-stack reuse, demo deploy,
     scenario runs, dashboards, AI prompts, teardown) and is
     registered in `docs/product/INDEX.md` with the product docs
     validator staying green; `validate_demo_playground.sh` and
     `validate_batch27_smoke.sh` pass; the batch is registered in
     `validate_all_batches_with_report.sh`; a demo playground
     runbook is registered in `validate_runbook_links.sh`.

## Batch Completion Gate

Before moving to the next batch:

- All completion checks in the current batch pass.
- New or changed runbooks are updated.
- Security, reliability, and rollback checks are complete.
- Outstanding risks are documented with owners and due dates.
