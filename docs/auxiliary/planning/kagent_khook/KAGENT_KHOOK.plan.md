# Observability Platform Extension Plan - Kagent + Khook AI and Automation Layer

## 1. Purpose

This document defines how to add **Kagent** and **Khook** to the observability
platform as a **decoupled AI and automation layer**.

The design is constrained by four non-negotiables:

1. **Kagent and Khook must remain replaceable**
2. **All agent-to-platform access must use MCP-facing interfaces**
3. **No AI-facing component may query OpenSearch, Neo4j, or other platform
   databases directly**
4. **The platform remains cloud-agnostic, Kubernetes-native, open-source-first,
   and plug-and-play**

This plan assumes the broader observability platform already includes:

- OpenTelemetry for collection and normalization
- OpenSearch for search, analytics, and vector retrieval
- Neo4j for graph/topology/dependency intelligence
- Grafana and OpenSearch Dashboards for visualization
- Kubernetes as the runtime boundary

It adds the missing **reasoning**, **reactive automation**, and **governed
action** layers.

## 2. Executive decision

### 2.1 Chosen role of each component

| Component | Role in this architecture | What it must **not** become |
| --- | --- | --- |
| **Kagent** | Agent runtime, orchestration surface, chat/UI entry point, A2A composition layer, HITL gate consumer | A data-plane system, direct database client, or monolithic automation brain |
| **Khook** | Event watcher, filter, deduplicator, prompt injector, Kagent trigger | A reasoning engine, remediation engine, or observability query system |
| **kmcp** | MCP server lifecycle manager and MCP packaging/deployment toolchain | A business-logic layer |
| **MCP services** | Stable integration contract between AI layer and observability platform | Thin wrappers around raw DB access without domain contracts |
| **Optional agentgateway / MCP gateway** | Governance, policy, audit, proxying, federation, rate limits, security, centralized routing for MCP/A2A/LLM traffic | A replacement for Kagent or for the observability platform itself |

### 2.2 Core architectural stance

The correct split is:

- **Khook watches and triggers**
- **Kagent reasons and coordinates**
- **MCP services expose approved capabilities**
- **Platform services implement retrieval, correlation, graph analysis, change
  intelligence, and safe actions**
- **Datastores remain behind platform-owned query services**

This mirrors both the attached research and the current official project
direction:

- Kagent is positioned as a Kubernetes-native agent framework with MCP and A2A
  support, not as the storage or ingestion system. [U1][S1][S2]
- Khook is positioned as a Kubernetes controller that monitors events and
  triggers Kagent agents from hook definitions with basic deduplication.
  [U1][S3]
- Current Kagent documentation explicitly treats MCP as the standard extension
  mechanism for bringing external capabilities into agents. [S2][S4]
- Current Kagent releases moved tool lifecycle responsibilities into **kmcp**
  and removed the old ToolServer API from Kagent. [S5][S6]

## 3. Architectural principles

## 3.1 Replaceability by contract

Kagent and Khook are integrated only through stable protocol and resource
boundaries:

- **Khook -> Kagent** via Hook definitions and agent invocation contract
- **Kagent -> tools** via MCP and A2A
- **MCP services -> platform services** via internal API contracts
- **Platform services -> databases** via platform-owned adapters/repositories

This means that later you can:

- replace Kagent with another agent runtime
- replace Khook with another trigger controller
- replace individual MCP services without changing the agent layer
- upgrade OpenSearch or Neo4j schemas without rewriting agent prompts

## 3.2 MCP-only AI access

No Kagent agent, no Khook workflow, and no external UI may connect directly to:

- OpenSearch REST endpoints
- Neo4j Bolt/HTTP endpoints
- PostgreSQL backends
- any other internal datastore

Instead, every AI-facing capability is exposed as one of:

- an **MCP server**
- a **federated MCP endpoint**
- a **Kagent agent exposed via A2A/MCP**
- a **governed HTTP tool** only when temporarily required during transition

The target state is **MCP-first**.

## 3.3 Query services before data stores

Even MCP servers should not be modeled as “LLM-friendly database clients”.

The recommended chain is:

`Agent -> MCP tool -> platform query service -> datastore`

not:

`Agent -> MCP tool -> raw DB query`

This gives you:

- schema insulation
- tenancy enforcement
- redaction control
- business-level result shaping
- query cost control
- easier testing
- easier future replacement

## 3.4 Read-first, act-later rollout

The initial rollout must be:

1. **read-only triage**
2. **read-only investigation**
3. **proposed remediation**
4. **approval-gated remediation**
5. **limited autonomous remediation for tightly bounded low-risk actions**

Do not start with autonomous repair.

## 4. What current upstream capabilities imply for your design

## 4.1 Kagent implications

Current Kagent documentation and repo indicate:

- Kagent is a Kubernetes-native framework for AI agents, with agents represented
  as CRDs and support for multiple model providers, MCP tools, A2A, and
  OpenTelemetry tracing. [S1][S7]
- Agents can consume MCP servers, Kubernetes Services designated for MCP, and
  other agents as tools. [S2][S8]
- A2A-enabled agents are automatically exposed as an MCP endpoint on the Kagent
  controller, which is useful for composition. [S8]
- Kagent now expects the tools lifecycle to be handled partly through **kmcp**,
  with the older ToolServer API removed. [S5]
- For production, Kagent should use an external PostgreSQL instance. [S9]
- Kagent supports Human-in-the-Loop approval gates for sensitive tools. [S10]

### Resulting design choice

Use **Kagent minimal profile**, not the demo profile, and explicitly define only
the agents and MCP references you need. [S11]

## 4.2 kmcp implications

Current kmcp documentation indicates:

