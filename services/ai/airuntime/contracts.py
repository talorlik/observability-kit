"""Embedded contract constants for the AI/MCP runtime.

Every constant block names its source file in the comment above it;
the runtime never parses YAML. scripts/ci/validate_ai_activation.sh
cross-checks these values against the governing contracts:

- CI-cross-checked verbatim: MCP catalog, tool response required
  fields, gateway discovery (heartbeat/timeout/failover), tool risk
  classification, approval timeout rules, escalation chain, dedupe and
  burst bounds, hook catalog, required scopes, restricted-domain deny
  list, casefile required fields, audit required fields, and - with
  the agent-binding enforcement - ROLE_BINDINGS, AGENT_TOOL_BINDINGS,
  DEFAULT_TOOL_POLICY, ACTION_PRECONDITIONS (plus failure behavior),
  and REQUIRED_APPROVAL_FIELDS.
- Derived, not a contract literal: TOOL_TO_SERVICE is a routing map
  computed from the catalog plus the risk classification (two
  classified tool ids do not equal their host service's catalog tool
  name).
- Mirrored vocabulary: MASK_FIELDS mirrors the redaction validator's
  masking vocabulary rather than a YAML list in
  TENANCY_REDACTION_RULES_V1.yaml.
"""

from __future__ import annotations

from typing import Any

# --- contracts/mcp/MCP_CATALOG_V1.yaml -------------------------------
# The seven catalog services, keyed by service name. Registration mode
# for all of them is explicit (the gateway registers each at startup).
MCP_CATALOG: dict[str, dict[str, str]] = {
    "incident-search-mcp": {
        "tool": "incident-search",
        "owner": "platform-observability",
        "version": "v1",
    },
    "graph-analysis-mcp": {
        "tool": "graph-analysis",
        "owner": "platform-observability",
        "version": "v1",
    },
    "trace-investigation-mcp": {
        "tool": "trace-investigation",
        "owner": "platform-observability",
        "version": "v1",
    },
    "metrics-correlation-mcp": {
        "tool": "metrics-correlation",
        "owner": "platform-observability",
        "version": "v1",
    },
    "change-intelligence-mcp": {
        "tool": "change-intelligence",
        "owner": "platform-observability",
        "version": "v1",
    },
    "runbook-execution-mcp": {
        "tool": "runbook-execution",
        "owner": "platform-ai-runtime",
        "version": "v1",
    },
    "incident-casefile-mcp": {
        "tool": "incident-casefile",
        "owner": "platform-ai-runtime",
        "version": "v1",
    },
}

# Derived routing map: classified tool id prefix -> catalog service.
# Derived from MCP_CATALOG plus TOOL_RISK_CLASSES: the casefile service
# exposes read/update operations as distinct classified tools, and the
# runbook-execution service hosts both write-path tools.
TOOL_TO_SERVICE: dict[str, str] = {
    "incident-search": "incident-search-mcp",
    "graph-analysis": "graph-analysis-mcp",
    "trace-investigation": "trace-investigation-mcp",
    "metrics-correlation": "metrics-correlation-mcp",
    "change-intelligence": "change-intelligence-mcp",
    "incident-casefile.read": "incident-casefile-mcp",
    "incident-casefile.update": "incident-casefile-mcp",
    "runbook-plan": "runbook-execution-mcp",
    "remediation-execute": "runbook-execution-mcp",
}

# --- contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json ----------------------
TOOL_RESPONSE_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "summary",
    "structured_data",
    "evidence_handles",
    "confidence",
    "time_window",
    "safety_class",
    "next_recommended_tools",
)

SAFETY_CLASSES: tuple[str, ...] = (
    "read.safe",
    "read.sensitive",
    "write.low-risk",
    "write.high-risk",
    "write.critical",
)

# --- contracts/mcp/GATEWAY_DISCOVERY_CONTRACT_V1.yaml ----------------
HEARTBEAT_INTERVAL_SECONDS: int = 30
UNHEALTHY_THRESHOLD_MISSED_HEARTBEATS: int = 3
DEFAULT_REQUEST_TIMEOUT_MS: int = 5000
UPPER_BOUND_REQUEST_TIMEOUT_MS: int = 30000
ON_TIMEOUT: str = "deny"
FAILOVER_FALLBACK_MODE: str = "deny"
RETRY_ATTEMPTS: int = 0

