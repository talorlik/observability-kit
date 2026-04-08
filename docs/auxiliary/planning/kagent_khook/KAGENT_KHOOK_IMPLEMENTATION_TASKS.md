# Kagent Khook Implementation Tasks

## Purpose

This document is the execution backlog for building the Kagent + Khook extension
as a cloud-agnostic, Kubernetes-native, open-source-first platform capability.
It converts planning intent into batch-by-batch implementation tasks that create
real repository artifacts.

## How To Use This Document

- Execute one batch at a time in numeric order.
- Start each task only after all listed dependencies are complete.
- Treat contract and governance tasks as hard gates for runtime implementation.
- Do not promote a batch unless all batch completion criteria pass.
- Keep core platform tasks separate from optional adapter extension tasks.

## Source-Of-Truth Hierarchy

1. `docs/auxiliary/AI_prompts/SYSTEM_INSTRUCTIONS_DOCS.md`
2. `docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK.plan.md`
3. `docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_PRD.md`
4. `docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_TECH.md`
5. `docs/auxiliary/planning/kagent_khook/KAGENT_KHOOK_TASKS.md`

## Implementation Principles

- Kubernetes is the platform boundary.
- AI-facing access is MCP-only through platform APIs.
- OpenTelemetry is the baseline collection path for AI control-plane telemetry.
- OpenSearch and OpenSearch Dashboards are default analytics and UI backends.
- Read-first rollout precedes approval-gated action rollout.
- Contracts, policy, and audit are release gates, not best-effort checks.
- Core runtime remains provider-neutral; adapters are optional extension work.

## Batch-To-Reference Mapping Table

| Implementation Batch Marker | Linked Task Batch Marker | Phase Alignment | Primary Contract Markers |
| ---- | ---- | ---- | ---- |
| `IKTB-01` Boundary and Contract Foundation | `KTB-01` | Phase 0 | `KK-C01` to `KK-C03` |
| `IKTB-02` Governance and Security Foundation | `KTB-02` | Phase 0 | `KK-C04` to `KK-C06` |
| `IKTB-03` Shared State and Envelope Foundation | `KTB-03` | Phase 0 | `KK-C07` to `KK-C09` |
| `IKTB-04` MCP Catalog and Contract Foundation | `KTB-04` | Phase 0 | `KK-C10` to `KK-C12` |
| `IKTB-05` Runtime Base Deployment | `KTB-05` | Phase 1 | `KK-C13` to `KK-C15` |
| `IKTB-06` Read-Only MCP Capability Layer | `KTB-06` | Phase 2 | `KK-C16` to `KK-C18` |
| `IKTB-07` Multi-Agent Orchestration Layer | `KTB-07` | Phase 3 | `KK-C19` to `KK-C21` |
| `IKTB-08` Khook Trigger and Reactive Triage Layer | `KTB-08` | Phase 4 | `KK-C22` to `KK-C24` |
| `IKTB-09` Approval-Gated Action Layer | `KTB-09` | Phase 5 | `KK-C25` to `KK-C27` |
| `IKTB-10` Productization and Release Readiness | `KTB-10` | Phase 6 | `KK-C28` to `KK-C30` |

## Agent Cross-Reference Navigation

Use this navigation to move across all three execution documents:

- `KAGENT_KHOOK_TASKS.md` provides sequencing and completion flow by `KTB-xx`.
- `KAGENT_KHOOK_TECH.md` provides contract details by `KK-Cxx`.
- `KAGENT_KHOOK_IMPLEMENTATION_TASKS.md` provides artifact-building execution by `IKTB-xx`.

Cross-reference workflow:

1. Start from the implementation batch marker (`IKTB-xx`) in this document.
2. Jump to the linked task batch marker (`KTB-xx`) in `KAGENT_KHOOK_TASKS.md`.
3. Validate all mapped technical contract markers (`KK-Cxx`) in `KAGENT_KHOOK_TECH.md`.
4. Close implementation work only when all three marker layers are satisfied.