- kmcp exists to accelerate MCP server development and manage MCP server
  lifecycle in Kubernetes. [S12]
- The kmcp controller manages MCPServer resources. [S13]
- kmcp is now installed by default with Kagent, but can also be managed
  separately depending on your release discipline. [S6]

### Resulting design choice

Use **kmcp as the standard packaging and lifecycle layer** for platform-owned
MCP services.

## 4.3 Khook implications

Current Khook docs/readme indicate:

- Khook monitors Kubernetes events and triggers Kagent agents from hook
  definitions. [S3]
- It currently supports event types such as `pod-restart`, `pod-pending`,
  `oom-kill`, `probe-failed`, and `node-not-ready`, and includes basic
  deduplication. [S3][S14]
- Hook resources can carry one or more event configurations with an agent target
  and prompt template. [S14]

### Resulting design choice

Use Khook only for:

- event qualification
- prompt templating
- event deduplication
- dispatch to the correct triage or investigation agent

Do not put reasoning logic in Khook.

## 4.4 Gateway / proxy implications

Current Kagent operational docs and related agentgateway documentation indicate:

- Kagent supports proxying agent-to-agent and agent-to-MCP traffic through a
  configured proxy URL. [S15]
- Current Kagent/kmcp guidance explicitly notes that when you want a gateway in
  front of kmcp resources, you should disable direct Kagent discovery on those
  MCPServer resources. [S4][S6]
- Agentgateway provides a federated MCP endpoint, centralized governance, audit,
  security, and can automatically expose OpenAPI resources as MCP-ready tools.
  [S16][S17]

### Resulting design choice

Use a **gatewayed MCP access layer** as the preferred production pattern.

This gateway can be:

- **agentgateway** if you want protocol-native governance now
- or a simpler internal MCP ingress/proxy if you want a narrower first phase

## 5. Target architecture

## 5.1 Layered view

```text
+------------------------------------------------------------------------------------------------------+
|                                      User / Operator Interfaces                                      |
| ---------------------------------------------------------------------------------------------------- |
| Kagent UI | Internal portal | Slack/Teams A2A clients | CLI/API | Incident console | Approval UI     |
+----------------------------------------------------------+-------------------------------------------+
                                                           |
                                                           v
+------------------------------------------------------------------------------------------------------+
|                              Multi-Agent Coordination and Control Layer                              |
| ---------------------------------------------------------------------------------------------------- |
| CEO Agent (central command/orchestrator)                                                             |
| - receives objectives, incidents, and escalations                                                    |
| - decomposes work into sub-tasks                                                                     |
| - invokes specialist agents as tools via A2A                                                         |
| - resolves conflicting findings                                                                      |
| - decides whether to stop, continue, escalate, or request approval                                   |
| ---------------------------------------------------------------------------------------------------- |
| Manager Agents                                                                                       |
| - triage-director                                                                                    |
| - investigation-manager                                                                              |
| - action-governor                                                                                    |
| ---------------------------------------------------------------------------------------------------- |
| Specialist Agents                                                                                    |
| - incident-investigator   - logs-analyst   - trace-analyst   - metrics-correlator                    |
| - graph-analyst           - change-correlator                                                        |
| - runbook-planner         - remediation-executor   - evidence-summarizer                             |
+----------------------------------------------------------+-------------------------------------------+
                                                           |
                                               agent-to-agent via A2A
                                               agent-to-tool via MCP
                                                           |
                                                           v
+------------------------------------------------------------------------------------------------------+
|                               AI Connectivity / Governance Layer                                     |
| ---------------------------------------------------------------------------------------------------- |
| agentgateway or internal MCP/A2A gateway                                                             |
| - authn/authz   - audit   - rate limits   - routing   - federation   - traffic policy                |
+----------------------------------------------------------+-------------------------------------------+
                                                           |
                                                           v
+------------------------------------------------------------------------------------------------------+
|                                          MCP Service Layer                                           |
| ---------------------------------------------------------------------------------------------------- |
| kmcp-managed MCP servers                                                                             |
| - incident-search-mcp  - graph-analysis-mcp  - trace-investigation-mcp                               |
| - metrics-correlation-mcp  - change-intelligence-mcp                                                 |
| - incident-casefile-mcp  - runbook-execution-mcp  - ticketing-notification-mcp                       |
+----------------------------------------------------------+-------------------------------------------+
                                                           |
                                                           v
+------------------------------------------------------------------------------------------------------+
|                                Platform Domain Services / Query APIs                                 |
| ---------------------------------------------------------------------------------------------------- |
| observability-query-api | graph-query-api | trace-correlation-api | metrics-analysis-api             |
| change-event-api | incident-memory-api | remediation-policy-api | runbook-engine-api                 |
+----------------------------------------------------------+-------------------------------------------+
                                                           |
                                                           v
+------------------------------------------------------------------------------------------------------+
|                                  Core Observability Data / Action Plane                              |
| ---------------------------------------------------------------------------------------------------- |
| OpenSearch | Neo4j | trace/metric stores | Kubernetes API | GitOps | ticketing | chat notifications  |
+------------------------------------------------------------------------------------------------------+
```

## 5.2 Reactive event path

```text
Kubernetes Event / Condition / Alert
        |
        v
     Khook
  - watch
  - dedupe
  - qualify
  - enrich event prompt
        |
        v
CEO agent or triage-director
        |
        +--> investigation-manager
        |       +--> logs-analyst
        |       +--> trace-analyst
        |       +--> metrics-correlator
        |       +--> graph-analyst
        |       +--> change-correlator
        |
        +--> action-governor
                +--> runbook-planner
                +--> remediation-executor [approval-gated]
        |
        v
MCP services -> platform query/action services -> backends
        |
        v
Diagnosis -> recommendation -> optional approval -> action
```

