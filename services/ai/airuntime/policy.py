"""Governance engine: risk classification, approvals, preconditions,
redaction, response validation, and audit event construction.

Used by both the kagent controller (approval lifecycle, audit) and the
MCP gateway (routing decisions, redaction, envelope validation). All
timestamps are ISO-8601 strings; callers supply the clock, so timeout
evaluation is testable against a fixed as-of time.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from airuntime.contracts import (
    ACTION_PRECONDITIONS,
    AGENT_TOOL_BINDINGS,
    APPROVAL_DECISIONS,
    APPROVAL_PRECONDITIONS,
    APPROVAL_TIMEOUT_RULES,
    AUDIT_REQUIRED_FIELDS,
    DEFAULT_TOOL_POLICY,
    ESCALATION_CHAIN,
    FINAL_ACTION_OUTCOMES,
    MASK_FIELDS,
    NOTIFY_CHANNELS,
    ON_UNRESOLVED_AFTER_CHAIN,
    POLICY_DECISIONS,
    REQUIRED_APPROVAL_FIELDS,
    RESTRICTED_DOMAIN_DENY_LIST,
    ROLE_BINDINGS,
    SAFETY_CLASSES,
    TOOL_RESPONSE_REQUIRED_FIELDS,
    TOOL_RISK_CLASSES,
)

REDACTION_MASK = "***redacted***"


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def classify_tool(tool_id: str) -> str | None:
    return TOOL_RISK_CLASSES.get(tool_id)


def policy_decision(
    tool_id: str, caller_class_allows: bool
) -> tuple[str, str]:
    """(decision, reason). Unclassified tools deny per contract."""
    risk_class = classify_tool(tool_id)
    if risk_class is None:
        return "deny", f"unclassified tool {tool_id}: default deny"
    if not caller_class_allows:
        return "deny", f"caller not permitted to invoke {tool_id}"
    return "allow", f"{tool_id} classified {risk_class}"


def check_agent_binding(
    caller_agent: str, tool_id: str, risk_class: str
) -> tuple[bool, str]:
    """Enforce TOOL_BINDINGS_V1: default_tool_policy is deny.

    Deny order: unknown caller, tool not in the caller's binding, risk
    class in the caller class's deny set. The tool list and the risk
    deny set are both checked because they guard different drift: a
    tool could be reclassified upward without the binding changing.
    """
    binding = AGENT_TOOL_BINDINGS.get(caller_agent)
    if binding is None:
        return False, (
            f"unknown caller {caller_agent!r}: default tool policy is "
            f"{DEFAULT_TOOL_POLICY}"
        )
    if tool_id not in binding["tools"]:
        return False, (
            f"{caller_agent} has no binding for {tool_id}: default "
            f"tool policy is {DEFAULT_TOOL_POLICY}"
        )
    role = ROLE_BINDINGS[binding["class"]]
    if risk_class in role.get("deny_risk_classes", ()):
        return False, (
            f"{caller_agent} class {binding['class']} denies risk "
            f"class {risk_class}"
        )
    return True, (
        f"{caller_agent} ({binding['class']}) is bound to {tool_id}"
    )


def approval_required(risk_class: str) -> bool:
    """Read classes never require approval; write classes follow the
    approval-flow precondition table."""
    return APPROVAL_PRECONDITIONS.get(risk_class, {}).get(
        "requires_human_approval", False
    )


def new_approval(
    casefile_id: str,
    tool: str,
    risk_class: str,
    requested_by: str,
    now_iso: str,
) -> dict[str, Any]:
    rules = APPROVAL_TIMEOUT_RULES.get(risk_class)
    if rules is None:
        raise ValueError(
            f"risk class {risk_class!r} has no approval timeout rules; "
            f"approvals exist only for {sorted(APPROVAL_TIMEOUT_RULES)}"
        )
    requested_at = _parse_iso(now_iso)
    deadline_at = requested_at + timedelta(
        minutes=rules["pending_timeout_minutes"]
    )
    warning_at = requested_at + timedelta(
        minutes=rules["warning_threshold_minutes"]
    )
    # Escalation clock: role i escalates at the pending deadline plus
    # the cumulative SLA minutes of the roles BEFORE it. The first role
    # is paged the moment the approval expires; each later role gets
    # the previous role's SLA to respond before the chain moves on.
    chain: list[dict[str, Any]] = []
    offset = 0
    for role, sla_minutes in ESCALATION_CHAIN:
        escalate_at = deadline_at + timedelta(minutes=offset)
        chain.append(
            {
                "role": role,
                "sla_minutes": sla_minutes,
                "escalate_at": escalate_at.isoformat(),
            }
        )
        offset += sla_minutes
    return {
        "approval_id": uuid.uuid4().hex,
        "casefile_id": casefile_id,
        "tool": tool,
        "risk_class": risk_class,
        "requested_by": requested_by,
        "requested_at": requested_at.isoformat(),
        "deadline_at": deadline_at.isoformat(),
        "warning_at": warning_at.isoformat(),
        "state": "pending",
        "approver": None,
        "decision": None,
        "decided_at": None,
        "escalation": {
            "chain": chain,
            "notify_channels": list(NOTIFY_CHANNELS),
            "on_unresolved": ON_UNRESOLVED_AFTER_CHAIN,
        },
    }


def decide_approval(
    approval: dict[str, Any],
    approver: str,
    decision: str,
    decided_at: str,
    change_ticket: str | None = None,
) -> dict[str, Any]:
    if approval["state"] != "pending":
        raise ValueError(
            f"approval {approval['approval_id']} is {approval['state']}, "
            f"not pending"
        )
    # The requester cannot be its own approver: a human surrogate must
    # be a distinct identity or the gate is theater.
    if approver == approval["requested_by"]:
        raise ValueError(
            f"self-approval denied: {approver} requested this approval"
        )
    if decision not in ("approved", "rejected"):
        raise ValueError(f"decision must be approved|rejected, got {decision!r}")
    if _parse_iso(decided_at) > _parse_iso(approval["deadline_at"]):
        raise ValueError(
            f"decision at {decided_at} is past the pending deadline "
            f"{approval['deadline_at']}"
        )
    if (
        approval["risk_class"] == "write.critical"
        and decision == "approved"
        and not change_ticket
    ):
        raise ValueError(
            "write.critical approval requires a change_ticket"
        )
    updated = dict(approval)
    updated.update(
        state=decision,
        approver=approver,
        decision=decision,
        decided_at=decided_at,
    )
    if change_ticket is not None:
        updated["change_ticket"] = change_ticket
    # APPROVAL_FLOW_V1 required_approval_fields: the decided record
    # must carry every field its risk class demands. change_ticket is
    # an execution precondition, so a rejection (which never executes)
    # is exempt from it - the identity/decision fields are not.
    required = REQUIRED_APPROVAL_FIELDS.get(approval["risk_class"], ())
    if decision != "approved":
        required = tuple(f for f in required if f != "change_ticket")
    missing = [f for f in required if not updated.get(f)]
    if missing:
        raise ValueError(
            f"decided approval missing required fields for "
            f"{approval['risk_class']}: {missing}"
        )
    return updated


def evaluate_timeout(
    approval: dict[str, Any], as_of_iso: str
) -> dict[str, Any]:
    """Evaluate the contract timeout rules against a supplied clock.

    Returns status not_due | warning | expired. The rehearsal drives
    this with a simulated as-of time; the rules themselves are the real
    APPROVAL_FLOW_V1 rules, not a test shortcut.
    """
    if approval["state"] != "pending":
        return {
            "status": "not-pending",
            "state": approval["state"],
            "as_of": as_of_iso,
        }
    as_of = _parse_iso(as_of_iso)
    warning_at = _parse_iso(approval["warning_at"])
    deadline_at = _parse_iso(approval["deadline_at"])
    if as_of < warning_at:
        return {"status": "not_due", "as_of": as_of_iso}
    if as_of < deadline_at:
        return {
            "status": "warning",
            "as_of": as_of_iso,
            "warning_at": approval["warning_at"],
            "deadline_at": approval["deadline_at"],
        }
    rules = APPROVAL_TIMEOUT_RULES[approval["risk_class"]]
    chain = approval["escalation"]["chain"]
    escalation_events = [
        {
            "role": entry["role"],
            "escalated_at": entry["escalate_at"],
            "channels": list(NOTIFY_CHANNELS),
        }
        for entry in chain
        if _parse_iso(entry["escalate_at"]) <= as_of
    ]
    past_whole_chain = len(escalation_events) == len(chain)
    return {
        "status": "expired",
        "state": "expired",
        "outcome": rules["on_timeout"],
        "as_of": as_of_iso,
        "deadline_at": approval["deadline_at"],
        "escalation_events": escalation_events,
        # Past the whole chain with no decision -> the contract's
        # final answer is deny.
        "final_denial": past_whole_chain,
        "on_unresolved": ON_UNRESOLVED_AFTER_CHAIN,
    }


def check_action_preconditions(
    tool_id: str, context: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Enforce ACTION_PRECONDITIONS_V1 for the three write-path tools.

    context keys: policy_decision, approval (dict|None),
    rollback_plan_present, change_ticket_present, valid_target.
    Any missing precondition blocks (on_missing_precondition: block).
    """
    preconditions = ACTION_PRECONDITIONS.get(tool_id)
    if preconditions is None:
        return False, [f"no action preconditions defined for {tool_id}: deny"]
    blocked: list[str] = []
    if context.get("policy_decision") != "allow":
        blocked.append("policy_decision is not allow")
    if not context.get("valid_target", True):
        blocked.append("target resource failed validation")
    if preconditions["approval"] == "approved":
        approval = context.get("approval")
        if not approval:
            blocked.append("approval record missing")
        elif approval.get("state") != "approved":
            blocked.append(
                f"approval state is {approval.get('state')!r}, "
                f"not approved"
            )
    if preconditions.get("requires_rollback_plan") and not context.get(
        "rollback_plan_present"
    ):
        blocked.append("rollback plan missing")
    if preconditions.get("requires_change_ticket") and not context.get(
        "change_ticket_present"
    ):
        blocked.append("change ticket missing")
    return (not blocked), blocked


