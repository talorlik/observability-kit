"""Approval-record validation for destructive transitions.

Validates approval records against contracts/policy/APPROVAL_FLOW_V1.yaml
(Batch 20 Task 4):

- required_approval_fields per risk class (preconditions block, restated
  by the API contract's ApprovalRecordHighRisk / ApprovalRecordCritical
  schemas): write.high-risk requires approval_id, approver, decision,
  decided_at; write.critical additionally requires change_ticket. The
  decision must be an approval.
- timeout_rules: pending_timeout_minutes bounds the life of an approval
  relative to decided_at (60 minutes for write.high-risk, 120 for
  write.critical). A destructive request arriving after the window is a
  timed-out approval and is denied. The API contract fixes the mapping:
  "missing, invalid, expired, or timed-out approval" maps to error_code
  approval-required or approval-invalid - there is no separate timeout
  error code, so a timeout raises ApprovalInvalid with a precise
  message. on_timeout deny-and-escalate plus requires_audit_event: the
  raised error carries the escalation directive in its message and
  details, and the service's emit_audit_record_on_denial gate persists
  it in the denial audit record (the audit-log escalation channel).
- escalation_rules: the default_escalation_chain, the deny outcome when
  the chain is exhausted (on_unresolved_after_chain: deny), the notify
  channels, and escalation_audit_event_required are attached verbatim
  to every timeout denial via escalation_directive(). The contract
  defines escalation as a flow, not as extra approval-record fields
  (the API record schemas are additionalProperties: false), so the
  resulting record requirement after a timeout is a fresh approval
  record decided within the window - validated by the same rules.

validate_approval's signature is stable: service.py calls it without a
now argument, and now=None means the current UTC time.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from tenantctl.models import (
    ApprovalInvalid,
    ApprovalRecord,
    ApprovalRequired,
    DATETIME_PATTERN,
)

RISK_HIGH = "write.high-risk"
RISK_CRITICAL = "write.critical"

# required_approval_fields per risk class, verbatim from
# contracts/policy/APPROVAL_FLOW_V1.yaml.
REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    RISK_HIGH: ("approval_id", "approver", "decision", "decided_at"),
    RISK_CRITICAL: (
        "approval_id",
        "approver",
        "decision",
        "decided_at",
        "change_ticket",
    ),
}

# timeout_rules per risk class, verbatim from
# contracts/policy/APPROVAL_FLOW_V1.yaml (write.low-risk has
# pending_timeout_minutes 0 / on_timeout not-applicable and never
# reaches this module because it requires no human approval).
PENDING_TIMEOUT_MINUTES: dict[str, int] = {
    RISK_HIGH: 60,
    RISK_CRITICAL: 120,
}
WARNING_THRESHOLD_MINUTES: dict[str, int] = {
    RISK_HIGH: 30,
    RISK_CRITICAL: 60,
}
ON_TIMEOUT = "deny-and-escalate"
TIMEOUT_REQUIRES_AUDIT_EVENT = True
# write.critical timeouts additionally require a change-management
# callback (timeout_rules.write.critical
# .requires_change_management_callback).
REQUIRES_CHANGE_MANAGEMENT_CALLBACK: dict[str, bool] = {
    RISK_HIGH: False,
    RISK_CRITICAL: True,
}

# escalation_rules, verbatim from contracts/policy/APPROVAL_FLOW_V1.yaml.
ESCALATION_CHAIN: tuple[dict[str, Any], ...] = (
    {"role": "oncall-sre", "sla_minutes": 30},
    {"role": "incident-commander", "sla_minutes": 60},
    {"role": "platform-director", "sla_minutes": 120},
)
ON_UNRESOLVED_AFTER_CHAIN = "deny"
ESCALATION_NOTIFY_CHANNELS: tuple[str, ...] = (
    "audit-log",
    "paging-service",
    "casefile-comment",
)
ESCALATION_AUDIT_EVENT_REQUIRED = True


def escalation_directive(
    risk_class: str | None = None,
) -> dict[str, Any]:
    """Machine-readable escalation directive (escalation_rules).

    Attached to every timeout denial so the denial audit record (the
    audit-log notify channel, escalation_audit_event_required) carries
    the contract's escalation semantics. The paging-service and
    casefile-comment notifications are dispatched by the surrounding
    AI/MCP runtime, not by this repository-only control plane.
    """
    directive: dict[str, Any] = {
        "on_timeout": ON_TIMEOUT,
        "escalation_chain": [dict(step) for step in ESCALATION_CHAIN],
        "on_unresolved_after_chain": ON_UNRESOLVED_AFTER_CHAIN,
        "notify_channels": list(ESCALATION_NOTIFY_CHANNELS),
        "escalation_audit_event_required": (
            ESCALATION_AUDIT_EVENT_REQUIRED
        ),
    }
    if risk_class is not None:
        directive["requires_change_management_callback"] = (
            REQUIRES_CHANGE_MANAGEMENT_CALLBACK.get(risk_class, False)
        )
    return directive


def _parse_decided_at(decided_at: str) -> datetime:
    """Parse decided_at as RFC 3339, normalized to UTC.

    The regex gate keeps the accepted shapes aligned with the API
    contract's date-time format; fromisoformat then rejects values that
    match the shape but are not real timestamps (month 13 and the
    like). Both failure modes are ApprovalInvalid.
    """
    if not DATETIME_PATTERN.match(decided_at):
        raise ApprovalInvalid(
            "approval decided_at must be an RFC 3339 date-time"
        )
    try:
        parsed = datetime.fromisoformat(
            decided_at.replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ApprovalInvalid(
            f"approval decided_at is not a valid RFC 3339 date-time: "
            f"{decided_at!r}"
        ) from error
    return parsed.astimezone(timezone.utc)


def _check_timeout(
    approval_id: str,
    decided_at_raw: str,
    decided_at: datetime,
    risk_class: str,
    reference: datetime,
) -> None:
    """Enforce timeout_rules and, on timeout, escalation_rules.

    The approval is valid while its age (reference - decided_at) is
    within pending_timeout_minutes, boundary inclusive: the timeout
    fires only once the window has elapsed. A decided_at after the
    reference time is inconsistent (the decision cannot postdate its
    use) and is rejected as invalid rather than treated as ageless.
    """
    if decided_at > reference:
        raise ApprovalInvalid(
            f"approval {approval_id!r} decided_at {decided_at_raw!r} "
            f"is later than the evaluation time "
            f"{reference.isoformat()}; a decision cannot postdate its "
            f"use"
        )
    window_minutes = PENDING_TIMEOUT_MINUTES[risk_class]
    window = timedelta(minutes=window_minutes)
    age = reference - decided_at
    if age <= window:
        return
    age_minutes = age.total_seconds() / 60.0
    chain = " -> ".join(
        str(step["role"]) for step in ESCALATION_CHAIN
    )
    raise ApprovalInvalid(
        f"approval {approval_id!r} timed out: decided_at "
        f"{decided_at_raw!r} is {age_minutes:.1f} minutes old, past "
        f"the {window_minutes}-minute pending timeout for {risk_class} "
        f"(contracts/policy/APPROVAL_FLOW_V1.yaml timeout_rules); "
        f"on_timeout {ON_TIMEOUT}: the request is denied and "
        f"escalated through the default escalation chain ({chain}), "
        f"unresolved-after-chain is denied, and a fresh approval "
        f"decided within the window is required",
        details={
            "risk_class": risk_class,
            "pending_timeout_minutes": window_minutes,
            "warning_threshold_minutes": (
                WARNING_THRESHOLD_MINUTES[risk_class]
            ),
            "decided_at": decided_at_raw,
            "evaluated_at": reference.isoformat(),
            **escalation_directive(risk_class),
        },
    )


def validate_approval(
    payload: Mapping[str, Any] | None,
    risk_class: str,
    *,
    now: datetime | None = None,
) -> ApprovalRecord:
    """Validate one approval record for the given risk class.

    Raises ApprovalRequired when no record was supplied and
    ApprovalInvalid when the record is malformed, incomplete, not an
    approval, or timed out per the approval flow contract's
    timeout_rules. now anchors the timeout check; None (the service's
    call shape) means the current UTC time. A naive now is interpreted
    as UTC.
    """
    required = REQUIRED_FIELDS.get(risk_class)
    if required is None:
        raise ApprovalInvalid(
            f"unknown approval risk class {risk_class!r}; expected one "
            f"of {sorted(REQUIRED_FIELDS)}"
        )
    if payload is None:
        raise ApprovalRequired(
            f"transition requires an approved request at risk class "
            f"{risk_class} per contracts/policy/APPROVAL_FLOW_V1.yaml"
        )
    if not isinstance(payload, Mapping):
        raise ApprovalInvalid("approval record must be a JSON object")
    problems: list[str] = []
    for key in required:
        value = payload.get(key)
        if not isinstance(value, str) or not value:
            problems.append(
                f"approval field {key!r} must be a non-empty string"
            )
    unknown = sorted(set(payload) - set(required))
    if unknown:
        problems.append(f"approval record has unknown field(s) {unknown}")
    if problems:
        raise ApprovalInvalid("; ".join(problems))
    decision = payload["decision"]
    if decision != "approved":
        raise ApprovalInvalid(
            f"approval decision must be 'approved', got {decision!r}"
        )
    decided_at_raw = payload["decided_at"]
    decided_at = _parse_decided_at(decided_at_raw)
    reference = now if now is not None else datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    else:
        reference = reference.astimezone(timezone.utc)
    _check_timeout(
        payload["approval_id"],
        decided_at_raw,
        decided_at,
        risk_class,
        reference,
    )
    return ApprovalRecord(
        approval_id=payload["approval_id"],
        approver=payload["approver"],
        decision=decision,
        decided_at=decided_at_raw,
        change_ticket=payload.get("change_ticket"),
    )
