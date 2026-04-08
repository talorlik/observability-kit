# Kagent Khook Incremental Tasks

This backlog is aligned with `KAGENT_KHOOK_PRD.md`,
`KAGENT_KHOOK_TECH.md`, and `KAGENT_KHOOK.plan.md`.
It is contract-first, cloud agnostic, Kubernetes-native, and open-source-first.
All tasks are incremental and sized small to medium.

## How To Use This Backlog

- Execute batches in order.
- Run one batch at a time (`do batch 1`, `do batch 2`, and so on).
- Start a task only after its dependencies are complete.
- Close a task only when its completion check passes.
- Treat every contract task as a hard gate for downstream implementation tasks.

## Contract-First Delivery Markers

Use these markers to keep sequencing and validation explicit.

| Batch | Primary Marker Coverage |
| ---- | ---- |
| Batch 1 | `KK-C01`, `KK-C02`, `KK-C03` |
| Batch 2 | `KK-C04`, `KK-C05`, `KK-C06` |
| Batch 3 | `KK-C07`, `KK-C08`, `KK-C09` |
| Batch 4 | `KK-C10`, `KK-C11`, `KK-C12` |
| Batch 5 | `KK-C13`, `KK-C14`, `KK-C15` |
| Batch 6 | `KK-C16`, `KK-C17`, `KK-C18` |
| Batch 7 | `KK-C19`, `KK-C20`, `KK-C21` |
| Batch 8 | `KK-C22`, `KK-C23`, `KK-C24` |
| Batch 9 | `KK-C25`, `KK-C26`, `KK-C27` |
| Batch 10 | `KK-C28`, `KK-C29`, `KK-C30` |

## Agent Cross-Reference Index

Use this index first when actioning tasks so contract dependencies are always
resolved before runtime implementation.

| Task Batch Marker | Batch | Contract Focus | Technical Marker Range | Implementation Batch Marker |
| ---- | ---- | ---- | ---- | ---- |
| `KTB-01` | Batch 1 - Boundary Contracts | boundary, replaceability, protocol edges | `KK-C01` to `KK-C03` | `IKTB-01` |
| `KTB-02` | Batch 2 - Governance Contracts | identity, risk, approval, audit | `KK-C04` to `KK-C06` | `IKTB-02` |
| `KTB-03` | Batch 3 - State Contracts | case file and inter-agent envelope | `KK-C07` to `KK-C09` | `IKTB-03` |
| `KTB-04` | Batch 4 - MCP Contracts | MCP service and tool contracts | `KK-C10` to `KK-C12` | `IKTB-04` |
| `KTB-05` | Batch 5 - Runtime Base | Kagent, Khook, kmcp, gateway base | `KK-C13` to `KK-C15` | `IKTB-05` |
| `KTB-06` | Batch 6 - Read MCP | incident, graph, trace, metrics, change | `KK-C16` to `KK-C18` | `IKTB-06` |
| `KTB-07` | Batch 7 - Agent Topology | CEO, manager, specialist, policy | `KK-C19` to `KK-C21` | `IKTB-07` |
| `KTB-08` | Batch 8 - Trigger Flows | hooks, enrichment, dedupe, dispatch | `KK-C22` to `KK-C24` | `IKTB-08` |
| `KTB-09` | Batch 9 - Gated Actions | runbook execution and write governance | `KK-C25` to `KK-C27` | `IKTB-09` |
| `KTB-10` | Batch 10 - Release Prep | install modes, compatibility, gates | `KK-C28` to `KK-C30` | `IKTB-10` |

Cross-reference usage:

- Start in `KAGENT_KHOOK_TASKS.md` at a `KTB-xx` batch marker.
- Use the Technical Marker Range to jump to `KAGENT_KHOOK_TECH.md`.
- Use the Implementation Batch Marker to jump to
  `KAGENT_KHOOK_IMPLEMENTATION_TASKS.md`.
- Match detailed section markers in the tech doc to implement and validate.
- Do not close a task unless its mapped `KK-Cxx` and `IKTB-xx` markers are
  satisfied.

## Batch 1 - Boundary and Protocol Contracts [KTB-01 | KK-C01, KK-C02, KK-C03]

Goal: lock non-negotiable boundaries before any runtime deployment.

1. Define architecture boundary contract:
   `Khook -> Kagent -> gatewayed MCP -> platform APIs -> backends`.
   - Dependencies: none.
   - Completion check: architecture contract document is versioned and approved.