# --- contracts/policy/TOOL_RISK_CLASSIFICATION_V1.yaml ---------------
TOOL_RISK_CLASSES: dict[str, str] = {
    "incident-search.v1": "read.safe",
    "graph-analysis.v1": "read.sensitive",
    "trace-investigation.v1": "read.sensitive",
    "metrics-correlation.v1": "read.safe",
    "change-intelligence.v1": "read.sensitive",
    "incident-casefile.read.v1": "read.sensitive",
    "incident-casefile.update.v1": "write.low-risk",
    "runbook-plan.v1": "write.high-risk",
    "remediation-execute.v1": "write.critical",
}
UNCLASSIFIED_TOOL_BEHAVIOR: str = "deny"

# --- contracts/policy/APPROVAL_FLOW_V1.yaml --------------------------
APPROVAL_TIMEOUT_RULES: dict[str, dict[str, Any]] = {
    "write.high-risk": {
        "pending_timeout_minutes": 60,
        "warning_threshold_minutes": 30,
        "on_timeout": "deny-and-escalate",
    },
    "write.critical": {
        "pending_timeout_minutes": 120,
        "warning_threshold_minutes": 60,
        "on_timeout": "deny-and-escalate",
    },
}

REQUIRED_APPROVAL_FIELDS: dict[str, tuple[str, ...]] = {
    "write.high-risk": ("approval_id", "approver", "decision", "decided_at"),
    "write.critical": (
        "approval_id",
        "approver",
        "decision",
        "decided_at",
        "change_ticket",
    ),
}

# (role, sla_minutes) in escalation order.
ESCALATION_CHAIN: tuple[tuple[str, int], ...] = (
    ("oncall-sre", 30),
    ("incident-commander", 60),
    ("platform-director", 120),
)
ON_UNRESOLVED_AFTER_CHAIN: str = "deny"
NOTIFY_CHANNELS: tuple[str, ...] = (
    "audit-log",
    "paging-service",
    "casefile-comment",
)

# Approval preconditions per risk class (write classes only; read
# classes never require human approval).
APPROVAL_PRECONDITIONS: dict[str, dict[str, bool]] = {
    "write.low-risk": {"requires_human_approval": False},
    "write.high-risk": {"requires_human_approval": True},
    "write.critical": {
        "requires_human_approval": True,
        "requires_manual_workflow": True,
        "requires_change_ticket": True,
    },
}

# --- contracts/policy/ACTION_PRECONDITIONS_V1.yaml -------------------
ACTION_PRECONDITIONS: dict[str, dict[str, Any]] = {
    "incident-casefile.update.v1": {"approval": "not-required"},
    "runbook-plan.v1": {
        "approval": "approved",
        "requires_rollback_plan": True,
    },
    "remediation-execute.v1": {
        "approval": "approved",
        "requires_rollback_plan": True,
        "requires_change_ticket": True,
    },
}
PRECONDITION_FAILURE_BEHAVIOR: dict[str, str] = {
    "on_missing_precondition": "block",
    "on_policy_error": "deny",
    "on_approval_service_unavailable": "deny",
}

# --- contracts/mcp/TENANCY_REDACTION_RULES_V1.yaml -------------------
REQUIRED_SCOPES: tuple[str, ...] = ("namespace", "tenant", "team")
MASK_FIELDS: tuple[str, ...] = ("secret", "api_key", "password", "token")
RESTRICTED_DOMAIN_DENY_LIST: tuple[str, ...] = (
    "pii.raw",
    "credentials",
    "key_material",
)
MAX_TIME_WINDOW_HOURS: int = 24
MAX_RESPONSE_ITEMS: int = 500
DENY_ON_SCOPE_MISMATCH: bool = True
INCLUDE_REDACTION_METADATA: bool = True

