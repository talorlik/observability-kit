# Observability Platform Implementation Tasks

## 1. Purpose

This document is the execution backlog for building the full observability
platform in this repository. It converts planning artifacts into concrete,
batch-executable implementation tasks that create or modify real repository
artifacts.

## 2. How To Use This Document

- Execute one batch at a time in numeric order unless a task states otherwise.
- Start each task only after all dependencies are complete.
- Treat each task as implementation work, not analysis work.
- Do not mark a task complete until validation and completion criteria pass.
- If validation fails, use rollback notes to return to a safe state.

## 3. Source-Of-Truth Hierarchy

1. `docs/auxiliary/AI_prompts/SYSTEM_INSTRUCTIONS_DOCS.md` (if present in execution
  context)
2. `docs/auxiliary/planning/OBSERVABILITY_PLATFORM_V2.plan.md`
3. `docs/auxiliary/planning/PRD.md`
4. `docs/auxiliary/planning/TECHNICAL.md`
5. `docs/auxiliary/planning/TASKS.md`

## 4. Implementation Principles

- Cloud agnostic, Kubernetes-native, and open-source-first.
- OpenTelemetry is the only baseline collector path.
- OpenSearch is the default data tier.
- Visualization is multi-tool by design with OpenSearch Dashboards and Grafana
  as core UIs.
- Neo4j is optional and derived only.
- Core platform and adapters remain strictly separated.
- Guided install and discovery-first behavior is mandatory.
- Every task produces concrete repository artifacts.
- Every task includes validation and rollback-safe behavior.

## 5. Batch-To-Reference Mapping Table

| Batch | Scope | Primary Technical Markers | Primary Functional Markers | Plan Phase |
| ---- | ---- | ---- | ---- | ---- |
| Batch 1 (`TB-01`) | Foundation and productization | `TR-10`, `TR-14` | `FR-001`, `FR-007`, `FR-018`, `FR-020` | Phase 1.0 |
| Batch 2 (`TB-02`) | Compatibility and mode system | `TR-04`, `TR-05`, `TR-14` | `FR-002`, `FR-003`, `FR-004`, `FR-005`, `FR-006` | Phase 1.0 |
| Batch 3 (`TB-03`) | Preflight and discovery engine | `TR-04`, `TR-05`, `TR-10` | `FR-003`, `FR-004`, `FR-005`, `FR-006` | Phase 1.0 |
| Batch 4 (`TB-04`) | Collector core topology | `TR-06`, `TR-11` | `FR-008`, `FR-009`, `FR-010`, `FR-019` | Phase 1.1 |
| Batch 5 (`TB-05`) | Logs pipeline | `TR-06`, `TR-07` | `FR-011`, `FR-010`, `FR-016` | Phase 1.1 |
| Batch 6 (`TB-06`) | Metrics and traces pipelines | `TR-06`, `TR-07` | `FR-012`, `FR-013`, `FR-016` | Phase 1.2 |
| Batch 7 (`TB-07`) | Onboarding model | `TR-06`, `TR-09`, `TR-12` | `FR-014`, `FR-015`, `FR-018` | Phase 1.2 |
| Batch 8 (`TB-08`) | Security, governance, resilience | `TR-07`, `TR-09`, `TR-12` | `FR-017`, `FR-020`, `FR-021`, `FR-022` | Phase 1.3-1.4 |
| Batch 9 (`TB-09`) | Operator UX and SLO ops | `TR-06`, `TR-10`, `TR-12` | `FR-016`, `FR-018`, `FR-019` | Phase 1.4 |
| Batch 9A (`TB-09A`) | Visualization and admin access plane | `TR-03`, `TR-09`, `TR-12` | `FR-027`, `FR-028`, `FR-029`, `FR-030` | Phase 1.4 |
| Batch 10 (`TB-10`) | Vector foundations | `TR-08`, `TR-09` | `FR-023` | Phase 2 |
| Batch 11 (`TB-11`) | Graph foundations | `TR-08`, `TR-11` | `FR-024` | Phase 3 |
| Batch 12 (`TB-12`) | Risk scoring and RCA readiness | `TR-08`, `TR-09`, `TR-13` | `FR-025`, `FR-026` | Phase 4-5 prep |
| Batch 13 (`TB-13`) | Core adapter integrations | `TR-03`, `TR-09`, `TR-10` | `FR-022` | Phase 1.4-2 bridge |

## 6. Repository Artifact Map

The platform execution path targets these repository areas:

- `install/discovery-engine/` for preflight, probes, and recommendation logic.
- `install/profiles/` for mode, compatibility, and integration profiles.
- `gitops/bootstrap/argocd/` for GitOps bootstrap and app-of-apps.
- `gitops/platform/observability/` for collector, search, and dashboard packaging.
- `gitops/platform/security/` for cert-manager, policy, identity, and secrets.
- `gitops/platform/storage/` for retention, backup, and restore support.
- `gitops/platform/search/` for OpenSearch and Dashboards packaging.
- `gitops/platform/graph/` for optional Neo4j package.
- `gitops/libraries/helm/observability-lib/` for workload onboarding library chart.
- `contracts/` for validation contracts used by CI and smoke tests.
- `scripts/ci/` for deterministic validation and batch smoke scripts.
- `tests/` for synthetic telemetry and end-to-end assertions.
- `docs/runbooks/` for install, validation, rollback, uninstall, and operations.

## 7. Implementation Batches

### Batch 1 - Delivery Foundation (`TB-01`)

Batch goal: establish productized repository structure, install contract, CI
gates, and runbook scaffolds.

#### Task IMP-01.1 - Install Contract Schema Baseline

- **Why it exists:** enforce deterministic install inputs and validation.
- **Depends on:** none.
- **Reference links:** `TB-01`, `TR-10`, `TR-14`, `FR-001`, Phase 1.0.
- **Implementation targets:**
- `contracts/install/INSTALL_CONTRACT.schema.json`
- `contracts/install/INSTALL_CONTRACT.example.yaml`
- `tests/contracts/test_install_contract.py`
- **Execution details:**
- Define required fields for mode, cluster context, storage, identity, secrets.
- Add strict type rules and enum constraints for deployment mode.
- Add one valid and one invalid sample document.
- Add schema test that validates expected pass and fail fixtures.
- **Expected outputs:** schema, fixtures, automated contract test.
- **Validation:** contract test passes in CI; invalid fixture fails as expected.
- **Rollback / safe failure note:** keep prior schema version in VCS tag; if
  schema breaks dependent tasks, pin validation to previous schema file.
- **Completion criteria:** schema is consumed by batch scripts and CI.

#### Task IMP-01.2 - Core GitOps Skeleton

- **Why it exists:** create stable paths for later chart and values work.
- **Depends on:** none.
- **Reference links:** `TB-01`, `TR-10`, `TR-14`, `FR-007`, Phase 1.0.
- **Implementation targets:**
- `gitops/bootstrap/argocd/`
- `gitops/platform/observability/chart/`
- `gitops/platform/observability/values/`
- `gitops/platform/search/opensearch/`
- `gitops/platform/search/dashboards/`
- **Execution details:**
- Create missing directory structure aligned to platform modules.
- Add placeholder `kustomization.yaml` and minimal chart metadata files.
- Add README files that define ownership and usage of each path.
- Wire root GitOps index in `gitops/README.md`.
- **Expected outputs:** bootstrap directories and baseline manifests.
- **Validation:** `kustomize build` and helm template checks pass for stubs.
- **Rollback / safe failure note:** revert newly added folders as one commit if
  render checks fail broadly.
