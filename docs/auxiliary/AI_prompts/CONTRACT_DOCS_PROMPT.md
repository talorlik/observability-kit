# CONTRACT DOCUMENTATION PROMPT

SYSTEM INSTRUCTION: See source document.
USER INSTRUCTIONS: See source document.
REFERENCES: Use the planning source documents as references.
CONTEXT:
To implement the direct wiring between core platform and kagent+khook later,
I need to produce a small, explicit contract pack. Most of it is already implied
in my planning docs, but these are the concrete docs I need as implementation inputs:

- CORE_AI_BOUNDARY_CONTRACT.md
Defines the canonical flow (Khook -> Kagent -> gatewayed MCP -> platform APIs ->
backends), forbidden bypass paths, and ownership boundaries.
- CORE_AI_INTEGRATION_INTERFACE_SPEC.md
Lists every core API the AI layer can call (query/action), with request/response
shapes, auth expectations, SLOs, error semantics, and versioning rules.
- MCP_CATALOG_AND_TOOL_CONTRACTS.md
Maps business capabilities to MCP tools (incident-search, graph-analysis, etc.),
includes tool schemas, risk class, tenancy/redaction behavior, and compatibility
policy.
- AGENT_TO_CORE_COMMUNICATION_CONTRACT.md
Defines the inter-agent envelope and case-file contract used when results are
persisted and passed back to core workflows.
- KHOOK_TRIGGER_TO_AGENT_DISPATCH_SPEC.md
Exact event types, qualification/dedup rules, enrichment fields, correlation keys,
and target agent routing policy.
- GATEWAY_DISCOVERY_AND_REGISTRATION_SPEC.md
How MCP services are registered/federated, when direct discovery is disabled, and
how RemoteMCPServer entries are wired.
- SECURITY_GOVERNANCE_AND_APPROVAL_MATRIX.md
Service account mapping, RBAC/namespace boundaries, tool risk classes, approval
prerequisites, audit required fields, and deny conditions.
- INTEGRATION_TEST_AND_RELEASE_GATES.md
Wiring-specific test matrix: happy path, bypass prevention, outage/degraded modes,
schema compatibility, and release blockers.
- OPERATIONS_RUNBOOK_CORE_AI_INTEGRATION.md
Install order, rollback paths, failure triage, validation commands, and day-2
operations for the integrated boundary.
TASKS:
- Produce each of these documents in full.
- Create them 1 by 1 and so as not to overwhelm your context limit.
- Ask me to continue to the next document after completing each one until you're
done with all of them.