# --- triggers/khook/hooks/HOOK_CATALOG_V1.yaml -----------------------
# hook id -> (object kind, event reason, severity)
HOOKS: dict[str, tuple[str, str, str]] = {
    "pod-restart": ("Pod", "Restarted", "high"),
    "oom-kill": ("Pod", "OOMKilled", "critical"),
    "probe-failed": ("Pod", "Unhealthy", "medium"),
    "pod-pending": ("Pod", "FailedScheduling", "medium"),
    "node-not-ready": ("Node", "NodeNotReady", "critical"),
}

REQUIRED_EVENT_FIELDS: tuple[str, ...] = (
    "event_id",
    "event_timestamp",
    "cluster",
    "namespace",
    "object_kind",
    "object_name",
    "reason",
    "message",
)

# --- triggers/khook/policies/DEDUPE_BURST_CONTROL_V1.yaml ------------
DEDUPE_KEY_FIELDS: tuple[str, ...] = (
    "incident_correlation_key",
    "reason",
    "object_kind",
    "object_name",
)
DEDUPE_WINDOW_SECONDS: int = 300
BURST_MAX_PER_WINDOW: int = 10
BURST_WINDOW_SECONDS: int = 60

# --- triggers/khook/policies/EVENT_ENRICHMENT_V1.yaml ----------------
# Stable sha256 hash over these fields, in this order.
CORRELATION_KEY_FIELDS: tuple[str, ...] = (
    "cluster",
    "namespace",
    "object_kind",
    "object_name",
    "reason",
)

# --- agents/catalog/AGENT_CATALOG_V1.yaml +
#     agents/policies/TOOL_BINDINGS_V1.yaml --------------------------
CEO_AGENT: str = "ops-ceo-agent"
INVESTIGATION_MANAGER: str = "investigation-manager"
CEO_ALLOWED_MCP_TOOLS: tuple[str, ...] = (
    "incident-casefile.read.v1",
    "incident-casefile.update.v1",
    "approval-status.v1",
)
# Read specialists in investigation-plan dispatch order; the
# evidence-summarizer has no tool binding (pure synthesis).
SPECIALIST_TOOLS: dict[str, str] = {
    "incident-investigator": "incident-search.v1",
    "trace-analyst": "trace-investigation.v1",
    "metrics-correlator": "metrics-correlation.v1",
    "graph-analyst": "graph-analysis.v1",
    "change-correlator": "change-intelligence.v1",
}
EVIDENCE_SUMMARIZER: str = "evidence-summarizer"
ALLOWED_COMMUNICATION_EDGES: tuple[tuple[str, str], ...] = (
    ("ceo", "manager"),
    ("manager", "specialist"),
    ("ceo", "specialist"),
)
DENIED_COMMUNICATION_EDGES: tuple[tuple[str, str], ...] = (
    ("specialist", "specialist"),
)

# --- agents/policies/TOOL_BINDINGS_V1.yaml ---------------------------
# default_tool_policy: any caller or tool without an explicit binding
# is denied. Role classes bound risk exposure; agent bindings pin the
# exact tool ids each agent may invoke.
DEFAULT_TOOL_POLICY: str = "deny"

ROLE_BINDINGS: dict[str, dict[str, Any]] = {
    "ceo": {
        "allow_risk_classes": (
            "read.safe", "read.sensitive", "write.low-risk",
        ),
        "deny_risk_classes": ("write.high-risk", "write.critical"),
    },
    "manager": {
        "allow_risk_classes": (
            "read.safe", "read.sensitive", "write.low-risk",
        ),
        "deny_risk_classes": ("write.high-risk", "write.critical"),
    },
    "specialist_read_only": {
        "allow_risk_classes": (
            "read.safe", "read.sensitive", "write.low-risk",
        ),
        "deny_risk_classes": ("write.high-risk", "write.critical"),
    },
    "specialist_action": {
        "allow_risk_classes": (
            "write.high-risk", "write.critical", "write.low-risk",
        ),
        "deny_risk_classes": (),
        "require_approval": True,
    },
}