## Repository Artifact Map

| Domain | Target Paths |
| ---- | ---- |
| Contracts and schemas | `contracts/ai/`, `contracts/mcp/`, `contracts/policy/` |
| Install and discovery | `install/discovery-engine/`, `install/profiles/` |
| GitOps runtime | `gitops/bootstrap/argocd/`, `gitops/platform/ai/` |
| MCP services | `services/mcp/incident-search/`, `services/mcp/graph-analysis/`, `services/mcp/trace-investigation/`, `services/mcp/metrics-correlation/`, `services/mcp/change-intelligence/`, `services/mcp/runbook-execution/`, `services/mcp/incident-casefile/` |
| Agent definitions | `agents/catalog/`, `agents/prompts/`, `agents/policies/` |
| Trigger layer | `triggers/khook/hooks/`, `triggers/khook/policies/` |
| Tests and CI | `tests/contracts/`, `tests/integration/`, `tests/safety/`, `tests/perf/`, `scripts/ci/` |
| Operations docs | `docs/runbooks/`, `docs/operations/` |
| Optional adapters | `adapters/providers/`, `adapters/identity/`, `adapters/secrets/`, `adapters/storage/`, `adapters/network/` |

## Implementation Batches

## Batch 1 - Boundary and Protocol Contracts [IKTB-01]

### Task IKTB-01-T01 - Define AI Runtime Boundary Contract
- Why it exists: enforce non-negotiable architecture path and prevent bypass.
- Depends on: none.
- Reference links: `KK-C01`, `KTB-01`, plan sections 2.2 and 5.1.
- Implementation targets: `contracts/ai/BOUNDARY_CONTRACT_V1.yaml`.
- Execution details:
  1. Define canonical runtime path and prohibited direct paths.
  2. Include allowed protocol edges for Khook, Kagent, gateway, MCP.
  3. Add schema version and compatibility notes.
- Expected outputs: versioned boundary contract.
- Validation: contract schema lint and CI check.
- Rollback / safe failure note: keep previous boundary version active until gates pass.
- Completion criteria: contract approved and referenced by CI.

### Task IKTB-01-T02 - Define Replaceability and Protocol Edge Contracts
- Why it exists: allow component swaps without behavior drift.
- Depends on: `IKTB-01-T01`.
- Reference links: `KK-C03`, `KTB-01`, plan sections 3.1 and 8.12.
- Implementation targets: `contracts/ai/REPLACEABILITY_MATRIX_V1.md`, `contracts/ai/PROTOCOL_EDGES_V1.yaml`.
- Execution details:
  1. Enumerate swappable components and fixed external behaviors.
  2. Define edge schemas for Khook-to-Kagent and agent-to-MCP paths.
  3. Add compatibility rules for contract evolution.
- Expected outputs: replaceability matrix and edge contract schemas.
- Validation: schema tests with sample payloads.
- Rollback / safe failure note: block merges for incompatible schema changes.
- Completion criteria: all protocol edges versioned and test-covered.

### Task IKTB-01-T03 - Enforce No Direct AI-to-Datastore Policy Gate
- Why it exists: guarantee MCP-mediated access posture.
- Depends on: `IKTB-01-T01`, `IKTB-01-T02`.
- Reference links: `KK-C02`, `KTB-01`, PRD section 13.
- Implementation targets: `contracts/policy/NO_DIRECT_DATASTORE_ACCESS.rego`, `scripts/ci/validate_ai_boundary_contracts.sh`.
- Execution details:
  1. Add deny policies for direct OpenSearch, Neo4j, and SQL clients.
  2. Add static scan checks for forbidden imports/endpoints.
  3. Integrate policy checks into CI script.
- Expected outputs: policy contracts and CI boundary gate.
- Validation: seeded negative tests fail as expected.
- Rollback / safe failure note: run in warning mode in dev, enforce in main branch.
- Completion criteria: CI blocks direct datastore access paths.

## Batch 2 - Security and Governance Contracts [IKTB-02]