def redact(structured: Any) -> tuple[Any, dict[str, Any]]:
    """Field-level masking plus restricted-domain record denial.

    Values of MASK_FIELDS keys are replaced with the mask; any dict
    carrying key "domain" whose value is on the restricted deny list is
    dropped entirely (a masked secret is still a record; a restricted
    domain must not appear at all).
    """
    masked_fields: list[str] = []
    denied_domains: list[str] = []
    _dropped = object()  # sentinel: parent removes this node

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if node.get("domain") in RESTRICTED_DOMAIN_DENY_LIST:
                denied_domains.append(node["domain"])
                return _dropped
            result: dict[str, Any] = {}
            for key, value in node.items():
                if key in MASK_FIELDS:
                    masked_fields.append(key)
                    result[key] = REDACTION_MASK
                    continue
                child = walk(value)
                if child is not _dropped:
                    result[key] = child
            return result
        if isinstance(node, list):
            children = []
            for item in node:
                child = walk(item)
                if child is not _dropped:
                    children.append(child)
            return children
        return node

    redacted = walk(structured)
    if redacted is _dropped:
        redacted = None
    metadata = {
        "masked_fields": masked_fields,
        "denied_domains": denied_domains,
        "field_level_redaction": True,
        "secret_masking": True,
    }
    return redacted, metadata


