# Kagent Khook Technical Requirements

This document defines implementation-facing technical requirements for the
Kagent + Khook extension layer.

It translates planning and product intent into concrete architecture, contract,
tooling, delivery, and validation requirements for engineering teams.

## Agent Cross-Reference Markers

Use these markers when mapping backlog tasks from
`KAGENT_KHOOK_TASKS.md` to implementation-ready technical requirements in this
document.

| Technical Marker | Scope | Primary Task Batch Marker | Primary Implementation Batch Marker |
| ---- | ---- | ---- | ---- |
| `KK-C01` | AI boundary and runtime path constraints | `KTB-01` | `IKTB-01` |
| `KK-C02` | no direct AI-to-datastore access policy | `KTB-01` | `IKTB-01` |
| `KK-C03` | replaceability, protocol edge, and namespace contracts | `KTB-01` | `IKTB-01` |
| `KK-C04` | identity and access isolation | `KTB-02` | `IKTB-02` |
| `KK-C05` | risk classification and approval gates | `KTB-02` | `IKTB-02` |
| `KK-C06` | audit completeness and governance traceability | `KTB-02` | `IKTB-02` |
| `KK-C07` | case-file canonical state contract | `KTB-03` | `IKTB-03` |
| `KK-C08` | inter-agent envelope schema contract | `KTB-03` | `IKTB-03` |
| `KK-C09` | communication graph boundaries and resume behavior | `KTB-03` | `IKTB-03` |
| `KK-C10` | MCP service categories and platform mediation contract | `KTB-04` | `IKTB-04` |
| `KK-C11` | MCP response schema and semantic versioning policy | `KTB-04` | `IKTB-04` |
| `KK-C12` | tenant scope, redaction, and response bounds | `KTB-04` | `IKTB-04` |
| `KK-C13` | install order for runtime base scaffolding | `KTB-05` | `IKTB-05` |
| `KK-C14` | gateway discovery and federated endpoint constraints | `KTB-05` | `IKTB-05` |
| `KK-C15` | GitOps layout and required platform tooling | `KTB-05` | `IKTB-05` |
| `KK-C16` | control-plane reliability requirements | `KTB-06` | `IKTB-06` |
| `KK-C17` | performance and quota control requirements | `KTB-06` | `IKTB-06` |
| `KK-C18` | runtime cost-control requirements | `KTB-06` | `IKTB-06` |
| `KK-C19` | contract validation gates in CI | `KTB-07` | `IKTB-07` |
| `KK-C20` | functional, safety, and multi-agent validation gates | `KTB-07` | `IKTB-07` |
| `KK-C21` | performance and upgrade validation gates | `KTB-07` | `IKTB-07` |
| `KK-C22` | release blocker criteria for unsafe paths | `KTB-08` | `IKTB-08` |
| `KK-C23` | release blocker criteria for governance bypass | `KTB-08` | `IKTB-08` |
| `KK-C24` | release blocker criteria for audit/schema failure | `KTB-08` | `IKTB-08` |
| `KK-C25` | required implementation deliverables: MCP and agent catalogs | `KTB-09` | `IKTB-09` |
| `KK-C26` | required implementation deliverables: communication and case file | `KTB-09` | `IKTB-09` |
| `KK-C27` | required implementation deliverables: risk policy and overlays | `KTB-09` | `IKTB-09` |
| `KK-C28` | productized install mode contract readiness | `KTB-10` | `IKTB-10` |
| `KK-C29` | compatibility and validation readiness for release | `KTB-10` | `IKTB-10` |
| `KK-C30` | operator runbook and production activation readiness | `KTB-10` | `IKTB-10` |

## 1. Technical Scope And Boundaries

### 1.1 System Boundary [`KK-C01`]

- The AI extension layer SHALL be implemented as Kubernetes-native control and
  service components deployed independently from the core observability data
  plane.
- The primary runtime path SHALL be:
  `Khook -> Kagent -> MCP gateway/catalog -> platform query/action APIs ->`
  `platform backends`.
- No AI-facing component SHALL directly access datastore-native protocols
  (OpenSearch REST DSL, Neo4j Cypher/Bolt, PostgreSQL SQL clients, or
  equivalent).

### 1.2 Replaceability Constraints [`KK-C03`]

- Kagent, Khook, gateway, and MCP services SHALL be replaceable by contract.
- Integration points SHALL be protocol and schema contracts, not shared
  internal libraries.
- Any component swap SHALL preserve external behavior of:
  - MCP tool names and versions
  - inter-agent envelope schema
  - case file schema
  - trigger payload schema

## 2. Platform Components And Runtime Topology

### 2.1 Mandatory Components

The platform SHALL include:

- Kagent control plane (minimal profile)
- Khook controller and Hook resources
- kmcp controller for MCP lifecycle
- external PostgreSQL for Kagent state
- platform-owned MCP services
- platform-owned query/correlation/action APIs
- secrets integration for runtime credentials
- OpenTelemetry instrumentation across AI components