### Task IKTB-02-T01 - Define Service Account and Namespace Access Matrix
- Why it exists: enforce least privilege by role and namespace.
- Depends on: Batch 1 complete.
- Reference links: `KK-C04`, `KTB-02`, PRD section 9.1.
- Implementation targets: `contracts/policy/IDENTITY_ACCESS_MATRIX_V1.yaml`, `gitops/platform/ai/policies/rbac/`.
- Execution details:
  1. Define service accounts per agent class and MCP service.
  2. Map allowed namespace and API/resource scopes.
  3. Add generated RBAC manifests from matrix.
- Expected outputs: identity matrix and RBAC policy set.
- Validation: policy tests for deny and allow scenarios.
- Rollback / safe failure note: preserve previous RBAC overlay for fallback.
- Completion criteria: matrix and manifests align with policy checks.

### Task IKTB-02-T02 - Implement Tool Risk Classification Contract
- Why it exists: gate tool usage by risk class and approval requirement.
- Depends on: `IKTB-02-T01`.
- Reference links: `KK-C05`, `KTB-02`, PRD section 9.2.
- Implementation targets: `contracts/policy/TOOL_RISK_CLASSIFICATION_V1.yaml`.
- Execution details:
  1. Classify tools into read and write classes.
  2. Define required approval and policy outcomes per class.
  3. Add mapping tests for complete tool coverage.
- Expected outputs: tool risk matrix.
- Validation: test ensures no tool is unclassified.
- Rollback / safe failure note: default unclassified tools to deny.
- Completion criteria: all cataloged tools mapped and tested.

### Task IKTB-02-T03 - Define Approval and Audit Contracts
- Why it exists: make write actions traceable and reversible.
- Depends on: `IKTB-02-T02`.
- Reference links: `KK-C05`, `KK-C06`, `KTB-02`, PRD sections 9.3 and 9.4.
- Implementation targets: `contracts/policy/APPROVAL_FLOW_V1.yaml`, `contracts/policy/AUDIT_EVENT_SCHEMA_V1.json`.
- Execution details:
  1. Define approval preconditions for `write.high-risk` and `write.critical`.
  2. Define mandatory audit fields and lineage identifiers.
  3. Add contract tests for rejected and approved action paths.
- Expected outputs: approval and audit schemas.
- Validation: schema validation and policy-driven path tests.
- Rollback / safe failure note: disable write-path execution when approval service fails.
- Completion criteria: approval and audit contracts enforced in CI.

## Batch 3 - Shared State and Inter-Agent Envelope [IKTB-03]

### Task IKTB-03-T01 - Implement Canonical Case-File Schema and Lifecycle
- Why it exists: persist workflow state independent of agent memory.
- Depends on: Batch 2 complete.
- Reference links: `KK-C07`, `KTB-03`, plan section 8.8.
- Implementation targets: `contracts/ai/CASEFILE_SCHEMA_V1.json`, `contracts/ai/CASEFILE_LIFECYCLE_V1.md`.
- Execution details:
  1. Define identity, status transitions, evidence, and action journal fields.
  2. Define resume-safe transitions and retention metadata.
  3. Provide sample create/update/resume/close fixtures.
- Expected outputs: case-file contract and fixtures.
- Validation: schema fixtures and state-machine checks.
- Rollback / safe failure note: preserve backward-compatible read support.
- Completion criteria: lifecycle checks pass for all fixture paths.

### Task IKTB-03-T02 - Implement Inter-Agent Envelope and Communication Policy
- Why it exists: standardize outputs and enforce bounded graph topology.
- Depends on: `IKTB-03-T01`.
- Reference links: `KK-C08`, `KK-C09`, `KTB-03`, plan sections 8.7 and 8.9.
- Implementation targets: `contracts/ai/AGENT_ENVELOPE_V1.json`, `contracts/ai/COMMUNICATION_GRAPH_V1.yaml`, `agents/policies/edge-policy.rego`.
- Execution details:
  1. Define shared envelope fields and required metadata.
  2. Define allowed edges and explicit deny defaults.
  3. Add policy tests for forbidden specialist-to-specialist calls.