2. Define "no direct AI-to-datastore access" policy contract and deny rules.
   - Dependencies: Task 1.
   - Completion check: static policy checks detect and fail direct datastore paths.
3. Define replaceability contract for Kagent, Khook, gateway, and MCP services.
   - Dependencies: Task 1.
   - Completion check: swap matrix lists required external contracts per component.
4. Define protocol edge contracts for Khook-to-Kagent, agent-to-agent, and
   agent-to-MCP paths.
   - Dependencies: Tasks 1-3.
   - Completion check: all protocol edges have versioned schema definitions.
5. Define namespace segmentation and cross-namespace allow-list contract.
   - Dependencies: Task 4.
   - Completion check: namespace boundary and `allowedNamespaces` rules are
     documented and testable.
6. Add CI contract gate bundle for Tasks 1-5.
   - Dependencies: Tasks 1-5.
   - Completion check: CI blocks merges when boundary or protocol contracts break.

## Batch 2 - Security and Governance Contracts [KTB-02 | KK-C04, KK-C05, KK-C06]

Goal: codify safety and governance constraints before attaching write paths.

1. Define per-agent and per-MCP service account contract.
   - Dependencies: Batch 1.
   - Completion check: identity matrix exists for every planned runtime component.
2. Define tool risk classification contract:
   `read.safe`, `read.sensitive`, `write.low-risk`, `write.high-risk`,
   `write.critical`.
   - Dependencies: Task 1.
   - Completion check: all planned tools are mapped to one risk class.
3. Define approval policy contract and required preconditions for write paths.
   - Dependencies: Task 2.
   - Completion check: `write.high-risk` and `write.critical` approvals are
     explicitly codified.
4. Define policy engine decision contract for allow, deny, and conditional paths.
   - Dependencies: Tasks 2-3.
   - Completion check: policy responses are schema-defined and consumed by agents.
5. Define audit contract for actor, tool call, evidence handle, policy decision,
   approval decision, and action result.
   - Dependencies: Tasks 1-4.
   - Completion check: required audit fields are validated by contract tests.
6. Add CI governance gate for identity, policy, approval, and audit contracts.
   - Dependencies: Tasks 1-5.
   - Completion check: CI fails when governance schema or mappings are incomplete.

## Batch 3 - Shared State and Envelope Contracts [KTB-03 | KK-C07, KK-C08, KK-C09]

Goal: standardize inter-agent state and message shape before agent rollout.

1. Define incident case-file canonical schema and lifecycle states.
   - Dependencies: Batches 1-2.
   - Completion check: schema validates sample create, update, resume, and close
     workflows.
2. Define inter-agent envelope schema for objective, findings, evidence, risk, and
   confidence.
   - Dependencies: Task 1.
   - Completion check: all planned agents can produce and consume the envelope.
3. Define contradiction-handling and confidence rollup contract.
   - Dependencies: Task 2.
   - Completion check: conflict examples resolve through deterministic rules.
4. Define case-file retention and replay contract for restart-safe workflow
   resumption.
   - Dependencies: Task 1.
   - Completion check: restart simulation resumes from persisted case-file state.
5. Define allowed communication graph contract:
   `CEO -> manager -> specialist`, with explicit exceptions.
   - Dependencies: Tasks 2-4.
   - Completion check: unauthorized communication edges are denied in policy tests.
6. Add CI schema gate for case file, envelope, and communication graph contracts.
   - Dependencies: Tasks 1-5.
   - Completion check: CI blocks non-conforming agent interface changes.

## Batch 4 - MCP Catalog and Tool Contracts [KTB-04 | KK-C10, KK-C11, KK-C12]

Goal: define stable MCP interfaces before implementing runtime services.

1. Define versioned MCP catalog contract for:
   `incident-search`, `graph-analysis`, `trace-investigation`,
   `metrics-correlation`, `change-intelligence`, `runbook-execution`,
   `incident-casefile`.
   - Dependencies: Batches 1-3.
   - Completion check: catalog includes tool names, versions, and ownership.
2. Define common MCP response contract:
   `summary`, `structured_data`, `evidence_handles`, `confidence`, `time_window`,
   `safety_class`, `next_recommended_tools`.
   - Dependencies: Task 1.
   - Completion check: schema tests pass for every cataloged tool.
3. Define tenancy, redaction, and query-boundary contracts for MCP responses.
   - Dependencies: Task 2.
   - Completion check: simulated restricted-field requests return compliant outputs.