### 2.2 Recommended Components

- MCP/A2A gateway (agentgateway or equivalent)
- policy engine for tool risk and approval enforcement
- centralized audit sink
- GitOps deployment controller for declarative lifecycle

### 2.3 Namespace Segmentation [`KK-C03`]

The deployment SHOULD segment namespaces as:

- `observability-system`: existing platform core
- `ai-runtime`: Kagent controller/UI/agents
- `ai-triggers`: Khook controller/hooks
- `mcp-system`: kmcp control components
- `mcp-services`: platform MCP servers
- `ai-gateway`: gateway/proxy
- `ai-policy`: policy and approval services

Cross-namespace interaction MUST be explicitly allow-listed.

## 3. Control Plane Contracts

### 3.1 Khook Trigger Contract [`KK-C03`]

Khook SHALL:

- watch configured Kubernetes event types
- qualify events by policy, scope, and risk class
- deduplicate event bursts with stable correlation keys
- enrich dispatch payloads with bounded context only
- dispatch to approved Kagent targets

Khook SHALL NOT:

- perform autonomous reasoning
- execute remediation actions
- embed long-lived workflow state

### 3.2 Agent Orchestration Contract [`KK-C09`]

The multi-agent topology SHALL follow:

- default: `CEO -> manager -> specialist`
- permitted shortcut: `CEO -> specialist`
- denied by default: `specialist -> specialist`

Allowed communication edges SHALL be codified and tested as policy.

### 3.3 Shared Case File Contract [`KK-C07`]

A platform-owned case file SHALL be the canonical workflow state store.

The case file MUST support at least:

- workflow identity and status
- incident context
- per-agent outputs
- evidence handles and retrieval pointers
- approval state and decision lineage
- action journal and rollback references

Restarted workflows SHALL resume from case file state, not transient memory.

## 4. MCP And API Technical Contracts

### 4.1 MCP Service Categories [`KK-C10`]

MCP services SHALL expose business capabilities:

- incident search
- graph analysis
- trace investigation
- metrics correlation
- change intelligence
- runbook execution
- incident case file access

Each MCP service SHALL call platform APIs, not datastores directly.

### 4.2 Tool Output Schema [`KK-C11`]

Each MCP tool response SHALL include:

- `summary`
- `structured_data`
- `evidence_handles`
- `confidence`
- `time_window`
- `safety_class`
- `next_recommended_tools`

Responses MUST default to compact payloads and avoid large raw dumps.

### 4.3 Tool Versioning [`KK-C11`]

- Tool names SHALL be semantically versioned (for example `*.v1`).
- Breaking schema changes SHALL require a new tool version.
- Prompt templates and agent logic SHALL bind to versioned response contracts.

### 4.4 Multi-Tenant Controls [`KK-C12`]

MCP and query APIs SHALL enforce:

- namespace scope
- tenant scope
- team scope
- query time-window ceilings
- response size ceilings
- field-level redaction
- secret masking
- deny-lists for restricted data domains

## 5. Agent Runtime Technical Requirements

### 5.1 Role Separation

The runtime SHALL include an orchestration tier, manager tier, and specialist
tier with bounded tool access.

Constraints:

- CEO agent SHALL orchestrate and synthesize only.
- investigation agents SHALL be read-path only.
- action agents SHALL have minimal write-capable tool sets.
- remediation executor SHALL require explicit approval state before invocation.

### 5.2 Inter-Agent Envelope Schema [`KK-C08`]

All agent outputs SHALL conform to a shared envelope with:

- objective
- findings
- evidence handles
- assumptions
- confidence
- risk level
- recommended next action

Schema conformance SHALL be validated in CI.

### 5.3 Tool Attachment Rules [`KK-C09`]

- Agents SHALL only mount tools required for their role.
- Write-class tools SHALL not be available to read-only agents.
- Cross-namespace tool access SHALL require explicit `allowedNamespaces`.

## 6. Security, Policy, And Governance

### 6.1 Identity And Access [`KK-C04`]

- Each agent class SHALL use a dedicated Kubernetes service account.
- Each MCP service SHALL use a dedicated service account.
- NetworkPolicies SHALL enforce namespace and egress boundaries.
- Secrets SHALL be referenced from secret stores only; prompts SHALL not carry
  plaintext secrets.

### 6.2 Tool Risk Classification [`KK-C05`]

Tool operations SHALL be classified:

- `read.safe`
- `read.sensitive`
- `write.low-risk`
- `write.high-risk`
- `write.critical`

The policy engine SHALL map each class to approval and execution constraints.

### 6.3 Approval And Execution Gates [`KK-C05`]

- `write.high-risk` SHALL always require human approval.
- `write.critical` SHALL require manual workflow outside autonomous execution.
- Policy checks SHALL execute before any write-path tool call.
- Rejection outcomes SHALL be fed back into workflow state and agent context.