- Expected outputs: envelope schema and graph policy.
- Validation: CI checks for schema conformance and edge enforcement.
- Rollback / safe failure note: fail closed on undefined edge.
- Completion criteria: agent outputs and communication edges validated in CI.

## Batch 4 - MCP Catalog and Tool Contracts [IKTB-04]

### Task IKTB-04-T01 - Build Versioned MCP Tool Catalog
- Why it exists: establish stable business-capability APIs for agents.
- Depends on: Batch 3 complete.
- Reference links: `KK-C10`, `KTB-04`, PRD section 8.6.
- Implementation targets: `contracts/mcp/MCP_CATALOG_V1.yaml`.
- Execution details:
  1. Register required MCP services and tool identifiers.
  2. Declare ownership, version, risk class, and tenancy scope.
  3. Link each tool to required response schema version.
- Expected outputs: versioned MCP catalog.
- Validation: catalog completeness checks against expected service list.
- Rollback / safe failure note: keep previous catalog version available.
- Completion criteria: catalog passes completeness and schema validation.

### Task IKTB-04-T02 - Define MCP Response, Tenancy, and Redaction Schemas
- Why it exists: ensure bounded, auditable, tenant-safe outputs.
- Depends on: `IKTB-04-T01`.
- Reference links: `KK-C11`, `KK-C12`, `KTB-04`, TECH section 4.
- Implementation targets: `contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json`, `contracts/mcp/TENANCY_REDACTION_RULES_V1.yaml`.
- Execution details:
  1. Define required fields (`summary`, `structured_data`, `evidence_handles`, and others).
  2. Define namespace/team scope and field-level redaction behavior.
  3. Add response-size and time-window ceilings.
- Expected outputs: response and redaction contracts.
- Validation: redaction and boundary tests with restricted fixtures.
- Rollback / safe failure note: default to redacted response on rule mismatch.
- Completion criteria: all catalog tools bind to validated schema.

## Batch 5 - Base Runtime and GitOps Scaffolding [IKTB-05]

### Task IKTB-05-T01 - Create Base GitOps Layout for AI Runtime
- Why it exists: establish declarative deployment structure by environment.
- Depends on: Batch 4 complete.
- Reference links: `KK-C13`, `KK-C15`, `KTB-05`, TECH section 7.3.
- Implementation targets: `gitops/platform/ai/base/`, `gitops/platform/ai/overlays/{quickstart,dev,staging,prod}/`.
- Execution details:
  1. Create base kustomization structure for kagent, khook, kmcp, gateway.
  2. Create environment overlays with explicit patch strategy.
  3. Add README for overlay purpose and promotion flow.
- Expected outputs: deployable base and overlay GitOps structure.
- Validation: `kustomize build` succeeds for all overlays.
- Rollback / safe failure note: use overlay pinning to revert environment rollout.
- Completion criteria: all overlays render without schema errors.

### Task IKTB-05-T02 - Scaffold Runtime Base Components
- Why it exists: deploy healthy control-plane baseline before service logic.
- Depends on: `IKTB-05-T01`.
- Reference links: `KK-C13`, `KK-C14`, `KTB-05`, PRD section 12.2.
- Implementation targets: `gitops/platform/ai/base/kagent/`, `gitops/platform/ai/base/khook/`, `gitops/platform/ai/base/kmcp/`, `gitops/platform/ai/base/gateway/`.
- Execution details:
  1. Add base manifests/charts and minimal runtime configs.
  2. Configure gatewayed MCP endpoint pattern with discovery controls.
  3. Add health probes, service monitors, and baseline resource limits.
- Expected outputs: healthy base runtime deployment specs.
- Validation: readiness and health checks pass in integration environment.
- Rollback / safe failure note: disable component via overlay patch if failing.
- Completion criteria: runtime components deploy and expose healthy status.

## Batch 6 - Read-Only MCP Services [IKTB-06]