4. Define gateway registration and discovery contract for kmcp-managed services.
   - Dependencies: Task 1.
   - Completion check: contract enforces disabled direct discovery for
     gateway-fronted services.
5. Define backward compatibility and semantic versioning policy for MCP tools.
   - Dependencies: Tasks 1-4.
   - Completion check: breaking changes require new version in contract checks.
6. Add CI MCP contract gate for schema, tenancy, redaction, and versioning.
   - Dependencies: Tasks 1-5.
   - Completion check: CI fails on contract drift or breaking changes.

## Batch 5 - Base Control Plane Scaffolding [KTB-05 | KK-C13, KK-C14, KK-C15]

Goal: stand up runtime base that implements approved contracts without
business-specific behavior.

1. Provision external PostgreSQL and Kagent minimal profile scaffold.
   - Dependencies: Batch 4.
   - Completion check: Kagent control plane health checks and storage connectivity
     pass.
2. Deploy kmcp and MCP CRD lifecycle scaffold.
   - Dependencies: Task 1.
   - Completion check: kmcp controller is healthy and MCP CRDs reconcile.
3. Deploy Khook controller scaffold in isolated trigger namespace.
   - Dependencies: Task 1.
   - Completion check: Khook controller health and watch loop readiness pass.
4. Deploy MCP/A2A gateway scaffold and baseline routing policy.
   - Dependencies: Tasks 1-2.
   - Completion check: gateway endpoint is reachable with policy controls enabled.
5. Configure OpenTelemetry instrumentation and baseline runtime telemetry for AI
   control plane.
   - Dependencies: Tasks 1-4.
   - Completion check: traces and metrics are visible for Kagent, Khook, kmcp, and
     gateway.
6. Add GitOps scaffolding for base and overlays (`quickstart`, `dev`, `staging`,
   `prod`).
   - Dependencies: Tasks 1-5.
   - Completion check: overlays render and sync without contract violations.

## Batch 6 - Read-Only MCP Service Scaffolding [KTB-06 | KK-C16, KK-C17, KK-C18]

Goal: implement governed read-path MCP services on stable contracts.

1. Scaffold `incident-search-mcp` with versioned read-only tools.
   - Dependencies: Batch 5.
   - Completion check: tool calls return schema-valid results via gateway.
2. Scaffold `graph-analysis-mcp` with bounded graph traversal tools.
   - Dependencies: Task 1.
   - Completion check: blast radius and dependency queries pass contract tests.
3. Scaffold `trace-investigation-mcp` and `metrics-correlation-mcp`.
   - Dependencies: Task 1.
   - Completion check: trace and metrics tools satisfy response and redaction
     contracts.
4. Scaffold `change-intelligence-mcp` with rollout and config-change lookups.
   - Dependencies: Task 1.
   - Completion check: change correlation responses are schema-valid and scoped.
5. Scaffold `incident-casefile-mcp` for case file read and write contract access.
   - Dependencies: Batch 3.
   - Completion check: agents can persist and retrieve case-file state by contract.
6. Add CI smoke and contract suite for all read-only MCP services.
   - Dependencies: Tasks 1-5.
   - Completion check: full MCP read-path suite passes with gateway-only access.

## Batch 7 - Multi-Agent Scaffolding [KTB-07 | KK-C19, KK-C20, KK-C21]

Goal: scaffold CEO-led multi-agent topology with strict tool and communication
controls.

1. Scaffold CEO and manager agents:
   `ops-ceo-agent`, `triage-director`, `investigation-manager`, `action-governor`.
   - Dependencies: Batch 6.
   - Completion check: manager invocation policy aligns to communication graph
     contract.
2. Scaffold investigation specialist agents:
   `incident-investigator`, `logs-analyst`, `trace-analyst`,
   `metrics-correlator`, `graph-analyst`, `change-correlator`,
   `evidence-summarizer`.
   - Dependencies: Task 1.
   - Completion check: each specialist has only approved read-path tool bindings.
3. Scaffold action specialists:
   `runbook-planner`, `remediation-executor`.
   - Dependencies: Task 1.
   - Completion check: remediation executor is blocked without approval state.
4. Apply prompt-fragment scaffolding for role, allowed tools, prohibited actions,
   case-file behavior, and escalation rules.
   - Dependencies: Tasks 1-3.
   - Completion check: all agent prompts include required contract fragments.