## 5.3 Query path for humans

```text
Operator question
   |
   v
CEO agent
   |
   +--> triage-director
   +--> investigation-manager
   |      +--> specialist agents
   +--> action-governor
   |
   +--> incident-casefile-mcp
   +--> domain MCP services
   |
   v
Correlated answer with evidence, confidence, contradictions resolved, and recommended action
```

## 6. Required component model

## 6.1 Namespaces

Use separate namespaces to preserve replacement boundaries and blast-radius
control.

| Namespace | Purpose |
| --- | --- |
| `observability-system` | Existing core observability platform |
| `ai-runtime` | Kagent runtime, UI, controller |
| `ai-triggers` | Khook controller and hook resources |
| `mcp-system` | kmcp controller, shared MCP CRDs |
| `mcp-services` | Platform-owned MCP servers |
| `ai-gateway` | Optional agentgateway / MCP gateway |
| `ai-policy` | approval services, prompt fragments, policy config |

## 6.2 Core components to deploy

### Mandatory

- Kagent
- Khook
- kmcp
- External PostgreSQL for Kagent production state
- Platform-owned MCP servers
- Platform-owned query/correlation APIs
- Secrets management integration
- OpenTelemetry instrumentation for AI layer

### Recommended

- agentgateway or equivalent MCP/A2A gateway
- GitOps deployment for AI layer resources
- policy engine for workload and secret governance
- dedicated audit sink for AI actions and approval records

### Optional

- Slack / Teams A2A clients
- voice or chat front ends
- agent memory for carefully bounded use cases
- developer-facing MCP catalog portal

## 7. MCP service design

## 7.1 MCP service categories

Build MCP services around **business capabilities**, not storage technologies.

### 1. Incident search MCP

Purpose:

- semantic incident lookup
- similar incidents
- postmortem retrieval
- known-fix retrieval

Backends:

- observability-query-api
- incident-memory-api

Never expose:

- raw OpenSearch index names
- arbitrary DSL passthrough

### 2. Graph analysis MCP

Purpose:

- blast radius
- upstream/downstream dependencies
- ownership lookup
- impacted user journeys
- critical path traversal

Backends:

- graph-query-api

Never expose:

- arbitrary Cypher execution

### 3. Trace investigation MCP

Purpose:

- fetch trace by correlation handle
- span tree summary
- anomalous span identification
- service hop comparison

Backends:

- trace-correlation-api

Never expose:

- raw tracing backend query language

### 4. Metrics correlation MCP

Purpose:

- time-window summaries
- anomaly windows
- candidate signals
- correlated resource spikes
- SLI/SLO state summaries

Backends:

- metrics-analysis-api

Never expose:

- unbounded arbitrary PromQL from a general-purpose agent unless isolated to a
  dedicated PromQL sub-agent

### 5. Change intelligence MCP

Purpose:

- recent deploys
- config changes
- rollout events
- GitOps sync history
- feature flag changes

Backends:

- change-event-api

### 6. Runbook execution MCP

Purpose:

- safe operational steps
- restart/pause/resume/rollback
- ticket creation
- notification
- evidence capture

Backends:

- runbook-engine-api
- remediation-policy-api

This MCP server is the most sensitive and must default to approval-gated mode.

## 7.2 Tool contract style

Every MCP tool should return:

- `summary`
- `structured_data`
- `evidence_handles`
- `confidence`
- `time_window`
- `safety_class`
- `next_recommended_tools`

Do not return huge raw payloads by default.

## 7.3 Tool versioning

Version all MCP tools semantically.

Pattern:

- `incident.search.v1`
- `graph.blast_radius.v1`
- `trace.trace_summary.v1`
- `runbook.restart_workload.v1`

Never let prompt text depend on unstable response shapes.

## 7.4 Multi-tenant and redaction rules

The MCP layer must enforce:

- namespace scoping
- tenant scoping
- team scoping
- field-level redaction
- secret masking
- deny-lists for regulated indexes or graph subgraphs
- query window ceilings
- result size ceilings

## 8. Multi-agent system design

## 8.1 Design goal

The AI layer must be an explicit **multi-agent system** rather than a single
general-purpose assistant.
This is required for four reasons:

1. **Narrow specialization improves reliability**
2. **Tool access can be minimized per agent**
3. **Inter-agent delegation creates a replaceable control topology**
4. **The central orchestration policy can be changed without changing specialist
   agents**

Kagent supports this model directly because agents can be used as tools by other
agents, every A2A-enabled agent is exposed through an A2A endpoint, and
A2A-enabled agents are also exposed as MCP servers through the kagent
controller. [S7][S8][S15]

## 8.2 Control topology

Use a three-tier control topology.

### Tier 1 - CEO agent

A single central orchestration agent acts as the **CEO** of the AI layer.

Suggested name:

- `ops-ceo-agent`

Its job is not to be the deepest technical specialist.
Its job is to:

- accept high-level goals from humans, Khook, or external systems
- classify the request or incident
- create an execution plan
- decide which specialist agents to invoke
- maintain task state
- merge findings into one coherent answer
- decide whether the workflow should escalate to approval or stop at
  recommendation
- keep agent interactions bounded and ordered

The CEO agent is the **command-and-synthesis plane**, not the raw analysis
plane.

### Tier 2 - manager agents

These agents own a bounded domain workflow and reduce the CEO agent's cognitive
load.

Recommended manager agents:

- `triage-director`
- `investigation-manager`
- `action-governor`

The CEO can call specialists directly in simple flows, but in production the
manager layer is better because it:

- stabilizes prompt complexity
- reduces chatty fan-out from the CEO agent
- creates clearer responsibility boundaries
- allows selective replacement of workflow logic

### Tier 3 - specialist agents

These agents perform the actual deep work in one narrow domain and are the main
consumers of MCP tools.

Recommended specialist agents:

- `incident-investigator`
- `logs-analyst`
- `trace-analyst`
- `metrics-correlator`
- `graph-analyst`
- `change-correlator`
- `evidence-summarizer`
- `runbook-planner`
- `remediation-executor`

## 8.3 Architectural rule for inter-agent communication

Inter-agent communication must follow this rule:

- default path: `CEO -> manager -> specialist`
- allowed shortcut: `CEO -> specialist`
- restricted path: `specialist -> specialist` only through explicit allow-list
- forbidden path: unbounded peer-to-peer mesh where every agent can call every
  other agent

This avoids:

- recursive delegation loops
- excessive token usage
- unclear ownership
- hard-to-debug emergent behavior

Kagent supports agent-to-agent invocation through agents-as-tools and A2A, and
can route agent-to-agent traffic through a proxy. [S8][S15]

## 8.4 CEO agent responsibilities

The CEO agent must specialize in orchestration, not raw querying.

### Inputs

- user requests
- Khook-triggered incident payloads
- manager agent escalations
- approval outcomes
- policy denials
- workflow completion notifications

### Responsibilities

1. classify the request or incident type
2. decide whether the workflow is informational, investigative, or actionable
3. instantiate a task plan
4. select the required manager and specialist agents
5. collect outputs in a shared case file
6. resolve contradictions between agents
7. assign follow-up work when evidence is insufficient
8. produce the final narrative or action proposal
9. route high-risk actions to approval
10. terminate the workflow cleanly and write the final state

### CEO constraints

The CEO agent should not:

- query OpenSearch or Neo4j directly
- own broad write tools
- perform raw operational actions
- execute arbitrary code
- hold long-lived private memory outside the platform case file

### CEO tool access

The CEO agent should have:

- read access to `incident-casefile-mcp`
- access to manager agents as tools
- optional access to a low-risk notification tool
- access to approval status lookup
- no direct access to `runbook-execution-mcp` high-risk actions

This keeps orchestration separate from execution.

## 8.5 Manager-agent model

### A. Triage Director

Purpose:

- rapid intake classification
- signal prioritization
- initial branching

Reads:

- case file
- incident search summaries
- basic metrics and event summaries

Can invoke:

- `incident-investigator`
- `graph-analyst`
- `change-correlator`

Should not:

- perform remediation

### B. Investigation Manager

Purpose:

- run a structured evidence-gathering workflow
- coordinate logs, traces, metrics, graph, and change analysis

Reads:

- all investigation outputs
- case file

Can invoke:

- `logs-analyst`
- `trace-analyst`
- `metrics-correlator`
- `graph-analyst`
- `change-correlator`
- `evidence-summarizer`

Should not:

- execute operational changes

### C. Action Governor

Purpose:

- verify safety posture before any write-path action
- transform diagnosis into bounded, policy-checked action candidates

Reads:

- investigation outputs
- policy classification
- runbook templates

Can invoke:

- `runbook-planner`
- `remediation-executor` only after approval state is satisfied

Should not:

- perform open-ended diagnosis

## 8.6 Specialist-agent catalog

### 1. Incident Investigator

Purpose:

- assemble the first coherent hypothesis set for an incident

Reads:

- incident search
- prior incidents
- trace summary
- metrics anomaly summary
- graph impact summary
- recent changes

Writes:

- hypothesis list
- ranked suspected causes
- missing-evidence requests

### 2. Logs Analyst

Purpose:

- interpret semantically retrieved log evidence

Reads:

- incident-search-mcp
- case file

Writes:

- error pattern summary
- likely failure signatures
- suspicious timestamps or components

### 3. Trace Analyst

Purpose:

- inspect service hops, span anomalies, latency inflation, and error propagation

Reads:

- trace-investigation-mcp

Writes:

- span-path summary
- anomalous service hop candidates
- correlation hints for graph and change agents

### 4. Metrics Correlator

Purpose:

- detect temporal correlation, saturation, resource stress, and SLI/SLO
  deviation

Reads:

- metrics-correlation-mcp

Writes:

- metric anomaly summary
- probable causal windows
- suggested next agents

### 5. Graph Analyst

Purpose:

- reason over service dependencies, blast radius, ownership, and
  upstream/downstream paths

Reads:

- graph-analysis-mcp

Writes:

- impacted services
- dependency path summary
- owner and escalation targets

### 6. Change Correlator

Purpose:

- connect incident onset with deploy, config, rollout, and flag changes

Reads:

- change-intelligence-mcp

Writes:

- change timeline
- correlated release candidates
- rollback candidates

### 7. Evidence Summarizer

Purpose:

- compress specialist outputs into a deterministic evidence packet for the CEO
  or managers

Reads:

- case file
- specialist outputs

Writes:

- normalized evidence summary
- contradiction table
- confidence rollup

### 8. Runbook Planner

Purpose:

- convert a verified diagnosis into bounded operational steps

Reads:

- investigation results
- remediation policy
- runbook catalog

Writes:

- action plan
- rollback plan
- expected blast radius
- required approvals

### 9. Remediation Executor

Purpose:

- execute tightly bounded pre-approved actions through MCP only

Reads:

- approved action plan
- policy state
- target resource identity

Writes:

- execution result
- evidence of change
- post-action validation summary

This agent must be completely separate from investigative agents.

## 8.7 Inter-agent communication protocol