### 6.4 Audit Requirements [`KK-C06`]

The system SHALL log:

- invoker identity
- agent identity and version
- tool calls and parameters (redacted)
- evidence handles
- policy decisions
- approval decisions
- target resources
- final action outcomes
- latency and token/cost metrics (where applicable)

Audit records SHALL provide end-to-end traceability across gateway and runtime.

## 7. Deployment, Configuration, And Tooling

### 7.1 Install Order (Production) [`KK-C13`]

Deployment SHOULD follow this sequence:

1. preflight and capability checks
2. external PostgreSQL
3. Kagent minimal profile
4. kmcp controller
5. gateway/proxy
6. platform query/action APIs
7. MCP services via kmcp
8. disable direct discovery for gateway-fronted MCP services
9. register federated endpoints
10. create agents
11. create hooks
12. enable read-only flows
13. enable approval-gated writes

### 7.2 Gateway Discovery Model [`KK-C14`]

For gateway-fronted MCP services:

- direct discovery SHALL be disabled on backend MCPServer resources
- gateway catalog registration SHALL be explicit
- Kagent SHALL reference only federated endpoints via `RemoteMCPServer`

### 7.3 GitOps Layout [`KK-C15`]

The repository SHOULD separate base and environment overlays for:

- Kagent
- Khook
- kmcp
- gateway
- agents
- hooks
- policies

Environment overlays SHOULD include quickstart, dev, staging, and prod.

### 7.4 Required Toolchain [`KK-C15`]

Engineering and operations SHOULD standardize on:

- Kubernetes (`kubectl`, Helm, Kustomize)
- GitOps controller (Argo CD or Flux)
- PostgreSQL operations and backup tooling
- OpenTelemetry collector and backend traces for AI control plane
- policy engine tooling (OPA/Gatekeeper/Kyverno class)
- CI schema and contract validation runners
- load and chaos test tooling for gateway/MCP/runtime paths

## 8. Reliability And Performance Requirements

### 8.1 Reliability [`KK-C16`]

- Core control plane components SHALL expose health/readiness endpoints.
- Workflow processing SHALL be idempotent under event replay and restart.
- Case file persistence SHALL guarantee workflow continuity.

### 8.2 Performance [`KK-C17`]

- Khook dedupe SHALL bound repeated trigger fan-out under restart bursts.
- Gateway and MCP fan-out SHALL operate within defined latency SLOs.
- Concurrent investigation workflows SHALL not violate per-tenant quotas.

### 8.3 Cost Controls [`KK-C18`]

- Token and execution budgets SHALL be enforceable per namespace/team.
- Agent prompts and tool responses SHALL remain compact and purpose-scoped.
- Tool invocation retries SHALL use bounded backoff and attempt limits.

## 9. Verification And Release Gates

### 9.1 Contract Validation [`KK-C19`]

CI SHALL validate:

- MCP response schema conformance
- agent envelope schema conformance
- version compatibility checks
- prohibited direct datastore client usage in AI-facing code

### 9.2 Functional And Safety Validation [`KK-C20`]

Pre-release validation SHALL include:

- human query flows
- event-triggered investigation flows
- approval-gated action flows
- rejected action behavior
- redaction and secret masking tests
- prompt-injection hardening tests

### 9.3 Multi-Agent Validation [`KK-C20`]

Validation SHALL prove:

- CEO delegation correctness
- manager-to-specialist constraints
- blocked unauthorized specialist peer calls
- contradiction handling and synthesis behavior
- resume behavior from case file after restart

### 9.4 Performance And Upgrade Validation [`KK-C21`]

Validation SHALL include:

- trigger storm handling
- concurrent investigation load
- gateway latency under load
- MCP outage and degraded-mode behavior
- Kagent/Khook/kmcp upgrades with stable contracts
- backend schema evolution hidden behind platform APIs

### 9.5 Release Blockers [`KK-C22`, `KK-C23`, `KK-C24`]

A release SHALL be blocked if any of the following is true:

- direct AI-to-datastore access path exists
- ungoverned write tool is reachable by an unauthorized agent
- gateway bypass is possible for governed tools
- required audit fields are missing from action-path traces
- schema compatibility checks fail for versioned tool contracts

## 10. Implementation Deliverables

Cross-reference note:

- Use `KK-C25` for MCP and agent catalog deliverables.
- Use `KK-C26` for communication policy graph and case-file deliverables.
- Use `KK-C27` for risk/approval policy matrix and deployment overlay deliverables.
- Use `KK-C28`, `KK-C29`, and `KK-C30` when validating productization readiness
  with install modes, compatibility, and operator release readiness.

Engineering completion SHALL include:

- versioned MCP catalog specification
- agent catalog specification with tool bindings
- inter-agent communication policy graph
- case file schema and retention policy
- risk/approval policy matrix
- deployment overlays for all target install modes
- operational runbooks and SLO definitions for AI control plane