5. Validate one end-to-end read-only orchestration flow through CEO synthesis.
   - Dependencies: Tasks 1-4.
   - Completion check: final synthesis is generated by CEO with evidence handles.
6. Add CI policy checks for forbidden tool mounts and forbidden agent edges.
   - Dependencies: Tasks 1-5.
   - Completion check: CI rejects non-compliant agent topology changes.

## Batch 8 - Khook Trigger Scaffolding [KTB-08 | KK-C22, KK-C23, KK-C24]

Goal: scaffold event-driven investigation workflows with controlled dispatch.

1. Define and scaffold initial Hook set for:
   `pod-restart`, `oom-kill`, `probe-failed`, `pod-pending`, `node-not-ready`.
   - Dependencies: Batch 7.
   - Completion check: hooks deploy with schema-valid event definitions.
2. Add event enrichment scaffold for namespace, owner, criticality, rollout marker,
   and incident correlation key.
   - Dependencies: Task 1.
   - Completion check: enriched payloads include required fields for downstream
     agents.
3. Add deduplication and burst-control scaffold for repeated event storms.
   - Dependencies: Tasks 1-2.
   - Completion check: noisy repeated events do not generate duplicate
     investigations.
4. Restrict Khook dispatch to read-only agents for initial rollout.
   - Dependencies: Tasks 1-3.
   - Completion check: write-path agents are unreachable from hooks in this phase.
5. Attach event-driven outputs to incident case file and operator channels.
   - Dependencies: Tasks 2-4.
   - Completion check: each trigger flow persists summary and evidence references.
6. Add Khook functional and resilience smoke suite.
   - Dependencies: Tasks 1-5.
   - Completion check: trigger-to-summary flow passes under normal and burst loads.

## Batch 9 - Approval-Gated Action Scaffolding [KTB-09 | KK-C25, KK-C26, KK-C27]

Goal: add bounded action path behind policy and approval gates.

1. Scaffold `runbook-execution-mcp` with bounded write-path tool catalog.
   - Dependencies: Batch 8.
   - Completion check: write tools are available only by risk-class policy.
2. Wire policy engine and approval service integration for action invocation.
   - Dependencies: Task 1.
   - Completion check: policy deny and approval required states are enforced.
3. Enforce remediation executor preconditions:
   approved plan, valid target, policy pass, rollback plan present.
   - Dependencies: Tasks 1-2.
   - Completion check: action execution is blocked when any precondition is missing.
4. Add action journaling and evidence capture contract for all write flows.
   - Dependencies: Tasks 1-3.
   - Completion check: post-action records include mandatory audit fields.
5. Add rejected-action and rollback workflow scaffolding.
   - Dependencies: Tasks 1-4.
   - Completion check: rejected and rollback paths are deterministic and auditable.
6. Add CI and staging action-gate test suite.
   - Dependencies: Tasks 1-5.
   - Completion check: high-risk actions cannot execute without explicit approval.

## Batch 10 - Productization and Release Scaffolding [KTB-10 | KK-C28, KK-C29, KK-C30]

Goal: package extension for repeatable delivery and release readiness.

1. Scaffold install mode contracts for `quickstart`, `attach`, `standalone`,
   and `hybrid`.
   - Dependencies: Batch 9.
   - Completion check: mode contract inputs and outputs are schema-documented.
2. Scaffold capability discovery and generated overlay templates per mode.
   - Dependencies: Task 1.
   - Completion check: discovery outputs map deterministically to overlay choices.
3. Scaffold compatibility matrix for Kubernetes version and distribution support.
   - Dependencies: Tasks 1-2.
   - Completion check: supported, conditional, and blocked states are defined.
4. Scaffold smoke, safety, performance, and upgrade validation suites.
   - Dependencies: Tasks 1-3.
   - Completion check: release suite covers functional, multi-agent, safety, and
     upgrade paths.
5. Publish operator runbooks for install, validation, approval flow, rollback, and
   uninstall.
   - Dependencies: Tasks 1-4.
   - Completion check: runbooks are complete and linked in platform docs.
6. Define final release gate checklist and sign-off workflow for production
   activation.
   - Dependencies: Tasks 1-5.
   - Completion check: release gate requires all batch completion checks to pass.

## Batch Completion Gate

Before moving to the next batch:

- All completion checks in the current batch pass.
- Contract tests for changed interfaces pass.
- Governance, security, and audit checks pass.
- New or changed runbooks are updated.
- Outstanding risks are documented with owners and due dates.