- **Completion criteria:** all referenced paths resolve and render stubs.

#### Task IMP-01.3 - CI Validation and Policy Gate

- **Why it exists:** block invalid config, policy drift, and secret leakage.
- **Depends on:** `IMP-01.1`, `IMP-01.2`.
- **Reference links:** `TB-01`, `TR-10`, `TR-14`, `FR-018`, `NFR-004`.
- **Implementation targets:**
- `.github/workflows/ci.yaml`
- `scripts/ci/validate_batch1_smoke.sh`
- `scripts/ci/validate_markdown.sh`
- **Execution details:**
- Add CI jobs for markdown, YAML, Helm template, and contract validation.
- Add policy check stage for required labels and prohibited hard-coded values.
- Add secret scan stage in pull request workflow.
- Add batch smoke script that runs all foundation checks in one command.
- **Expected outputs:** deterministic CI stages and batch smoke command.
- **Validation:** seeded invalid YAML and seeded secret are both rejected in CI.
- **Rollback / safe failure note:** disable only failing job gates with
  documented temporary exception and expiry date.
- **Completion criteria:** main branch enforces checks without manual bypass.

#### Task IMP-01.4 - Baseline Runbook Set

- **Why it exists:** provide operator entrypoints for install and failure paths.
- **Depends on:** `IMP-01.1`, `IMP-01.3`.
- **Reference links:** `TB-01`, `TR-14`, `FR-020`, `NFR-006`.
- **Implementation targets:**
- `docs/runbooks/INSTALL_RUNBOOK.md`
- `docs/runbooks/VALIDATION_RUNBOOK.md`
- `docs/runbooks/ROLLBACK_UNINSTALL_RUNBOOK.md`
- **Execution details:**
- Create runbook templates with prerequisites, commands, and verification steps.
- Add explicit rollback and uninstall command paths.
- Cross-link runbooks from root `README.md`.
- Add CI check that verifies runbook links resolve.
- **Expected outputs:** actionable runbooks and link verification check.
- **Validation:** runbook link validation job passes.
- **Rollback / safe failure note:** if link check breaks release flow, revert
  latest runbook-only edits and restore previous valid links.
- **Completion criteria:** operators can execute baseline install validation path.

### Batch 2 - Compatibility and Modes (`TB-02`)

Batch goal: define support matrix, profiles, and deterministic mode selection.

#### Task IMP-02.1 - Compatibility Matrix Artifacts

- **Why it exists:** codify support boundaries and prevent unsafe installs.
- **Depends on:** `IMP-01.1`.
- **Reference links:** `TB-02`, `TR-04`, `TR-14`, `FR-002`, Phase 1.0.
- **Implementation targets:**
- `install/profiles/compatibility/COMPATIBILITY_MATRIX.yaml`
- `install/profiles/compatibility/COMPATIBILITY_RULES.schema.json`
- **Execution details:**
- Define supported Kubernetes versions and distro states.
- Add `supported`, `conditional`, and `blocked` grading rules.
- Add schema validation for matrix integrity.
- Document update process for future version additions.
- **Expected outputs:** machine-readable matrix and rules schema.
- **Validation:** sample clusters map to expected grades in matrix tests.
- **Rollback / safe failure note:** keep previous matrix snapshot and switch
  grader to previous file if rules produce broad false blocks.
- **Completion criteria:** matrix consumed by discovery engine with
  deterministic output.

#### Task IMP-02.2 - Profile Schema Definitions

- **Why it exists:** standardize optional platform profile inputs.
- **Depends on:** `IMP-01.1`.
- **Reference links:** `TB-02`, `TR-05`, `TR-14`, `FR-002`, `FR-005`.
- **Implementation targets:**
- `install/profiles/cluster/PROFILE.schema.json`
- `install/profiles/storage/PROFILE.schema.json`
- `install/profiles/identity/PROFILE.schema.json`
- `install/profiles/secrets/PROFILE.schema.json`
- `install/profiles/ingress/PROFILE.schema.json`
- **Execution details:**
- Define shared profile schema core and per-domain overlays.
- Capture prerequisites, defaults, and generated values contract fields.
- Add profile examples for quickstart and production-leaning modes.
- Add schema tests for each profile class.
- **Expected outputs:** profile schemas and validated examples.
- **Validation:** all profile fixtures pass schema checks.
- **Rollback / safe failure note:** fall back to previous profile version files
  if downstream rendering becomes incompatible.
- **Completion criteria:** installer can parse all profile types consistently.

#### Task IMP-02.3 - Mode Recommendation Decision Table

- **Why it exists:** map discovered capabilities to deterministic install mode.
- **Depends on:** `IMP-02.1`, `IMP-02.2`.
- **Reference links:** `TB-02`, `TR-04`, `TR-05`, `FR-003`, `FR-006`.
- **Implementation targets:**
- `install/discovery-engine/mode_recommendation_rules.yaml`
- `install/discovery-engine/remediation_catalog.yaml`
- `tests/discovery/test_mode_recommendation.py`
- **Execution details:**
- Define recommendation logic for `quickstart`, `attach`, `standalone`, `hybrid`.
- Add blocked-condition remediation mappings with action hints.
- Add tests that verify mode recommendation determinism.
- Add tests that ensure every blocked rule has remediation text.
- **Expected outputs:** decision rules, remediation catalog, tests.
- **Validation:** test suite confirms deterministic mode outputs.
- **Rollback / safe failure note:** route recommendation to `attach` safe default
  on rule-evaluation failure.
- **Completion criteria:** discovery can emit mode and remediation bundle.

### Batch 3 - Preflight and Discovery Engine (`TB-03`)

Batch goal: deliver guided preflight, capability discovery, generated overlays,
and post-install readiness reporting.

#### Task IMP-03.1 - Preflight Engine

- **Why it exists:** detect blockers before install attempts.
- **Depends on:** `IMP-02.1`, `IMP-02.3`.
- **Reference links:** `TB-03`, `TR-05`, `FR-004`, Phase 1.0.
- **Implementation targets:**
- `install/discovery-engine/preflight_checks.py`
- `install/discovery-engine/checks/`
- `tests/discovery/test_preflight_checks.py`
- **Execution details:**
- Implement checks for API reachability, RBAC access, CRD presence.
- Include checks for storage class and ingress or Gateway API availability.
- Emit structured pass or fail output with reason and remediation ID.
- Add unit tests for pass, conditional, and fail paths.
- **Expected outputs:** preflight engine module and tests.
- **Validation:** preflight test suite covers all check classes.
- **Rollback / safe failure note:** on check module failure, stop install early
  and emit explicit safe-exit status.
- **Completion criteria:** engine blocks unsupported installs deterministically.

#### Task IMP-03.2 - Discovery Report and Generated Overlays