The platform should standardize inter-agent communication around a **case-file
contract** rather than free-form conversation alone.

### Required envelope for every agent output

Each agent response should write a structured object such as:

- `task_id`
- `case_id`
- `agent_name`
- `objective`
- `summary`
- `findings`
- `evidence_handles`
- `confidence`
- `assumptions`
- `requested_next_agents`
- `requested_tools`
- `risk_level`
- `recommended_actions`
- `status`

### Communication pattern

1. CEO or manager invokes another agent as a tool through A2A.
2. The called agent reads the relevant case-file slice from
   `incident-casefile-mcp`.
3. The called agent executes only its allowed MCP tools.
4. The called agent writes a structured result back to the case file.
5. The caller consumes the result, decides the next step, and either:
   - invokes another specialist
   - asks for more evidence
   - escalates to the Action Governor
   - terminates the flow

This keeps long-running reasoning state outside transient chat context.

## 8.8 Shared state and memory model

Do not rely on hidden, unbounded conversational memory between agents.

Use a platform-owned **incident case file** backed by your own service layer.

### Case file contents

- incident metadata
- original event or user request
- execution plan
- per-agent outputs
- evidence handles
- approval state
- selected remediation plan
- final resolution summary
- audit trail

### Why this matters

- agent replacement becomes easier
- workflows can resume after restart
- the evidence chain is auditable
- different runtimes can participate later
- no agent needs direct datastore access

The case file is exposed to agents through `incident-casefile-mcp`, not through
a raw database connection.

## 8.9 Allowed communication graph

Recommended communication graph:

```text
Human / Khook
    |
    v
CEO Agent
    |
    +--> Triage Director
    |       |
    |       +--> Incident Investigator
    |       +--> Graph Analyst
    |       +--> Change Correlator
    |
    +--> Investigation Manager
    |       |
    |       +--> Logs Analyst
    |       +--> Trace Analyst
    |       +--> Metrics Correlator
    |       +--> Graph Analyst
    |       +--> Change Correlator
    |       +--> Evidence Summarizer
    |
    +--> Action Governor
            |
            +--> Runbook Planner
            +--> Remediation Executor  [approval-gated]
```

### Communication policy

- specialists may return `requested_next_agents`
- only the caller decides whether to invoke them
- specialists do not autonomously expand the graph unless explicitly allowed
- the CEO is the final synthesis point for user-facing output
- the Action Governor is the final synthesis point for action proposals

## 8.10 Triggered workflows with Khook

Khook should normally trigger the **CEO agent** or the **Triage Director**, not
a random specialist.

Recommended pattern:

- `low/medium-complexity event` -> `triage-director`
- `high-severity or ambiguous event` -> `ops-ceo-agent`
- `known safe repetitive event` -> `triage-director`, then optionally
  `action-governor`

This prevents event triggers from bypassing orchestration and creating
inconsistent workflows.

## 8.11 Tool and agent attachment rules

Use explicit attachment boundaries.

### CEO agent

Allowed tools:

- `incident-casefile-mcp`
- `approval-status-mcp`
- manager agents as tools

### Manager agents

Allowed tools:

- `incident-casefile-mcp`
- specialist agents as tools
- only the minimal cross-domain MCP tools required for branching

### Specialist agents

Allowed tools:

- only their domain MCP servers
- `incident-casefile-mcp`

### Executor agents

Allowed tools:

- `runbook-execution-mcp`
- `incident-casefile-mcp`
- optional post-action validation MCP tools

This tool discipline matters more than prompt wording.

## 8.12 Replacement model

This multi-agent design remains replaceable because:

- specialist capabilities are hidden behind MCP and A2A contracts
- the CEO agent orchestrates by contract, not by datastore specifics
- the case file is platform-owned
- the gateway mediates traffic
- the execution path is isolated from the investigation path

You can later replace:

- the CEO agent with another orchestrator
- Kagent with another runtime that supports A2A or MCP wrapping
- a specialist agent with a new model or implementation
- the entire action-governor layer without changing the investigation agents

## 8.13 Prompting rules for the multi-agent system

Every production agent prompt should include:

- domain role
- allowed agents it may invoke
- allowed MCP tools
- prohibited tools and actions
- required case-file read/write behavior
- required evidence format
- confidence rules
- contradiction handling rules
- escalation conditions
- approval requirements
- explicit ban on direct DB references or raw datastore querying

## 8.14 Skills and reusable prompt fragments

Use reusable skill/prompt fragments for:

- Kubernetes context
- observability reasoning style
- graph reasoning style
- incident narrative format
- remediation safety rules
- evidence citation rules
- escalation behavior
- case-file write contract
- inter-agent delegation etiquette

## 9. Khook design

## 9.1 Role of Khook in the platform

Khook is the **reactive dispatch layer** for Kubernetes-native events.

It should:

- monitor supported event types
- deduplicate noisy event bursts
- apply per-namespace/per-workload hook selection
- construct structured event prompts
- dispatch to the correct Kagent agent
- record audit status in Hook state and cluster events

It should not:

- run heavy analysis
- directly call platform query APIs
- directly call data stores
- directly remediate resources

## 9.2 Initial hook set

Use only high-signal, high-value hooks in phase 1:

| Hook | Event types | Default action |
| --- | --- | --- |
| `hook-crash-investigate` | `pod-restart`, `oom-kill`, `probe-failed` | investigate and report |
| `hook-scheduling-investigate` | `pod-pending` | investigate and report |
| `hook-node-health-investigate` | `node-not-ready` | investigate and escalate |
| `hook-critical-service-impact` | `probe-failed` on labelled critical workloads | investigate blast radius |
| `hook-change-correlation` | restart/failure events near deploy windows | investigate change correlation |