AGENT_TOOL_BINDINGS: dict[str, dict[str, Any]] = {
    "ops-ceo-agent": {
        "class": "ceo",
        "tools": (
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
            "approval-status.v1",
        ),
    },
    "triage-director": {
        "class": "manager",
        "tools": (
            "incident-search.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "investigation-manager": {
        "class": "manager",
        "tools": (
            "incident-search.v1",
            "change-intelligence.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "action-governor": {
        "class": "manager",
        "tools": (
            "approval-status.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "incident-investigator": {
        "class": "specialist_read_only",
        "tools": (
            "incident-search.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "logs-analyst": {
        "class": "specialist_read_only",
        "tools": (
            "incident-search.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "trace-analyst": {
        "class": "specialist_read_only",
        "tools": (
            "trace-investigation.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "metrics-correlator": {
        "class": "specialist_read_only",
        "tools": (
            "metrics-correlation.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "graph-analyst": {
        "class": "specialist_read_only",
        "tools": (
            "graph-analysis.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "change-correlator": {
        "class": "specialist_read_only",
        "tools": (
            "change-intelligence.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "evidence-summarizer": {
        "class": "specialist_read_only",
        "tools": (
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "runbook-planner": {
        "class": "specialist_action",
        "tools": (
            "runbook-plan.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
    "remediation-executor": {
        "class": "specialist_action",
        "tools": (
            "remediation-execute.v1",
            "incident-casefile.read.v1",
            "incident-casefile.update.v1",
        ),
    },
}

# --- contracts/ai/PROTOCOL_EDGES_V1.yaml -----------------------------
EDGE_VERSION: str = "v1"
KHOOK_TO_KAGENT_FIELDS: tuple[str, ...] = (
    "edge_version",
    "correlation_id",
    "event_type",
    "source_namespace",
    "risk_class",
    "payload",
)
AGENT_TO_AGENT_FIELDS: tuple[str, ...] = (
    "edge_version",
    "from_agent",
    "to_agent",
    "objective",
    "findings",
    "evidence_handles",
    "confidence",
)
AGENT_TO_MCP_FIELDS: tuple[str, ...] = (
    "edge_version",
    "caller_agent",
    "tool",
    "tool_version",
    "tenant_scope",
    "input",
)

# --- contracts/ai/CASEFILE_SCHEMA_V1.json ----------------------------
CASEFILE_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "case_id",
    "status",
    "incident_context",
    "agent_outputs",
    "evidence_handles",
    "approval_state",
    "action_journal",
    "lineage",
    "created_at",
    "updated_at",
)
CASEFILE_STATUSES: tuple[str, ...] = (
    "open",
    "triaging",
    "investigating",
    "awaiting-approval",
    "executing",
    "resolved",
    "closed",
    "rejected",
)
ACTION_JOURNAL_OUTCOMES: tuple[str, ...] = (
    "executed",
    "blocked",
    "rolled-back",
    "failed",
)

# --- contracts/policy/AUDIT_EVENT_SCHEMA_V1.json ---------------------
AUDIT_REQUIRED_FIELDS: tuple[str, ...] = (
    "schema_version",
    "invoker_identity",
    "agent_identity",
    "agent_version",
    "tool_call",
    "tool_parameters_redacted",
    "evidence_handles",
    "policy_decision",
    "approval_decision",
    "target_resources",
    "final_action_outcome",
    "latency_ms",
    "cost",
    "event_time",
)
POLICY_DECISIONS: tuple[str, ...] = ("allow", "deny", "conditional")
APPROVAL_DECISIONS: tuple[str, ...] = ("approved", "rejected", "not-required")
FINAL_ACTION_OUTCOMES: tuple[str, ...] = (
    "executed",
    "blocked",
    "rolled-back",
    "failed",
)
COST_REQUIRED_FIELDS: tuple[str, ...] = ("tokens", "estimated_usd")

# --- contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml ------------
MODEL_REQUEST_FIELDS: tuple[str, ...] = (
    "provider",
    "model_ref",
    "tenant_id",
    "redaction_profile",
    "casefile_id",
    "max_output_tokens",
)
MODEL_RESPONSE_FIELDS: tuple[str, ...] = (
    "provider",
    "model_ref",
    "content",
    "usage",
    "stop_reason",
)
MODEL_USAGE_FIELDS: tuple[str, ...] = ("input_tokens", "output_tokens")
REHEARSAL_PROVIDER: str = "local-stub"
REFERENCE_PROVIDER: str = "anthropic-reference"