### Task IKTB-06-T01 - Scaffold Read-Only MCP Service Implementations
- Why it exists: provide investigative capabilities with no write risk.
- Depends on: Batch 5 complete.
- Reference links: `KK-C16`, `KK-C17`, `KK-C18`, `KTB-06`, PRD section 12.3.
- Implementation targets: `services/mcp/incident-search/`, `services/mcp/graph-analysis/`, `services/mcp/trace-investigation/`, `services/mcp/metrics-correlation/`, `services/mcp/change-intelligence/`.
- Execution details:
  1. Scaffold service handlers with catalog-aligned tool signatures.
  2. Connect handlers to platform query APIs, not datastore clients.
  3. Add bounded retries, timeout budgets, and quota controls.
- Expected outputs: five read-only MCP service scaffolds.
- Validation: contract and integration tests via gateway.
- Rollback / safe failure note: disable specific tool registrations while keeping service up.
- Completion criteria: all services return schema-valid responses.

### Task IKTB-06-T02 - Implement Incident Case-File MCP Service
- Why it exists: allow managed read/write case-file access under contract.
- Depends on: `IKTB-06-T01`, `IKTB-03-T01`.
- Reference links: `KK-C07`, `KK-C16`, `KTB-06`, PRD section 8.2.
- Implementation targets: `services/mcp/incident-casefile/`.
- Execution details:
  1. Implement case create/read/update APIs with schema enforcement.
  2. Add audit and status transition constraints.
  3. Add restart-resume integration tests.
- Expected outputs: case-file MCP service with tested lifecycle behavior.
- Validation: state transition tests and audit field completeness checks.
- Rollback / safe failure note: preserve read-only mode if write path fails.
- Completion criteria: case-file operations pass contract and resilience tests.

## Batch 7 - Multi-Agent Topology and Prompt Controls [IKTB-07]

### Task IKTB-07-T01 - Implement Agent Catalog and Tool Bindings
- Why it exists: create bounded CEO-manager-specialist orchestration model.
- Depends on: Batch 6 complete.
- Reference links: `KK-C19`, `KK-C20`, `KK-C21`, `KTB-07`, plan section 8.
- Implementation targets: `agents/catalog/AGENT_CATALOG_V1.yaml`, `agents/policies/TOOL_BINDINGS_V1.yaml`.
- Execution details:
  1. Register CEO, manager, and specialist agents from PRD catalog.
  2. Bind allowed tools per role and deny all undefined tools.
  3. Enforce remediation executor preconditions.
- Expected outputs: agent catalog and tool-binding policies.
- Validation: policy tests for allowed/forbidden tool mounts.
- Rollback / safe failure note: fallback to read-only agent set.
- Completion criteria: all agent bindings comply with role policy.

### Task IKTB-07-T02 - Add Prompt Fragments and Orchestration Flow Tests
- Why it exists: codify role behavior and deterministic synthesis output.
- Depends on: `IKTB-07-T01`.
- Reference links: `KK-C20`, `KK-C21`, `KTB-07`, plan sections 8.13 and 8.14.
- Implementation targets: `agents/prompts/fragments/`, `tests/integration/agent_orchestration/`.
- Execution details:
  1. Create role prompt fragments with allowed/prohibited behaviors.
  2. Add contradiction and confidence rollup instructions.
  3. Implement one end-to-end read-only CEO synthesis test.
- Expected outputs: prompt fragment set and orchestration test suite.
- Validation: E2E flow asserts case-file persistence and evidence handles.
- Rollback / safe failure note: disable affected agent class on prompt regression.
- Completion criteria: orchestrated investigation flow passes with policy conformance.

## Batch 8 - Khook Triggered Investigation Flows [IKTB-08]