- **Why it exists:** translate detection outputs into deployable GitOps values.
- **Depends on:** `IMP-03.1`.
- **Reference links:** `TB-03`, `TR-05`, `TR-10`, `FR-006`, `FR-007`.
- **Implementation targets:**
- `install/discovery-engine/report_generator.py`
- `install/discovery-engine/output/`
- `gitops/platform/observability/values/generated/`
- **Execution details:**
- Generate capability, compatibility, mode, and remediation report bundle.
- Render values overlays from profile plus discovery outputs.
- Store generated overlays in deterministic path and naming pattern.
- Add schema checks for generated overlay completeness.
- **Expected outputs:** report JSON or YAML and generated values overlays.
- **Validation:** sample run creates all expected files without manual edits.
- **Rollback / safe failure note:** if generation fails mid-run, remove partial
  generated files and preserve last known-good overlay set.
- **Completion criteria:** outputs are accepted by GitOps render pipeline.

#### Task IMP-03.3 - Post-Install Readiness and Smoke Bundle

- **Why it exists:** confirm install health and telemetry path readiness.
- **Depends on:** `IMP-03.2`, `IMP-01.4`.
- **Reference links:** `TB-03`, `TR-10`, `FR-018`, `FR-019`.
- **Implementation targets:**
- `scripts/validate/post_install_readiness.sh`
- `tests/smoke/platform_smoke_bundle/`
- `contracts/install/POST_INSTALL_READINESS.schema.json`
- **Execution details:**
- Implement readiness checks for collector health and backend ingest readiness.
- Add smoke tests for logs, metrics, traces, and dashboard accessibility.
- Emit readiness report against schema contract.
- Add CI entrypoint for post-install smoke execution.
- **Expected outputs:** readiness script, smoke tests, readiness contract.
- **Validation:** smoke bundle passes on reference cluster profile.
- **Rollback / safe failure note:** on readiness failure, halt promotion and keep
  previous release active.
- **Completion criteria:** release gate requires readiness success evidence.

### Batch 4 - Collector Core Topology (`TB-04`)

Batch goal: operational OpenTelemetry operator, agent, gateway, processors,
and failure simulation evidence.

#### Task IMP-04.1 - OpenTelemetry Operator and Collector Packaging

- **Why it exists:** provide baseline collector control plane and runtime.
- **Depends on:** `IMP-03.2`.
- **Reference links:** `TB-04`, `TR-06`, `TR-11`, `FR-008`, `FR-009`.
- **Implementation targets:**
- `gitops/platform/observability/chart/`
- `gitops/platform/observability/values/otel-operator.yaml`
- `gitops/platform/observability/values/otel-agent.yaml`
- `gitops/platform/observability/values/otel-gateway.yaml`
- **Execution details:**
- Add chart values for OpenTelemetry Operator deployment.
- Add agent DaemonSet values for passive log and host metrics collection.
- Add gateway Deployment values for OTLP ingest and export.
- Add liveness and readiness probes for both collector classes.
- **Expected outputs:** renderable operator and collector manifests.
- **Validation:** helm template and cluster dry-run apply both pass.
- **Rollback / safe failure note:** rollback GitOps app revision to prior chart
  values set if collector rollout degrades.
- **Completion criteria:** operator, agent, and gateway reach healthy status.

#### Task IMP-04.2 - Baseline Processor Chains and OTLP Paths

- **Why it exists:** enforce required telemetry processing and routing.
- **Depends on:** `IMP-04.1`.
- **Reference links:** `TB-04`, `TR-06`, `FR-009`, `FR-010`.
- **Implementation targets:**
- `gitops/platform/observability/values/collector-pipelines.yaml`
- `contracts/telemetry/COLLECTOR_PIPELINE_CONTRACT.json`
- **Execution details:**
- Add mandatory processors `k8sattributes`, `resource`, `memory_limiter`, `batch`.
- Add trace sampling default processor chain and environment override capability.
- Configure OTLP exporter targets with profile-derived endpoints.
- Add contract checks that assert processor order and required pipeline nodes.
- **Expected outputs:** validated processor and OTLP routing config.
- **Validation:** collector config test confirms required chains and exports.
- **Rollback / safe failure note:** keep previous collector config map revision
  and revert on startup or export regressions.
- **Completion criteria:** telemetry export path is stable in attach and standalone.

#### Task IMP-04.3 - Collector Health Telemetry and Failure Simulation

- **Why it exists:** verify bounded loss behavior under stress and outage events.
- **Depends on:** `IMP-04.2`.
- **Reference links:** `TB-04`, `TR-11`, `FR-019`, `NFR-001`.
- **Implementation targets:**
- `gitops/platform/search/dashboards/saved-objects/COLLECTOR_HEALTH.ndjson`
- `tests/failure/collector_failure_simulations/`
- `docs/runbooks/COLLECTOR_FAILURE_SIMULATION_RUNBOOK.md`
- **Execution details:**
- Add dashboard views for queue depth, drops, retries, and export latency.
- Add failure simulation scenarios for gateway restart and backend outage.
- Capture expected bounded-loss evidence in simulation outputs.
- Link simulation procedure and recovery steps in runbook.
- **Expected outputs:** health dashboards, simulation tests, operations runbook.
- **Validation:** simulation suite produces expected bounded-loss metrics.
- **Rollback / safe failure note:** disable simulation workload from production
  namespaces if it causes interference.
- **Completion criteria:** reliability evidence is attached to batch gate.

### Batch 5 - Logs Pipeline (`TB-05`)

Batch goal: production-grade logs pipeline with parsing, multiline handling,
redaction, never-index policy, and dashboards.

#### Task IMP-05.1 - Log Parsing and Multiline Rules

- **Why it exists:** normalize logs into queryable schema-compliant records.
- **Depends on:** `IMP-04.2`.
- **Reference links:** `TB-05`, `TR-06`, `TR-07`, `FR-011`.
- **Implementation targets:**
- `gitops/platform/observability/values/logs-pipeline.yaml`
- `contracts/logs/LOG_PARSING_CONTRACT.json`
- `tests/logs/test_multiline_rules.py`
- **Execution details:**
- Add CRI and JSON parser blocks with baseline field mappings.
- Add multiline rules for Java, Go, and Python stack traces.
- Validate parsed output includes required core fields.
- Add fixture-based tests for multiline correctness.
- **Expected outputs:** logs pipeline config and parser tests.
- **Validation:** fixture tests pass for single-line and multiline cases.
- **Rollback / safe failure note:** switch parser mode to passthrough for affected
  sources if parsing introduces loss.
- **Completion criteria:** pipeline parses baseline fixture set successfully.

#### Task IMP-05.2 - Redaction and Never-Index Policy

- **Why it exists:** prevent sensitive data from storage and retrieval.
- **Depends on:** `IMP-05.1`.
- **Reference links:** `TB-05`, `TR-07`, `TR-09`, `FR-011`, `NFR-004`.
- **Implementation targets:**
- `gitops/platform/observability/values/logs-redaction.yaml`
- `contracts/logs/NEVER_INDEX_RULES.json`
- `tests/logs/test_redaction_policy.py`
- **Execution details:**
- Define redact rules for secret-like keys and sensitive token patterns.
- Define never-index rules for prohibited fields and payload regions.
- Add unit tests for redact replacement and field removal behavior.
- Add CI test that fails when prohibited patterns are still indexed.
- **Expected outputs:** redaction policy config and automated validation.
- **Validation:** seeded sensitive fixtures are redacted or dropped.
- **Rollback / safe failure note:** if over-redaction impacts operations, move
  affected rules to warn-only and open fast follow-up fix.
- **Completion criteria:** prohibited sensitive data is absent from indexed docs.

#### Task IMP-05.3 - Logs Storage Contracts and Dashboarding