## 9.3 Prompt template rules for Khook

Prompts generated by hooks must be:

- compact
- structured
- scoped
- evidence-first
- action-neutral by default

Do not use the autonomous examples from upstream as your production baseline.

Use a controlled format such as:

```text
EVENT:
- type: oom-kill
- namespace: payments
- workload: checkout-api
- resource: checkout-api-7f9d6c5d9c-2l7mk
- first_seen: 2026-04-08T10:14:00Z
- cluster: prod-eu1

TASK:
1. Determine likely cause.
2. Retrieve related logs, traces, metrics summary, recent changes, and dependency impact.
3. Produce a ranked diagnosis.
4. Recommend bounded next actions.
5. Do not execute changes unless an approved action tool is explicitly invoked.
```

## 9.4 Event enrichment strategy

Before dispatch, enrich events with:

- cluster ID
- environment
- namespace
- workload labels
- owner/team
- criticality tier
- deployment revision
- recent rollout marker
- incident correlation key

If Khook itself should remain simpler, implement enrichment in a lightweight
platform event-enricher service and have Khook include only keys that the agent
can use to fetch deeper data through MCP.

## 10. Gateway and discovery strategy

## 10.1 Why a gateway is recommended

A gateway in front of MCP services gives:

- protocol centralization
- consistent authentication
- rate limiting
- audit logging
- easier future runtime replacement
- federation of many MCP services into fewer stable endpoints
- cleaner exposure of existing REST APIs as MCP tools

This is particularly attractive because current official guidance already
supports:

- proxying Kagent agent-to-MCP traffic [S15]
- disabling direct MCP discovery when fronting kmcp services with a gateway
  [S4][S6]
- using agentgateway as a protocol-native governance layer [S16][S17]

## 10.2 Recommended production pattern

### Pattern A - Preferred

`Kagent -> agentgateway -> MCP services -> platform APIs -> databases`

### Pattern B - Simpler interim

`Kagent -> internal MCP proxy -> MCP services -> platform APIs -> databases`

### Pattern C - Not recommended except dev

`Kagent -> MCP services directly`

## 10.3 Discovery and registration rules

For every kmcp-managed MCPServer intended to sit behind a gateway:

- set discovery disabled on the MCPServer
- register it explicitly in the gateway catalog
- expose only the federated endpoint to Kagent
- create `RemoteMCPServer` resources in Kagent that point at the gateway
  endpoint, not at individual backends

## 11. Security and governance

## 11.1 Identity model

Use:

- dedicated Kubernetes service accounts per agent class
- dedicated service accounts per MCP service
- namespace isolation
- NetworkPolicies
- secret references, never prompt-embedded secrets
- approval-gated tools for destructive operations

## 11.2 Tool classes

| Class | Examples | Approval |
| --- | --- | --- |
| `read.safe` | incident search, graph lookup, trace summary | none |
| `read.sensitive` | privileged config lookup, restricted tenant views | conditional |
| `write.low-risk` | incident annotation, ticket creation, Slack notification | conditional |
| `write.high-risk` | restart workload, pause rollout, rollback, scale, cordon/drain | required |
| `write.critical` | delete resources, change network policy, production failover | manual workflow only |

## 11.3 Approval flow

Use Kagent HITL for:

- tool approvals
- explicit operator confirmation
- rejection reasons fed back into the agent context

For system-to-system automation outside the UI, back the approval decision with
your own approval service and expose that through MCP or A2A.

## 11.4 Audit requirements

Log at minimum:

- who invoked the agent
- which agent ran
- which tools were called
- evidence handles returned
- approval decisions
- final actions
- action target resources
- timing and latency
- token/cost metrics if using hosted models

## 12. Deployment model

## 12.1 Installation mode

Use four supported modes in platform documentation:

### Quickstart

- local or sandbox cluster
- Kagent minimal
- Khook
- kmcp
- mock or reduced MCP catalog
- no autonomous actions

### Attach

- existing observability platform
- add AI layer only
- connect MCP services to existing APIs

### Standalone

- full platform plus AI layer in one cluster

### Hybrid

- AI layer in-cluster
- observability APIs or backends may be external

## 12.2 Recommended production install order

1. Preflight checks
2. Capability discovery
3. Install external PostgreSQL for Kagent
4. Install Kagent with minimal profile
5. Install kmcp
6. Install MCP gateway
7. Deploy platform-owned query APIs
8. Deploy MCP services through kmcp
9. Disable direct discovery where gatewayed
10. Register federated MCP endpoints
11. Create Kagent agents
12. Create Khook hooks
13. Enable read-only investigation
14. Enable approvals
15. Later enable bounded write actions

## 12.3 GitOps structure

Recommended structure:

```text
platform/
  observability/
  ai-layer/
    base/
      kagent/
      khook/
      kmcp/
      gateway/
      agents/
      hooks/
      policies/
    overlays/
      quickstart/
      dev/
      staging/
      prod/
```

## 13. Detailed implementation plan

## Phase 0 - Architecture hardening

### Objectives

- lock interface boundaries
- stop direct datastore access from AI-facing components
- define MCP catalog

### Deliverables

- interface contracts for query APIs
- MCP tool catalog v1
- agent catalog v1
- trigger catalog v1
- security classification matrix
- approval policy matrix

### Exit criteria

- all required tools mapped to platform APIs
- no proposed design still depends on direct OpenSearch/Neo4j access from agents

## Phase 1 - Base AI control plane

### Objectives

- install a minimal but production-capable runtime foundation

### Tasks