### Task IKTB-08-T01 - Implement Hook Catalog and Event Enrichment Pipeline
- Why it exists: enable reactive triage with controlled dispatch and dedupe.
- Depends on: Batch 7 complete.
- Reference links: `KK-C22`, `KK-C23`, `KK-C24`, `KTB-08`, PRD section 12.5.
- Implementation targets: `triggers/khook/hooks/HOOK_CATALOG_V1.yaml`, `triggers/khook/policies/EVENT_ENRICHMENT_V1.yaml`.
- Execution details:
  1. Define initial hooks (`pod-restart`, `oom-kill`, `probe-failed`, and others).
  2. Add enrichment fields and stable correlation keys.
  3. Add dedupe and burst-control policy logic.
- Expected outputs: hook catalog and enrichment policy set.
- Validation: functional tests for dedupe and event qualification.
- Rollback / safe failure note: switch hooks to observe-only mode on instability.
- Completion criteria: triggers produce schema-valid enriched payloads.

### Task IKTB-08-T02 - Wire Khook to Read-Only Agent Dispatch and Case Attachments
- Why it exists: complete event-to-summary path without write-path risk.
- Depends on: `IKTB-08-T01`, `IKTB-07-T02`.
- Reference links: `KK-C22`, `KTB-08`, PRD section 10.2.
- Implementation targets: `triggers/khook/dispatch/`, `tests/integration/khook_event_flows/`.
- Execution details:
  1. Restrict dispatch targets to read-only investigation agents.
  2. Persist outputs to case file and operator channels.
  3. Add burst-load resilience tests.
- Expected outputs: event-driven investigation flow implementation.
- Validation: trigger-to-summary integration tests pass.
- Rollback / safe failure note: disable dispatch for noisy hook classes.
- Completion criteria: event flow works under normal and burst scenarios.

## Batch 9 - Approval-Gated Action Plane [IKTB-09]

### Task IKTB-09-T01 - Implement Runbook Execution MCP with Approval Preconditions
- Why it exists: add bounded write path with policy and approval controls.
- Depends on: Batch 8 complete.
- Reference links: `KK-C25`, `KK-C26`, `KK-C27`, `KTB-09`, PRD section 12.6.
- Implementation targets: `services/mcp/runbook-execution/`, `contracts/policy/ACTION_PRECONDITIONS_V1.yaml`.
- Execution details:
  1. Implement runbook execution tools with strict input schemas.
  2. Enforce approval, policy pass, target validation, and rollback plan checks.
  3. Add deterministic rejected-action behavior.
- Expected outputs: gated action MCP service and precondition policy contract.
- Validation: high-risk actions fail without approval; pass with required state.
- Rollback / safe failure note: force policy deny when approval service unavailable.
- Completion criteria: action path adheres to all governance contracts.

### Task IKTB-09-T02 - Implement Action Journal and Rollback Workflows
- Why it exists: preserve auditability and safe recovery for all write actions.
- Depends on: `IKTB-09-T01`.
- Reference links: `KK-C26`, `KK-C27`, `KTB-09`, PRD section 9.4.
- Implementation targets: `services/mcp/runbook-execution/journal/`, `docs/runbooks/AI_ACTION_ROLLBACK_RUNBOOK.md`, `tests/safety/action_gates/`.
- Execution details:
  1. Persist action attempt, approval, policy decision, and result entries.
  2. Implement rollback workflow hooks with deterministic state transitions.
  3. Add tests for rejected and rollback branches.
- Expected outputs: action journal and rollback implementation plus runbook.
- Validation: audit completeness and rollback test suite pass.
- Rollback / safe failure note: block further actions if journaling sink fails.
- Completion criteria: every write attempt has complete auditable lineage.

## Batch 10 - Productization and Release Gates [IKTB-10]

### Task IKTB-10-T01 - Implement Guided Install Discovery and Overlay Generation
- Why it exists: make deployment repeatable across install modes.
- Depends on: Batch 9 complete.
- Reference links: `KK-C28`, `KK-C29`, `KTB-10`, PRD section 12.7.
- Implementation targets: `install/discovery-engine/`, `install/profiles/ai-runtime/`, `install/profiles/adapters/`.
- Execution details:
  1. Implement preflight and capability detection checks.
  2. Generate deterministic overlays for quickstart, attach, standalone, hybrid.
  3. Emit compatibility and remediation reports.