- **Why it exists:** enforce index lifecycle controls and operator observability.
- **Depends on:** `IMP-05.2`.
- **Reference links:** `TB-05`, `TR-07`, `FR-010`, `FR-016`.
- **Implementation targets:**
- `gitops/platform/search/opensearch/templates/logs-template.json`
- `gitops/platform/search/opensearch/ilm/logs-ilm-policy.json`
- `gitops/platform/search/dashboards/saved-objects/LOGS_OPERATIONS.ndjson`
- **Execution details:**
- Add `logs-*` index template with strict mappings for known fields.
- Add lifecycle policy for rollover and retention.
- Add dashboard views for parse errors, lag, and redaction counters.
- Add contract validation for template and policy installation.
- **Expected outputs:** OpenSearch template, ILM policy, and saved objects.
- **Validation:** template and policy install cleanly; dashboards render.
- **Rollback / safe failure note:** revert alias routing to prior index family if
  template deployment causes write failures.
- **Completion criteria:** logs ingestion and operations dashboards are stable.

### Batch 6 - Metrics and Traces Pipelines (`TB-06`)

Batch goal: complete metric and trace ingestion, sampling defaults, correlation,
and signal dashboards.

#### Task IMP-06.1 - Metrics Subscription and OTLP Metrics Path

- **Why it exists:** support low-touch metrics onboarding with stable contracts.
- **Depends on:** `IMP-04.2`.
- **Reference links:** `TB-06`, `TR-06`, `TR-07`, `FR-012`.
- **Implementation targets:**
- `gitops/platform/observability/values/metrics-pipeline.yaml`
- `contracts/metrics/METRICS_SUBSCRIPTION_CONTRACT.json`
- `tests/metrics/test_annotation_onboarding.py`
- **Execution details:**
- Enable annotation and label-based scrape target discovery.
- Add OTLP metrics receiver path for instrumented services.
- Enforce metric naming and metadata normalization rules.
- Add tests for scrape and OTLP metrics ingest cases.
- **Expected outputs:** metrics pipeline config and subscription tests.
- **Validation:** opted-in workload metrics appear in target index family.
- **Rollback / safe failure note:** disable auto-scrape for offending namespace
  and retain OTLP-only path during remediation.
- **Completion criteria:** metrics ingestion contract passes for reference services.

#### Task IMP-06.2 - Trace Ingestion and Sampling Defaults

- **Why it exists:** provide bounded trace volume with correlation readiness.
- **Depends on:** `IMP-04.2`.
- **Reference links:** `TB-06`, `TR-06`, `FR-013`, `NFR-002`.
- **Implementation targets:**
- `gitops/platform/observability/values/traces-pipeline.yaml`
- `contracts/traces/TRACE_SAMPLING_CONTRACT.json`
- `tests/traces/test_sampling_defaults.py`
- **Execution details:**
- Add OTLP trace receiver path and required trace processors.
- Define default sampling policy with environment overrides.
- Add contract tests for sampling configuration and expected behavior.
- Add load test fixture to validate bounded ingestion under burst.
- **Expected outputs:** trace pipeline config and sampling tests.
- **Validation:** trace ingest succeeds and sampling targets match policy.
- **Rollback / safe failure note:** switch to conservative head sampling fallback
  if tail policies destabilize gateway.
- **Completion criteria:** trace volume control works without losing critical spans.

#### Task IMP-06.3 - Trace-Log Correlation and Signal Dashboards

- **Why it exists:** enable operator pivots across all three telemetry signals.
- **Depends on:** `IMP-05.3`, `IMP-06.1`, `IMP-06.2`.
- **Reference links:** `TB-06`, `TR-06`, `FR-016`.
- **Implementation targets:**
- `gitops/platform/search/dashboards/saved-objects/METRICS_TRACES_OVERVIEW.ndjson`
- `tests/e2e/test_trace_log_correlation.py`
- **Execution details:**
- Ensure `trace_id` and `span_id` are retained in logs and traces where present.
- Add dashboards for metric latency, error rate, and trace drilldown.
- Add end-to-end test validating trace-to-log and log-to-trace pivots.
- Capture evidence bundle for correlation validation gate.
- **Expected outputs:** dashboards and correlation evidence tests.
- **Validation:** correlation test passes with synthetic and pilot data.
- **Rollback / safe failure note:** disable pivot links if field mismatches occur,
  while preserving core ingestion.
- **Completion criteria:** operators can pivot signals without manual query stitching.

### Batch 7 - Onboarding and Subscription Model (`TB-07`)

Batch goal: one-block onboarding via library chart, policy checks, and
troubleshooting path.

#### Task IMP-07.1 - `observability-lib` Helm Library

- **Why it exists:** standardize workload onboarding into a low-touch contract.
- **Depends on:** `IMP-01.2`, `IMP-06.3`.
- **Reference links:** `TB-07`, `TR-06`, `TR-09`, `FR-014`, `FR-015`.
- **Implementation targets:**
- `gitops/libraries/helm/observability-lib/Chart.yaml`
- `gitops/libraries/helm/observability-lib/templates/`
- `gitops/libraries/helm/observability-lib/values.schema.json`
- **Execution details:**
- Create reusable templates for labels, annotations, env vars, and OTEL config.
- Implement mode toggles for passive, low-touch, and instrumentation-aware paths.
- Add values schema with required ownership and environment metadata.
- Add chart unit tests for template rendering by mode.
- **Expected outputs:** reusable onboarding library and schema tests.
- **Validation:** sample service chart renders from one onboarding values block.
- **Rollback / safe failure note:** keep service-local override templates if
  library update introduces blocking render regressions.
- **Completion criteria:** at least one pilot service onboarded through library.

#### Task IMP-07.2 - Metadata and Policy Enforcement

- **Why it exists:** enforce governance and contract compliance at onboarding.
- **Depends on:** `IMP-07.1`, `IMP-01.3`.
- **Reference links:** `TB-07`, `TR-09`, `TR-12`, `FR-014`, `FR-018`.
- **Implementation targets:**
- `gitops/platform/security/kyverno/`
- `contracts/onboarding/ONBOARDING_METADATA_CONTRACT.json`
- `tests/policy/test_onboarding_metadata_policy.py`
- **Execution details:**
- Add policies requiring `service.name`, `environment`, and ownership labels.
- Block onboarding manifests missing required metadata.
- Add policy test fixtures for valid and invalid onboarding manifests.
- Add CI job for onboarding policy checks.
- **Expected outputs:** policy manifests and metadata validation tests.
- **Validation:** non-compliant onboarding is rejected with clear failure output.
- **Rollback / safe failure note:** switch failing strict policy to audit mode
  temporarily with tracked remediation due date.
- **Completion criteria:** policy gate active in CI and cluster admission.

#### Task IMP-07.3 - Onboarding Examples and Troubleshooting Guide

- **Why it exists:** reduce onboarding lead time and support self-service teams.
- **Depends on:** `IMP-07.1`, `IMP-07.2`.
- **Reference links:** `TB-07`, `TR-12`, `FR-015`, `NFR-006`.
- **Implementation targets:**
- `docs/onboarding/ONBOARDING_VALUES_CONTRACT.md`
- `docs/onboarding/ONBOARDING_EXAMPLES.md`
- `docs/onboarding/TROUBLESHOOTING.md`
- `tests/e2e/test_one_block_onboarding.py`
- **Execution details:**
- Document one-block onboarding contract with mode examples.
- Add troubleshooting tree for schema, policy, and runtime failures.
- Add e2e test that onboards a sample service from one values block.
- Link onboarding docs from root README and runbooks.
- **Expected outputs:** onboarding docs and one-block e2e test.
- **Validation:** one-block onboarding test passes in CI smoke.
- **Rollback / safe failure note:** revert onboarding example updates if they no
  longer match current values schema.
