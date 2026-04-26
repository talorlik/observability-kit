#!/usr/bin/env python3

"""Approval gate primitives for assisted RCA recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, UTC


@dataclass(frozen=True)
class ApprovalDecision:
    recommendation_id: str
    reviewer: str
    approval_decision: str
    reason_code: str
    timestamp: str


def create_decision(
    recommendation_id: str,
    reviewer: str,
    approval_decision: str,
    reason_code: str,
) -> ApprovalDecision:
    if approval_decision not in {"approved", "rejected"}:
        raise ValueError("approval_decision must be approved or rejected")
    return ApprovalDecision(
        recommendation_id=recommendation_id,
        reviewer=reviewer,
        approval_decision=approval_decision,
        reason_code=reason_code,
        timestamp=datetime.now(UTC).isoformat(),
    )


def can_release_rca_suggestion(decision: ApprovalDecision) -> bool:
    """Release is allowed only with explicit approved decision."""
    return decision.approval_decision == "approved"
