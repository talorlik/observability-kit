# Kagent Khook Product Requirements Document

This PRD defines product requirements to implement the Kagent + Khook
extension as a decoupled AI and automation layer for the observability
platform.

## 1. Purpose And Desired Outcome

The platform must gain:

- AI-assisted incident triage and investigation
- Event-driven investigation triggers
- Governed, approval-aware remediation execution
- A reusable, cloud-agnostic, Kubernetes-native extension model

The implementation must preserve replaceability and avoid direct
AI-to-datastore coupling.

## 2. Problem Statement

The current platform has strong telemetry and analytics components, but
requires a controlled reasoning and automation layer that can:

- turn incident context into coordinated investigations
- correlate logs, traces, metrics, graph, and change signals
- escalate to bounded actions with policy and approval controls
- remain portable across deployments and future runtime replacements

## 3. Goals

- Deliver a production-capable Kagent and Khook control plane.
- Expose observability capabilities through governed MCP contracts.
- Implement a CEO-led multi-agent operating model with bounded roles.
- Enable reactive investigation from Kubernetes events.
- Introduce action execution only behind policy and approval gates.
- Package the extension for repeatable productized installation.

## 4. Non-Goals

- Khook as a reasoning or remediation engine.
- Direct agent access to OpenSearch, Neo4j, PostgreSQL, or any datastore.
- Autonomous high-risk remediation in initial releases.
- Raw database query tools exposed as MCP interfaces.
- A gateway replacing Kagent or the observability platform.

## 5. Product Principles

- Replaceability by contract at every layer.
- MCP-first integration for all AI-facing capabilities.
- Query services before data stores.
- Read-first, act-later progressive rollout.
- Security, governance, and auditability by default.

## 6. Stakeholders And Users

- Platform engineering
- SRE and incident response teams
- Security and governance teams
- Service owners and on-call operators

## 7. Scope

### 7.1 In Scope

- Kagent deployment in minimal profile with external PostgreSQL.
- Khook deployment for trigger, qualification, and dispatch.
- kmcp lifecycle management for platform-owned MCP services.
- Gatewayed MCP and A2A access for policy, routing, and audit.
- Read-only and action MCP service catalogs.
- Multi-agent topology with CEO, manager, and specialist tiers.
- Shared case-file model and incident case-file MCP boundary.
- Validation suites for functional, safety, performance, and upgrades.
- Productization assets for install, attach, hybrid, and standalone modes.

### 7.2 Out Of Scope

- Replacing existing observability data planes.
- Bypassing platform APIs with datastore-native clients.
- Unbounded tool access by any single agent.

## 8. System Requirements

### 8.1 Architecture Requirements

- The runtime architecture must follow:
  `Khook -> Kagent -> gatewayed MCP catalog -> platform query/action APIs
  -> backends`.
- Kagent and Khook must remain pluggable modules.
- Datastore access must remain behind platform-owned service contracts.
- Gateway-fronted MCP services must disable direct discovery where required.

### 8.2 Component Requirements

The implementation must include:

- Kagent
- Khook
- kmcp
- gateway or internal MCP/A2A proxy with governance controls
- incident-casefile-mcp
- read-only MCP services:
  - incident-search-mcp
  - graph-analysis-mcp
  - trace-investigation-mcp
  - metrics-correlation-mcp
  - change-intelligence-mcp
- action MCP service:
  - runbook-execution-mcp

### 8.3 Agent Model Requirements

The implementation must include:

- `ops-ceo-agent`
- manager agents:
  - `triage-director`
  - `investigation-manager`
  - `action-governor`
- specialist agents:
  - `incident-investigator`
  - `logs-analyst`
  - `trace-analyst`
  - `metrics-correlator`
  - `graph-analyst`
  - `change-correlator`
  - `evidence-summarizer`
  - `runbook-planner`
  - `remediation-executor`

The CEO agent must produce the final synthesis and orchestrate all major
flows.

### 8.4 Inter-Agent Contract Requirements