- **Completion criteria:** new team can self-onboard without platform code edits.

### Batch 8 - Security, Isolation, and Resilience (`TB-08`)

Batch goal: tenant isolation, encryption controls, audit logging, and proven
backup, restore, rollback, and uninstall paths.

#### Task IMP-08.1 - Team and Environment Isolation

- **Why it exists:** prevent cross-tenant visibility and unauthorized access.
- **Depends on:** `IMP-05.3`, `IMP-06.3`, `IMP-07.2`.
- **Reference links:** `TB-08`, `TR-07`, `TR-09`, `FR-017`.
- **Implementation targets:**
- `gitops/platform/search/opensearch/security/roles/`
- `gitops/platform/search/opensearch/security/role-mappings/`
- `gitops/platform/search/dashboards/spaces/`
- **Execution details:**
- Define role model for environment and team-level index access boundaries.
- Add role mappings and dashboard space permissions.
- Add negative tests for blocked cross-team access attempts.
- Document identity and role assumptions in security guide.
- **Expected outputs:** RBAC artifacts and isolation tests.
- **Validation:** cross-team access test cases fail as expected.
- **Rollback / safe failure note:** restore previous role mappings from backup if
  legitimate operator access is blocked.
- **Completion criteria:** isolation enforcement verified in runtime tests.

#### Task IMP-08.2 - Encryption, Audit Logging, and Governance Evidence

- **Why it exists:** satisfy security and auditability requirements.
- **Depends on:** `IMP-08.1`.
- **Reference links:** `TB-08`, `TR-09`, `FR-017`, `NFR-005`.
- **Implementation targets:**
- `gitops/platform/security/cert-manager/`
- `contracts/security/ENCRYPTION_CONTROLS_VALIDATION.json`
- `contracts/security/AUDIT_LOGGING_VALIDATION.json`
- `tests/security/test_audit_event_capture.py`
- **Execution details:**
- Configure TLS certificate management for collector and backend traffic.
- Enable audit logging for access, config changes, and onboarding actions.
- Add contracts for encryption controls and audit event completeness.
- Add tests validating audit event generation and retention.
- **Expected outputs:** encryption and audit governance artifacts.
- **Validation:** security contract checks and audit tests pass in CI.
- **Rollback / safe failure note:** if certificate rollout fails, revert to prior
  secret and certificate revision while preserving encrypted transport.
- **Completion criteria:** required encryption and audit evidence is available.

#### Task IMP-08.3 - Backup, Restore, Rollback, and Uninstall Drills

- **Why it exists:** prove operational recoverability and safe failure behavior.
- **Depends on:** `IMP-08.2`, `IMP-01.4`.
- **Reference links:** `TB-08`, `TR-12`, `FR-020`, `FR-021`.
- **Implementation targets:**
- `gitops/platform/storage/velero/`
- `scripts/ops/run_restore_drill.sh`
- `scripts/ops/run_rollback_drill.sh`
- `scripts/ops/run_uninstall_validation.sh`
- `docs/runbooks/DR_RESTORE_RUNBOOK.md`
- **Execution details:**
- Define scheduled snapshot and backup workflow for telemetry indices.
- Implement restore drill script with success verification checks.
- Implement rollback drill for GitOps revision and exporter route changes.
- Implement uninstall validation script with cleanup and post-checks.
- **Expected outputs:** drill scripts and DR plus uninstall runbook updates.
- **Validation:** non-production restore and rollback drills complete successfully.
- **Rollback / safe failure note:** if drill fails, stop promotion and keep prior
  stable deployment until root cause is resolved.
- **Completion criteria:** recovery and uninstall evidence attached to release gate.

### Batch 9 - Operator Experience and SLO Operations (`TB-09`)

Batch goal: dashboard taxonomy, health alerts, SLOs, burn-rate operations, and
incident drill evidence.

#### Task IMP-09.1 - Dashboard Taxonomy and Saved Objects Packaging

- **Why it exists:** make observability surfaces predictable and navigable.
- **Depends on:** `IMP-05.3`, `IMP-06.3`, `IMP-08.1`.
- **Reference links:** `TB-09`, `TR-10`, `FR-016`, `FR-019`.
- **Implementation targets:**
- `gitops/platform/search/dashboards/saved-objects/PLATFORM_OVERVIEW.ndjson`
- `gitops/platform/search/dashboards/saved-objects/SERVICE_OVERVIEW.ndjson`
- `gitops/platform/search/dashboards/saved-objects/GOVERNANCE_OVERVIEW.ndjson`
- **Execution details:**
- Define taxonomy for platform, service, and governance dashboard domains.
- Package saved objects into deterministic import bundle.
- Add CI validation to detect broken object references.
- Document dashboard ownership and update path.
- **Expected outputs:** versioned dashboard bundles and validation check.
- **Validation:** saved objects import cleanly on test cluster.
- **Rollback / safe failure note:** restore previous saved object bundle if new
  objects break navigation or visualizations.
- **Completion criteria:** dashboard structure is stable and discoverable.

#### Task IMP-09.2 - Platform Health Alerts and SLO Burn-Rate Rules

- **Why it exists:** detect platform regressions and service SLO risk early.
- **Depends on:** `IMP-04.3`, `IMP-09.1`.
- **Reference links:** `TB-09`, `TR-06`, `TR-12`, `FR-016`.
- **Implementation targets:**
- `gitops/platform/search/dashboards/alerts/platform_health_rules.ndjson`
- `gitops/platform/search/dashboards/alerts/slo_burn_rate_rules.ndjson`
- `contracts/slo_ops/PLATFORM_HEALTH_ALERTS_VALIDATION.json`
- **Execution details:**
- Add alerts for collector drops, ingest lag, and backend health failures.
- Define baseline SLI queries and SLO thresholds for pilot services.
- Add burn-rate and symptom alerts with runbook URL links.
- Add alert rule validation contracts.
- **Expected outputs:** alert rule packs and SLO validation contracts.
- **Validation:** synthetic event tests trigger expected alert routes.
- **Rollback / safe failure note:** disable high-noise rules while preserving
  critical symptom rules during tuning.
- **Completion criteria:** alerting behavior is reliable and linked to runbooks.

#### Task IMP-09.3 - Incident Drill and Noise Reduction Loop

- **Why it exists:** reduce MTTR and improve signal quality over time.
- **Depends on:** `IMP-09.2`.
- **Reference links:** `TB-09`, `TR-12`, `FR-018`, `NFR-006`.
- **Implementation targets:**
- `docs/runbooks/INCIDENT_DRILL_RUNBOOK.md`
- `contracts/slo_ops/INCIDENT_DRILL_EVIDENCE_VALIDATION.json`
- `contracts/slo_ops/ALERT_NOISE_REDUCTION_VALIDATION.json`
- **Execution details:**
- Execute tabletop drill with dashboards, alerts, and runbooks.
- Capture response timeline, escalations, and remediation actions.
- Record false-positive and noise metrics before and after tuning cycle.
- Commit tuned thresholds and drill outcomes as evidence artifacts.
- **Expected outputs:** drill evidence and alert-noise trend artifacts.
- **Validation:** drill evidence contract and noise trend checks pass.
- **Rollback / safe failure note:** restore prior alert thresholds if tuning
  reduces incident detection sensitivity.