- Expected outputs: discovery engine and generated overlay pipeline.
- Validation: mode recommendation and overlay generation tests pass.
- Rollback / safe failure note: keep manual overlay selection fallback path.
- Completion criteria: install profile generation succeeds across supported modes.

### Task IKTB-10-T02 - Final Validation Gates, Runbooks, and Release Checklist
- Why it exists: enforce production-readiness before activation.
- Depends on: `IKTB-10-T01`.
- Reference links: `KK-C30`, `KTB-10`, PRD sections 14 and 17.
- Implementation targets: `tests/perf/ai_runtime/`, `tests/safety/`, `scripts/ci/validate_kagent_khook_release.sh`, `docs/runbooks/CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md`.
- Execution details:
  1. Add functional, safety, performance, and upgrade test bundles.
  2. Add release CI script that aggregates all mandatory gates.
  3. Publish operator runbooks for install, approvals, rollback, uninstall.
- Expected outputs: release gate automation and operator readiness docs.
- Validation: release script passes in staging with full evidence output.
- Rollback / safe failure note: release blocked unless all gates are green.
- Completion criteria: release checklist is fully satisfiable and reproducible.

## Optional Adapter Extension Batches

Adapter tasks are optional and must not block core `IKTB-01` through `IKTB-10`.

- `IKAD-01` Provider event-source adapters under `adapters/providers/`.
- `IKAD-02` Identity backend adapters under `adapters/identity/`.
- `IKAD-03` Secrets backend adapters under `adapters/secrets/`.
- `IKAD-04` Storage backend adapters under `adapters/storage/`.
- `IKAD-05` Network and ingress adapters under `adapters/network/`.
- `IKAD-06` CI/CD adapter templates under `adapters/cicd/`.

Each adapter batch must include:
- compatibility contract,
- bounded integration tests,
- rollback/uninstall notes,
- explicit statement that core contracts remain unchanged.

## Batch Completion Gate

A batch is complete only when all are true:

- all tasks in the batch meet completion criteria;
- contract tests pass for every changed schema or policy;
- governance and audit checks pass for changed flows;
- related runbooks are updated;
- CI gates for the batch are green.

## Global Definition Of Done

- All required core batches (`IKTB-01` to `IKTB-10`) are complete.
- No direct AI-to-datastore path exists in shipped artifacts.
- Required MCP catalog and agent catalog are versioned and validated.
- Read-only and approval-gated flows pass acceptance tests.
- Install, rollback, and uninstall procedures are documented and tested.

## Global Validation Gate

- Functional: human query, event-driven triage, action proposal/execution flows.
- Safety: approval enforcement, policy denial, redaction, prompt-injection handling.
- Multi-agent: bounded communication graph and contradiction handling.
- Performance: burst behavior, concurrency, gateway and MCP latency SLO checks.
- Upgrade: contract compatibility across Kagent, Khook, kmcp, gateway, and MCP schemas.

## Global Rollback And Uninstall Gate

- Every write-path task has explicit rollback preconditions.
- Rollback automation and manual fallback steps are documented.
- Uninstall path preserves required audit records and case-file integrity.
- Failed release candidate can be reverted to previous known-good overlay.

## Open Questions And Blocked Decisions

- Which gateway implementation is the default production reference.
- Final policy engine choice for approval and risk enforcement profile.
- External PostgreSQL deployment ownership model per environment.
- Exact SLO targets for event-to-summary and action-gate latencies.
- Minimum supported Kubernetes distribution/version matrix for initial release.

## Suggested First Execution Order

1. `IKTB-01` through `IKTB-04` to lock contracts and governance.
2. `IKTB-05` through `IKTB-06` to stand up runtime and read-only MCP path.
3. `IKTB-07` through `IKTB-08` to enable controlled orchestration and reactive triage.
4. `IKTB-09` for approval-gated action plane.
5. `IKTB-10` for discovery-led productization and final release readiness.
