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
| Batch 10 | `TR-08`, `TR-09` |
| Batch 11 | `TR-08`, `TR-11` |
| Batch 12 | `TR-08`, `TR-09`, `TR-13` |

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
| `TB-10` | Batch 10 - Vector Foundations | `TR-08`, `TR-09` |
| `TB-11` | Batch 11 - Graph Foundation | `TR-08`, `TR-11` |
| `TB-12` | Batch 12 - Risk Scoring and Assisted RCA Readiness | `TR-08`, `TR-09`, `TR-13` |

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

## Batch Completion Gate

Before moving to the next batch:

- All completion checks in the current batch pass.
- New or changed runbooks are updated.
- Security, reliability, and rollback checks are complete.
- Outstanding risks are documented with owners and due dates.