- **Completion criteria:** two review cycles show improved alert quality.

### Batch 9A - Visualization and Admin Access Plane (`TB-09A`)

Batch goal: implement core multi-tool visualization and secure external admin
GUI exposure.

#### Task IMP-09A.1 - Visualization Ownership Contract

- **Why it exists:** prevent UI ambiguity and enforce signal-to-tool ownership.
- **Depends on:** `IMP-09.1`.
- **Reference links:** `TB-09A`, `TR-03`, `FR-027`.
- **Implementation targets:**
- `contracts/visualization/SIGNAL_UI_OWNERSHIP.yaml`
- `docs/runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md`
- **Execution details:**
- Define canonical ownership for logs, metrics, traces, and graph workflows.
- Include rule for Grafana as mandatory core UI and Jaeger or Bloom as optional.
- Add validation rule that fails if required ownership entries are missing.
- **Expected outputs:** ownership contract, runbook update, validation check.
- **Validation:** contract lint confirms all required signals map to core UIs.
- **Rollback / safe failure note:** revert to previous contract revision and block
  promotion if mapping causes dashboard contract conflicts.
- **Completion criteria:** ownership matrix is enforced in CI and documented.

#### Task IMP-09A.2 - Core UI Provisioning Paths

- **Why it exists:** ensure deterministic GitOps provisioning for core UIs.
- **Depends on:** `IMP-09A.1`.
- **Reference links:** `TB-09A`, `TR-03`, `FR-027`, `FR-029`.
- **Implementation targets:**
- `gitops/platform/search/dashboards/`
- `gitops/platform/observability/grafana/`
- `contracts/visualization/UI_PROVISIONING_CONTRACT.json`
- **Execution details:**
- Add provisioning paths for OpenSearch Dashboards assets and Grafana dashboards.
- Define dashboard taxonomy for platform, NOC, service, and executive views.
- Add contract checks for required folder and asset naming conventions.
- **Expected outputs:** versioned UI asset paths and provisioning contract.
- **Validation:** GitOps render confirms both tool paths are referenced and valid.
- **Rollback / safe failure note:** disable only newly introduced UI app entries
  while preserving previous dashboard delivery path.
- **Completion criteria:** both core UI stacks provision from repository assets.

#### Task IMP-09A.3 - Admin Access Plane Manifests and Profiles

- **Why it exists:** externalize admin GUIs without requiring cluster shell access.
- **Depends on:** `IMP-03.1`, `IMP-03.2`, `IMP-08.1`.
- **Reference links:** `TB-09A`, `TR-09`, `TR-12`, `FR-028`.
- **Implementation targets:**
- `install/profiles/admin-access/PROFILE.schema.json`
- `gitops/platform/access/admin-ingress/`
- `gitops/platform/access/admin-gateway/`
- **Execution details:**
- Add profile schema for endpoint mode, TLS source, authn mode, and RBAC mapping.
- Implement ingress and Gateway API manifests for OpenSearch Dashboards, Grafana,
  and graph-enabled Neo4j Browser endpoints.
- Add placeholders for optional Jaeger UI and optional Neo4j Bloom exposure.
- **Expected outputs:** profile schema and renderable access manifests.
- **Validation:** schema tests and manifest render checks pass for both modes.
- **Rollback / safe failure note:** switch admin access profile to internal-only
  mode and disable external routes if access checks fail.
- **Completion criteria:** profile-driven admin exposure manifests are available.

#### Task IMP-09A.4 - TLS, Authn/Authz, and GUI Smoke Validation

- **Why it exists:** verify secure reachability and role-scoped access
  for admin UIs.
- **Depends on:** `IMP-09A.2`, `IMP-09A.3`.
- **Reference links:** `TB-09A`, `TR-09`, `TR-12`, `FR-028`, `FR-030`.
- **Implementation targets:**
- `tests/smoke/admin_gui/`
- `scripts/validate/admin_gui_smoke.sh`
- `contracts/install/ADMIN_GUI_READINESS.schema.json`
- **Execution details:**
- Add endpoint, TLS, and login checks for enabled admin GUIs.
- Add role-scoped checks for read-only and admin personas.
- Emit readiness report with per-UI pass or fail status.
- Wire checks into post-install and batch smoke execution.
- **Expected outputs:** smoke suite, readiness schema, CI gate integration.
- **Validation:** smoke suite passes for enabled UIs and fails on expected
  break cases.
- **Rollback / safe failure note:** keep prior access route set active and block
  promotion until smoke failures are resolved.
- **Completion criteria:** admin GUI readiness evidence is mandatory for release.

### Batch 10 - Vector Foundations (`TB-10`)

Batch goal: curated evidence extraction, embedding pipeline, vector indexing,
semantic retrieval service, and governance controls.

#### Task IMP-10.1 - Curated Evidence Extraction Pipeline

- **Why it exists:** define governable source artifacts for semantic retrieval.
- **Depends on:** `IMP-09.3`.
- **Reference links:** `TB-10`, `TR-08`, `TR-09`, `FR-023`, Phase 2.
- **Implementation targets:**
- `pipelines/vector/extraction_pipeline.py`
- `contracts/vector/CURATED_ARTIFACT_OWNERSHIP_VALIDATION.json`
- `contracts/vector/EXTRACTION_SNAPSHOTS_VALIDATION.json`
- **Execution details:**
- Define curated input classes: incidents, summaries, runbooks, diagnostics.
- Implement extraction jobs from telemetry and docs into versioned snapshots.
- Tag artifacts with owner, source, and retention metadata.
- Add contracts that ensure ownership and snapshot integrity.
- **Expected outputs:** extraction job and governed snapshot artifacts.
- **Validation:** extraction run produces versioned snapshot bundle.
- **Rollback / safe failure note:** freeze snapshot updates and use previous
  snapshot version if extraction produces invalid artifacts.
- **Completion criteria:** curated snapshot is queryable and contract-validated.

#### Task IMP-10.2 - Embedding Pipeline and `vectors-*` Indices

- **Why it exists:** materialize semantic vectors in OpenSearch.
- **Depends on:** `IMP-10.1`.
- **Reference links:** `TB-10`, `TR-08`, `FR-023`.
- **Implementation targets:**
- `pipelines/vector/embedding_pipeline.py`
- `gitops/platform/search/opensearch/templates/vectors-template.json`
- `contracts/vector/VECTORS_INDEX_WRITE_VALIDATION.json`
- **Execution details:**
- Implement batch embedding generation for curated artifacts.
- Define vector index template with metadata and distance strategy fields.
- Write embeddings and metadata to `vectors-*` index family.
- Add validation contract for vector write correctness and mapping integrity.
- **Expected outputs:** embedding pipeline and vector index template.
- **Validation:** vectors are written and queryable through OpenSearch.
- **Rollback / safe failure note:** pause embedding writes and route retrieval to
  prior vector index alias during mapping or write failures.
- **Completion criteria:** vector index population is stable and reproducible.