def validate_tool_response(payload: dict[str, Any]) -> list[str]:
    """Violations of TOOL_RESPONSE_SCHEMA_V1; empty list means valid."""
    violations = [
        f"missing envelope field: {f}"
        for f in TOOL_RESPONSE_REQUIRED_FIELDS
        if f not in payload
    ]
    if "confidence" in payload:
        confidence = payload["confidence"]
        if not isinstance(confidence, (int, float)) or isinstance(
            confidence, bool
        ) or not (0.0 <= float(confidence) <= 1.0):
            violations.append(
                f"confidence must be a number in [0,1], got {confidence!r}"
            )
    if "safety_class" in payload and payload["safety_class"] not in SAFETY_CLASSES:
        violations.append(
            f"safety_class {payload['safety_class']!r} not in contract enum"
        )
    if "time_window" in payload:
        window = payload["time_window"]
        if not isinstance(window, dict) or not window.get("start") or not window.get("end"):
            violations.append("time_window must carry start and end")
    return violations


def build_audit_event(
    invoker_identity: str,
    agent_identity: str,
    tool_call: str,
    tool_parameters_redacted: dict[str, Any],
    policy_decision: str,
    approval_decision: str,
    final_action_outcome: str,
    latency_ms: int,
    event_time: str,
    agent_version: str = "v1",
    evidence_handles: list[str] | None = None,
    target_resources: list[str] | None = None,
    tokens: int = 0,
    estimated_usd: float = 0.0,
) -> dict[str, Any]:
    """All 14 AUDIT_EVENT_SCHEMA_V1 fields, enums validated loudly."""
    if policy_decision not in POLICY_DECISIONS:
        raise ValueError(f"invalid policy_decision {policy_decision!r}")
    if approval_decision not in APPROVAL_DECISIONS:
        raise ValueError(f"invalid approval_decision {approval_decision!r}")
    if final_action_outcome not in FINAL_ACTION_OUTCOMES:
        raise ValueError(
            f"invalid final_action_outcome {final_action_outcome!r}"
        )
    event = {
        "schema_version": "v1",
        "invoker_identity": invoker_identity,
        "agent_identity": agent_identity,
        "agent_version": agent_version,
        "tool_call": tool_call,
        "tool_parameters_redacted": tool_parameters_redacted,
        "evidence_handles": evidence_handles or [],
        "policy_decision": policy_decision,
        "approval_decision": approval_decision,
        "target_resources": target_resources or [],
        "final_action_outcome": final_action_outcome,
        "latency_ms": int(latency_ms),
        "cost": {"tokens": int(tokens), "estimated_usd": float(estimated_usd)},
        "event_time": event_time,
    }
    missing = [f for f in AUDIT_REQUIRED_FIELDS if f not in event]
    if missing:
        raise AssertionError(f"audit event missing fields: {missing}")
    return event