1. Install external PostgreSQL for Kagent
2. Install Kagent minimal profile
3. Install kmcp
4. Install Khook
5. Install gateway/proxy
6. Add OpenTelemetry instrumentation for AI layer
7. Add NetworkPolicies and service accounts
8. GitOps-manage all CRDs and Helm releases

### Exit criteria

- Kagent UI reachable
- Kagent tracing visible
- kmcp controller healthy
- Khook healthy
- gateway healthy
- no demo agents active in production

## Phase 2 - Read-only MCP capability layer

### Objectives

- expose the platform’s read path through governed MCP interfaces

### Tasks

1. Build `incident-search-mcp`
2. Build `graph-analysis-mcp`
3. Build `trace-investigation-mcp`
4. Build `metrics-correlation-mcp`
5. Build `change-intelligence-mcp`
6. Deploy via kmcp
7. Register via gateway
8. Create Kagent `RemoteMCPServer` references
9. Disable direct MCP discovery for gatewayed services

### Exit criteria

- all five MCP services callable from test client
- no tool calls bypass gateway
- result schemas stable and versioned

## Phase 3 - Multi-agent mesh and CEO orchestration

### Objectives

- create a governed multi-agent system with a central orchestration agent and
  narrow specialist agents

### Tasks

1. Create `ops-ceo-agent`
2. Create `triage-director`
3. Create `investigation-manager`
4. Create `action-governor`
5. Create `incident-investigator`
6. Create `logs-analyst`
7. Create `trace-analyst`
8. Create `metrics-correlator`
9. Create `graph-analyst`
10. Create `change-correlator`
11. Create `evidence-summarizer`
12. Create `runbook-planner`
13. Create `remediation-executor`
14. Define the case-file schema and `incident-casefile-mcp`
15. Define allowed agent-to-agent communication graph
16. Define reusable prompt fragments / skills
17. Add response schemas, confidence rules, and contradiction handling rules
18. Configure proxy-mediated agent-to-agent routing
19. Configure cross-namespace `allowedNamespaces` only where required

### Exit criteria

- CEO agent can orchestrate at least one full investigation flow end-to-end
- manager agents can invoke only their approved specialist sets
- specialist agents cannot invoke forbidden peers or forbidden tools
- the case file captures all agent outputs and evidence handles
- final synthesis is produced by the CEO agent, not by ad hoc peer chatter

## Phase 4 - Reactive triage with Khook

### Objectives

- add event-driven investigation without action risk

### Tasks

1. Define namespace/workload labeling strategy
2. Create initial Hook resources
3. Add event enrichment logic
4. Add incident correlation keys
5. Route Khook only to read-only agents initially
6. Store outputs in incident/event records

### Exit criteria

- supported event types trigger the intended agent
- duplicate noisy bursts do not create repeated investigations
- event-driven summaries are attached to incidents or sent to the chosen channel

## Phase 5 - Approval-gated action plane

### Objectives

- add bounded actions under governance

### Tasks

1. Build `runbook-execution-mcp`
2. Separate `remediation-executor` from investigator
3. Configure approval requirements for sensitive tools
4. Add policy service checks
5. Add rollback hooks and action journaling
6. Add operator-facing action review UX

### Exit criteria

- actions cannot execute without policy pass
- high-risk actions always require approval
- rollback instructions produced for every action class

## Phase 6 - Productization and self-service

### Objectives

- make the AI layer installable and reusable as a platform module

### Tasks

1. Discovery engine for cluster capabilities
2. Generated install overlays
3. Auto-detection of existing observability APIs/services
4. Self-service onboarding wizard
5. Compatibility matrix
6. smoke tests and uninstall flows
7. adapter model for cloud-specific event sources and ticketing systems

### Exit criteria

- install flow works for quickstart, attach, standalone, and hybrid
- discovered services can be subscribed with minimal manual work
- platform docs clearly separate automatic vs manual steps

## 14. Example resource patterns

## 14.1 Kagent install posture

- use minimal profile
- define only explicit agents
- use external PostgreSQL
- use proxy URL to gateway
- do not ship preloaded demo agents into production

## 14.2 MCP resource posture

- platform-owned MCP servers are built and deployed by kmcp
- discovery disabled when a gateway fronts them
- Kagent references only gateway-facing `RemoteMCPServer` entries

## 14.3 Agent posture

- each agent has a dedicated service account
- read-only agents cannot see write-capable tools
- action agents have very small tool sets
- prompts require evidence and confidence output
- high-risk tools use `requireApproval`

## 14.4 Khook posture

- one hook per operational domain or risk class
- prompts are structured and scoped
- initial hooks are investigation-only
- remediation hooks enabled only after validation

## 15. Validation plan

## 15.1 Functional tests

1. Human query -> incident summary
2. Human query -> blast radius analysis
3. Human query -> recent change correlation
4. Khook trigger -> agent investigation
5. Approval-gated remediation proposal
6. Approved action execution
7. Rejected action behavior
8. Gateway outage behavior
9. MCP service outage behavior
10. datastore outage behavior behind query API

## 15.2 Multi-agent behavior tests

1. CEO agent delegates to the correct manager agent for each incident class
2. manager agent invokes the correct specialist set for each workflow
3. specialist outputs are written back to the case file in the required schema
4. contradictory specialist findings are surfaced and resolved by the CEO agent
5. specialist-to-specialist invocation is blocked when not explicitly allowed
6. action-governor cannot run until investigation evidence reaches minimum
   completeness
7. remediation-executor cannot run without approval state
8. agent restart mid-workflow can resume from case-file state
9. cross-namespace agent references respect `allowedNamespaces`
10. proxy-mediated agent-to-agent routing preserves auditability