#### Task IMP-10.3 - Semantic Retrieval Service and Quality Checks

- **Why it exists:** provide operator-facing retrieval endpoint with governance.
- **Depends on:** `IMP-10.2`.
- **Reference links:** `TB-10`, `TR-09`, `FR-023`, `NFR-005`.
- **Implementation targets:**
- `services/retrieval/semantic_retrieval_service.py`
- `tests/retrieval/test_semantic_quality.py`
- `contracts/vector/RETRIEVAL_QUALITY_BASELINE_VALIDATION.json`
- `contracts/vector/GOVERNANCE_CONTROLS_VALIDATION.json`
- **Execution details:**
- Implement retrieval endpoint with top-k result and score output.
- Add PII filtering and retrieval audit event emission.
- Build baseline relevance test set and score thresholds.
- Add governance and retrieval quality contract checks.
- **Expected outputs:** retrieval service, quality tests, governance contracts.
- **Validation:** quality baseline and governance checks pass.
- **Rollback / safe failure note:** fallback endpoint to lexical-only retrieval
  when vector relevance or governance checks fail.
- **Completion criteria:** semantic retrieval is operational and auditable.

### Batch 11 - Graph Foundations (`TB-11`)

Batch goal: optional Neo4j deployment, graph schema, sync jobs, freshness
monitoring, and operator query support.

#### Task IMP-11.1 - Optional Neo4j Deployment Profile

- **Why it exists:** add graph module without coupling to core telemetry path.
- **Depends on:** `IMP-10.3`.
- **Reference links:** `TB-11`, `TR-08`, `TR-11`, `FR-024`, Phase 3.
- **Implementation targets:**
- `gitops/platform/graph/neo4j/`
- `install/profiles/graph/PROFILE.schema.json`
- `contracts/graph/GRAPH_MODULE_PROFILE_VALIDATION.json`
- **Execution details:**
- Package Neo4j deployment as optional profile-gated module.
- Define enable or disable switch and dependency checks.
- Add graph profile schema and validation contract.
- Document fallback behavior when graph module is disabled.
- **Expected outputs:** optional Neo4j package and profile contract.
- **Validation:** core platform remains healthy with graph both on and off.
- **Rollback / safe failure note:** disable graph module profile and keep core
  telemetry path active on graph deployment failures.
- **Completion criteria:** graph module activation is explicit and reversible.

#### Task IMP-11.2 - Graph Schema and Idempotent Sync Jobs

- **Why it exists:** build consistent derived topology and incident graph.
- **Depends on:** `IMP-11.1`.
- **Reference links:** `TB-11`, `TR-08`, `FR-024`.
- **Implementation targets:**
- `graph/schema/neo4j_schema.cypher`
- `graph/sync/sync_jobs.py`
- `contracts/graph/GRAPH_SCHEMA_VERSIONING_VALIDATION.json`
- `contracts/graph/GRAPH_IDEMPOTENT_SYNC_VALIDATION.json`
- **Execution details:**
- Define schema for service, workload, dependency, owner, and incident nodes.
- Implement sync jobs from OpenSearch plus curated metadata sources.
- Ensure idempotent upsert behavior and conflict-safe key strategy.
- Add schema versioning and sync idempotency validation contracts.
- **Expected outputs:** graph schema, sync jobs, validation contracts.
- **Validation:** repeated sync runs converge to same graph state.
- **Rollback / safe failure note:** stop sync scheduler and restore prior schema
  migration state if integrity checks fail.
- **Completion criteria:** graph is populated and stable across repeated syncs.

#### Task IMP-11.3 - Freshness Monitoring and Operator Query Set

- **Why it exists:** provide trustworthy graph recency and operational use cases.
- **Depends on:** `IMP-11.2`.
- **Reference links:** `TB-11`, `TR-11`, `FR-024`, `NFR-006`.
- **Implementation targets:**
- `graph/queries/topology_queries.cypher`
- `graph/queries/blast_radius_queries.cypher`
- `contracts/graph/GRAPH_FRESHNESS_ALERTS_VALIDATION.json`
- `docs/runbooks/GRAPH_FOUNDATION_OPERATOR_GUIDE.md`
- **Execution details:**
- Add freshness metrics and stale graph alert thresholds.
- Add topology and blast-radius query library for common operations.
- Add freshness alert validation contract.
- Document rebuild, repair, and fallback runbook procedures.
- **Expected outputs:** query library, freshness controls, and runbook.
- **Validation:** stale-data simulation triggers freshness alerts.
- **Rollback / safe failure note:** if freshness signal is unreliable, mark graph
  insights as degraded and suspend graph-dependent alerting.
- **Completion criteria:** operators can run supported queries with freshness trust.

### Batch 12 - Risk Scoring and Assisted RCA Readiness (`TB-12`)

Batch goal: deterministic risk scoring, backtesting, hybrid retrieval
orchestration, human approval, and RCA auditability.

#### Task IMP-12.1 - Deterministic Risk Feature and Scoring Jobs

- **Why it exists:** establish reproducible risk computation before RCA assist.
- **Depends on:** `IMP-11.3`.
- **Reference links:** `TB-12`, `TR-08`, `TR-13`, `FR-025`, Phase 4.
- **Implementation targets:**
- `pipelines/risk/feature_definitions.yaml`
- `pipelines/risk/scoring_job.py`
- `contracts/risk_rca/DETERMINISTIC_RISK_FEATURES_VALIDATION.json`
- `contracts/risk_rca/RISK_SCORING_OUTPUTS_VALIDATION.json`
- **Execution details:**
- Define deterministic feature set from graph and telemetry evidence.
- Implement scoring job with versioned model-free weighting logic.
- Emit scoring outputs with feature attribution details.
- Add contracts for deterministic features and output schema.
- **Expected outputs:** scoring job, feature definitions, validation contracts.
- **Validation:** reruns on same input produce identical scores.
- **Rollback / safe failure note:** freeze score updates and preserve previous
  published score set if determinism checks fail.
- **Completion criteria:** deterministic risk scores are generated and queryable.

#### Task IMP-12.2 - Backtesting and Hybrid Retrieval Orchestration

- **Why it exists:** verify risk usefulness and prepare evidence assembly for RCA.
- **Depends on:** `IMP-12.1`, `IMP-10.3`, `IMP-11.3`.
- **Reference links:** `TB-12`, `TR-08`, `FR-025`, `FR-026`.
- **Implementation targets:**
- `pipelines/risk/backtesting_job.py`
- `services/retrieval/hybrid_retrieval_orchestrator.py`
- `contracts/risk_rca/BACKTESTING_EVIDENCE_VALIDATION.json`
- `contracts/risk_rca/HYBRID_RETRIEVAL_EVIDENCE_BUNDLES_VALIDATION.json`
- **Execution details:**
- Run historical backtests and compute precision and recall trend artifacts.
- Implement hybrid retrieval orchestration combining vector and graph evidence.
- Emit evidence bundles with traceable source links and scores.
- Add contracts for backtesting artifact completeness and bundle integrity.
- **Expected outputs:** backtesting artifacts and hybrid retrieval service.
- **Validation:** backtest and evidence bundle contracts pass.
- **Rollback / safe failure note:** fallback to vector-only retrieval in RCA
  prep workflows if hybrid orchestration quality drops.
- **Completion criteria:** hybrid evidence bundle generation is reliable.