- All agent outputs must use a standard envelope containing:
  - objective
  - findings
  - evidence handles
  - assumptions
  - confidence
  - risk level
  - recommended next action
- A platform-owned case file must persist workflow state and evidence links.
- Only approved agent communication edges are allowed.
- Specialist-to-specialist communication is denied unless explicitly allowed.

### 8.5 Khook Requirements

- Khook must support event qualification, enrichment, deduplication, and
  dispatch.
- Phase 1 hooks must be investigation-only.
- Hooks must be scoped by domain or risk class.
- Event-driven outputs must attach to incident records or configured channels.

### 8.6 MCP Tool Contract Requirements

- MCP tools must expose business-level intents, not raw datastore queries.
- Contracts must be versioned and schema-stable.
- Responses must be structured, concise, and auditable.
- Tenant controls and redaction must be enforced before response return.

## 9. Security And Governance Requirements

### 9.1 Identity And Access

- Each agent must use a dedicated service account.
- Least-privilege RBAC and NetworkPolicies are mandatory.
- Cross-namespace access must use explicit `allowedNamespaces`.

### 9.2 Tool Risk Classes

Tool classes must include:

- `read` for investigation-only access
- `write.low-risk` for bounded operational writes
- `write.high-risk` for impactful infrastructure actions

### 9.3 Approval And Policy

- High-risk actions must always require approval.
- Action execution must require policy pass before invocation.
- The remediation executor must not run without approval state.
- Every action class must include rollback instructions.

### 9.4 Auditability

- All tool calls, decisions, and approvals must be logged.
- Audit logs must preserve actor, timestamp, request, response summary, and
  policy result.
- Proxy-mediated routing must preserve end-to-end traceability.

## 10. Functional Requirements

### 10.1 Human Query Flows

The system must support:

- incident summarization
- blast radius analysis
- recent change correlation

### 10.2 Event-Driven Flows

The system must support:

- event trigger to agent investigation
- burst deduplication for noisy repeated events
- event-to-summary attachment in incident workflow

### 10.3 Action Flows

The system must support:

- remediation proposal generation
- approval-gated action execution
- deterministic behavior for rejected actions

## 11. Non-Functional Requirements

### 11.1 Reliability

- Core control plane components must be health-checkable and observable.
- Workflow execution must resume from case-file state after agent restarts.

### 11.2 Performance

- The platform must handle concurrent investigations.
- Khook must handle restart burst scenarios with bounded duplication.
- Gateway and MCP fan-out behavior must remain within defined latency budgets.

### 11.3 Cost And Efficiency

- Token and cost budgets must be enforceable per namespace or team.
- Result schemas must remain compact and purpose-scoped.

### 11.4 Maintainability

- Upgrades to Kagent, Khook, kmcp, and gateway must preserve contract
  compatibility.
- Backend schema evolution must remain hidden behind platform query APIs.

## 12. Phased Delivery Requirements

### 12.1 Phase 0 - Architecture Hardening

Required outputs:

- interface contracts for query APIs
- MCP tool catalog v1
- agent catalog v1
- trigger catalog v1
- security classification matrix
- approval policy matrix

Release gate:

- no design path permits direct AI-to-datastore access.

### 12.2 Phase 1 - Base AI Control Plane

Required outputs:

- Kagent minimal profile with external PostgreSQL
- kmcp, Khook, and gateway deployment
- OpenTelemetry instrumentation for AI layer
- GitOps-managed CRDs and releases

Release gate:

- control plane healthy, traced, reachable, and free of demo agents in
  production.

### 12.3 Phase 2 - Read-Only MCP Capability Layer

Required outputs:

- five read-only MCP services deployed via kmcp
- gateway registrations and Kagent `RemoteMCPServer` references
- discovery disabled for gateway-fronted MCP services where required

Release gate:

- all read-only MCP tools callable through gateway with stable schemas.

### 12.4 Phase 3 - Multi-Agent Mesh And CEO Orchestration

Required outputs:

- CEO, manager, and specialist agents configured
- case-file schema and incident-casefile-mcp implemented
- communication graph and prompt skill fragments finalized
- contradiction handling and confidence rules enforced

Release gate:

- at least one end-to-end investigation flow is fully orchestrated by CEO.

### 12.5 Phase 4 - Reactive Triage With Khook

Required outputs:

- initial hook resources and labeling strategy
- event enrichment and correlation key strategy
- read-only dispatch routing and incident attachment

Release gate:

- supported events trigger intended agents without repeated noisy duplicate
  investigations.

### 12.6 Phase 5 - Approval-Gated Action Plane

Required outputs:

- runbook-execution-mcp
- action-governor and remediation-executor separation
- policy checks, approvals, rollback hooks, and action journaling
- operator-facing action review UX

Release gate:

- high-risk actions are impossible without approval and policy success.

### 12.7 Phase 6 - Productization And Self-Service

Required outputs:

- discovery engine and generated install overlays
- service auto-detection and onboarding wizard
- compatibility matrix, smoke tests, uninstall flows
- adapter model for cloud event sources and ticketing systems

Release gate:

- install flows succeed for quickstart, attach, standalone, and hybrid modes.

## 13. Acceptance Criteria

The implementation is accepted when all are true:

- no AI-facing component directly connects to internal datastores
- all required MCP services are deployed, reachable, and versioned
- CEO-led orchestration produces final synthesis for investigation workflows
- inter-agent and tool access adheres to defined allow-lists
- high-risk actions require explicit approval and policy pass
- audit trails cover investigation, decision, approval, and action paths
- phase gates pass functional, safety, performance, and upgrade validation

## 14. Validation Requirements

### 14.1 Functional Validation

- human query to incident summary
- human query to blast radius analysis
- human query to change correlation
- Khook event to investigation
- remediation proposal and approved execution
- rejected action handling
- outage behavior for gateway, MCP, and backing data paths

### 14.2 Multi-Agent Validation

- CEO delegates correctly by incident class
- manager invokes approved specialists only
- specialist outputs persist to case file with required schema
- contradictory findings are surfaced and resolved by CEO
- forbidden specialist communication is blocked
- action-governor and remediation-executor enforce preconditions

### 14.3 Safety Validation

- unsupported action attempts fail safely
- missing approval blocks execution
- overbroad namespace access is denied
- prompt injection attempts are contained
- malformed tool responses are handled safely
- redaction and secret masking are validated

### 14.4 Performance And Upgrade Validation

- hook storm behavior
- concurrent investigation throughput
- gateway and MCP latency under load
- Kagent controller and database contention checks
- upgrade compatibility across Kagent, Khook, kmcp, gateway, and backend schema
  changes

## 15. Risks And Mitigation Requirements

- Upstream API churn must be contained via version pinning and contract tests.
- Tool sprawl must be controlled via per-agent curated tool catalogs.
- Direct-bypass regressions must be prevented with policy and code review gates.
- Event noise must be controlled by qualification, enrichment, and deduplication.
- Data sensitivity must be controlled by redaction, masking, and audit.
- Cost and latency must be controlled by coordinator patterns, caching, and
  response budgets.

## 16. Dependencies

- Kubernetes runtime and namespace strategy
- external PostgreSQL for Kagent production operation
- existing observability platform query and action APIs
- OpenTelemetry pipeline for AI layer telemetry
- GitOps delivery pipeline and environment overlays
- approval and policy integration surfaces

## 17. Release Readiness Checklist

- architecture and contract hardening complete
- control plane healthy across target environments
- MCP catalog and agent topology validated
- Khook investigation triggers validated in production-like conditions
- approvals, policy checks, and rollback flows verified
- runbooks, operator guides, and onboarding documentation complete

## 18. Success Metrics

- reduced investigation time-to-first-hypothesis
- reduced event-to-summary latency
- high correctness of change-correlation findings
- high approval-path completion rate for valid actions
- low rate of blocked or unsafe action attempts
- stable MCP and agent workflow availability