## 15.2 Safety tests

- agent attempts unsupported action
- tool with missing approval
- overbroad namespace access
- prompt injection in logs/events
- malicious or malformed tool response
- data redaction validation
- secret masking validation

## 15.3 Performance tests

- hook storm on restart bursts
- concurrent incident investigations
- gateway latency under load
- MCP fan-out limits
- Kagent controller/database contention
- token/cost budgets per namespace/team

## 15.4 Upgrade tests

- Kagent upgrade with unchanged MCP contracts
- Khook upgrade with unchanged hook contracts
- kmcp upgrade with unchanged MCPServer lifecycle
- gateway replacement with preserved MCP endpoint contract
- OpenSearch/Neo4j backend schema changes hidden behind query APIs

## 16. Operational guidance

## 16.1 What to monitor

### Kagent

- controller health
- queue depth
- database latency
- tool call latency
- agent failure rate
- approval queue length

### Khook

- events processed
- dedupe hit rate
- failed dispatches
- hook processing latency
- controller restarts

### kmcp / MCP services

- MCP server pod health
- tool error rate
- response latency
- auth failures
- gateway registration consistency

### Platform query services

- OpenSearch query latency
- Neo4j traversal latency
- trace lookup latency
- cache hit rates
- rate-limit rejects

## 16.2 SRE posture

Use SLOs for:

- investigation response latency
- event-to-summary latency
- MCP service availability
- approval-path completion time
- action execution success rate

## 17. Risks and mitigations

| Risk | Why it matters | Mitigation |
| --- | --- | --- |
| Upstream API churn | Kagent is still evolving rapidly | isolate via MCP and platform APIs; pin versions; use contract tests |
| Tool sprawl | too many tools degrade reasoning quality | small curated tool catalogs per agent |
| Direct-bypass regressions | future teams may point agents at raw stores | enforce network policy and code review rule: no DB-native clients in AI-facing components |
| Autonomous action risk | incorrect remediation can amplify incidents | read-first rollout; approval gates; bounded tool sets |
| Event noise | Khook can be flooded by low-value events | qualify triggers; enrich; dedupe; add policy filters |
| Data sensitivity | logs and graph data may contain secrets or regulated fields | redact in query APIs; mask in MCP; audit access |
| Cost / latency | multi-step agent workflows can get slow and expensive | coordinator pattern; response budgets; caching; short result schemas |

## 18. Final recommendation

Adopt the following target pattern:

### Recommended production architecture

`Khook -> Kagent -> gatewayed MCP catalog -> platform query/action APIs ->
backends`

with these explicit rules:

1. **Install Kagent in minimal mode**
2. **Run Khook only as a trigger and dispatch controller**
3. **Use kmcp to package and operate MCP services**
4. **Front MCP services with an MCP/A2A gateway for governance**
5. **Disable direct discovery on MCP services that must be reached through the
   gateway**
6. **Expose only business-level MCP tools, never raw OpenSearch or Neo4j
   queries**
7. **Implement a CEO-agent-led multi-agent mesh with manager and specialist
   tiers**
8. **Standardize inter-agent work through a platform-owned case file and A2A
   contracts**
9. **Split investigation agents from action agents**
10. **Roll out actions only behind approval gates**
11. **Treat Kagent and Khook as pluggable modules, not core platform
    dependencies**
12. **Keep datastore access behind platform-owned query services**

This satisfies:

- decoupling
- replaceability
- MCP-first access
- no direct DB querying by AI-facing components
- cloud-agnostic platform evolution
- guided and productized platform growth

## 19. Source-backed implementation notes

### User-provided inputs

- **[U1]** Attached research summary on Kagent/Khook integration patterns and
  role split
- **[U2]** Attached system instructions for cloud-agnostic, plug-and-play,
  Kubernetes-native observability documentation

### Official sources used

- **[S1]** Kagent project homepage and overview
- **[S2]** Kagent tools documentation
- **[S3]** Khook GitHub README
- **[S4]** Kagent first MCP tool guide / kmcp discovery guidance
- **[S5]** Kagent release notes - ToolServer removal and kmcp split
- **[S6]** Kagent release notes - kmcp installed by default / discovery guidance
- **[S7]** Kagent GitHub technical details
- **[S8]** Kagent agents documentation
- **[S9]** Kagent installation docs - production PostgreSQL guidance
- **[S10]** Kagent Human-in-the-Loop docs
- **[S11]** Kagent installation docs - demo vs minimal profile
- **[S12]** kmcp introduction docs
- **[S13]** kmcp controller installation docs
- **[S14]** Khook Hook configuration examples
- **[S15]** Kagent operational considerations - proxying agent-to-MCP traffic
- **[S16]** agentgateway docs for Kagent integration
- **[S17]** agentgateway project overview

## 20. Immediate implementation baseline

If this extension is started now, the best baseline is:

- Kagent minimal profile
- external PostgreSQL
- kmcp installed and used for all platform-owned MCP servers
- Khook investigation-only hooks
- gateway in front of all MCP services
- RemoteMCPServer references from Kagent to gateway endpoints only
- ops-ceo-agent plus manager and specialist agents from day one
- incident-casefile-mcp as the shared workflow state boundary
- no direct OpenSearch or Neo4j access from Kagent agents
- no autonomous remediation until after validation phase

[U1]: #user-provided-inputs
[U2]: #user-provided-inputs
[S2]: #official-sources-used
[S3]: #official-sources-used
[S4]: #official-sources-used
[S6]: #official-sources-used
[S7]: #official-sources-used
[S8]: #official-sources-used
[S14]: #official-sources-used
[S15]: #official-sources-used
[S17]: #official-sources-used