#### Task IMP-12.3 - Human Approval Controls and RCA Auditability

- **Why it exists:** ensure assisted RCA is controlled, explainable, and auditable.
- **Depends on:** `IMP-12.2`.
- **Reference links:** `TB-12`, `TR-09`, `TR-13`, `FR-026`, `NFR-005`.
- **Implementation targets:**
- `services/rca/approval_workflow.py`
- `gitops/platform/search/dashboards/saved-objects/RCA_AUDIT_OVERVIEW.ndjson`
- `contracts/risk_rca/HUMAN_APPROVAL_WORKFLOW_VALIDATION.json`
- `contracts/risk_rca/PILOT_GO_HOLD_DECISION_VALIDATION.json`
- **Execution details:**
- Implement explicit approval gate before publishing RCA suggestions.
- Log decision actor, timestamp, rationale, and evidence references.
- Add dashboard for RCA audit events and approval latency.
- Add pilot go or hold decision contract tied to governance review.
- **Expected outputs:** approval workflow and RCA audit artifacts.
- **Validation:** no RCA suggestion is released without approval evidence.
- **Rollback / safe failure note:** disable RCA publication path and retain score
  and evidence generation only if approval control fails.
- **Completion criteria:** RCA readiness gate passes with full audit traceability.

### Batch 13 - Core Adapter Integrations (`TB-13`)

Batch goal: complete core adapter integrations at the end of execution while
preserving core contract stability and cloud neutrality.

#### Task IMP-ADP.1 - Provider and Backend Adapter Contract

- **Why it exists:** keep cloud and backend integrations plug-and-play.
- **Depends on:** `IMP-02.2`, `IMP-03.2`, `IMP-08.1`, `IMP-09.1`.
- **Reference links:** `TB-13`, `TR-03`, `TR-09`, `FR-022`.
- **Implementation targets:**
- `install/profiles/adapters/ADAPTER_CONTRACT.schema.json`
- `adapters/providers/README.md`
- `adapters/storage/README.md`
- **Execution details:**
- Define adapter registration schema with prerequisites and fallback fields.
- Document non-goals and contract boundary against core platform.
- Tie adapter profile inputs to discovery outputs and generated overlays.
- Tie backend adapter requirements to OpenSearch template and ILM contracts.
- Add validation fixtures for supported and invalid adapter definitions.
- Add CI contract check for adapter definitions.
- **Expected outputs:** adapter contract schema and docs.
- **Validation:** adapter contract tests pass for all shipped adapters.
- **Rollback / safe failure note:** disable adapter profile and revert to core
  default module path when adapter validation fails.
- **Completion criteria:** adapters are integrated, discoverable, and
  contract-validated.

#### Task IMP-ADP.2 - Identity, Secrets, and Network Adapter Stubs

- **Why it exists:** provide extension points for non-default control planes.
- **Depends on:** `IMP-ADP.1`, `IMP-07.2`, `IMP-08.2`.
- **Reference links:** `TB-13`, `TR-09`, `TR-10`, `FR-022`.
- **Implementation targets:**
- `adapters/identity/`
- `adapters/secrets/`
- `adapters/network/`
- `docs/adapters/ADAPTER_ENABLEMENT_GUIDE.md`
- **Execution details:**
- Create adapter stub modules with required metadata and capability declarations.
- Add profile selection wiring for adapter activation.
- Tie identity and secrets adapters to onboarding metadata and policy checks.
- Tie network adapters to ingress and gateway assumptions from discovery logic.
- Add smoke tests ensuring adapter activation does not mutate core contracts.
- Document enable, validate, and disable lifecycle for each adapter class.
- **Expected outputs:** adapter stubs, docs, and smoke tests.
- **Validation:** adapter smoke tests pass and core tests remain unchanged.
- **Rollback / safe failure note:** adapter rollback uses profile disable plus
  cleanup script with no core module changes.
- **Completion criteria:** adapter modules are production-integrated and remain
  safely disable-able via profiles.

#### Task IMP-ADP.3 - CI/CD Adapter Neutrality Checks

- **Why it exists:** preserve Argo CD default while remaining CI/CD neutral.
- **Depends on:** `IMP-01.3`, `IMP-03.2`, `IMP-ADP.1`.
- **Reference links:** `TB-13`, `TR-10`, `FR-007`, `FR-022`.
- **Implementation targets:**
- `scripts/ci/validate_gitops_neutrality.sh`
- `contracts/adapters/CICD_ADAPTER_NEUTRALITY_VALIDATION.json`
- **Execution details:**
- Add check that core manifests do not require vendor-specific CI/CD fields.
- Add adapter-specific checks for optional CI/CD pathways.
- Add neutrality contract that verifies Argo CD remains reference default only.
- Tie CI/CD adapter checks to generated overlay and GitOps app paths.
- Add validation output used by release gate.
- **Expected outputs:** neutrality validation script and contract artifact.
- **Validation:** neutrality check passes with and without adapter modules enabled.
- **Rollback / safe failure note:** if neutrality check fails, block adapter merge
  and keep core delivery path unchanged.
- **Completion criteria:** CI/CD neutrality is continuously enforced.

## 8. Batch Completion Gate

A batch is complete only if all of the following are true:

- Every task completion criterion in the batch is satisfied.
- Required artifacts are committed in the declared target paths.
- Batch smoke script passes in CI and local execution path.
- Security and policy checks pass with no untracked exceptions.
- Runbooks and operator docs are updated for changed behavior.

## 9. Global Definition Of Done

- Platform behavior matches core constraints from `TECHNICAL.md`.
- All required contracts and schemas validate in CI.
- Guided install, discovery, and generated overlays are operational.
- Logs, metrics, traces, dashboards, and alerting are production-ready.
- Rollback, uninstall, backup, and restore paths are validated.
- Optional vector and graph modules are profile-gated and reversible.
- Assisted RCA readiness has explicit governance and audit controls.

## 10. Global Validation Gate

- Run foundation CI validation from `scripts/ci/`.
- Run batch smoke script for current batch.
- Run post-install readiness and telemetry smoke suite.
- Run security, policy, and secret scanning checks.
- Run contract validation for all changed `contracts/` artifacts.
- Attach evidence artifacts to release or promotion decision.

## 11. Global Rollback and Uninstall Gate

- Every batch change has a documented rollback command or GitOps revision path.
- Uninstall path is validated without orphaning critical resources.
- Restore drill evidence exists for batches changing storage behavior.
- Approval to promote requires passing rollback and uninstall drills.

## 12. Open Questions and Blocked Decisions

- Confirm long-term default for identity integration in core profile.
- Confirm retention defaults per environment tier for logs and traces.
- Confirm minimum support window for Kubernetes versions in matrix.
- Confirm managed versus self-managed policy for optional Neo4j in regulated zones.
- Confirm governance body and SLA for RCA approval workflow decisions.

## 13. Suggested First Execution Order

1. Execute Batch 1 through Batch 3 to stabilize install and discovery.
2. Execute Batch 4 through Batch 6 to establish telemetry core.
3. Execute Batch 7 through Batch 9 to harden onboarding and operations.
4. Execute Batch 10 through Batch 12 for vector, graph, and RCA readiness.
5. Execute Batch 13 (`TB-13`) after Batch 12 to finalize end-of-plan tie-ins
   for provider, identity, secrets, storage, network, and CI/CD integrations.
