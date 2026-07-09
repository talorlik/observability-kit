"""Offline tests for approval gating and audit (Batch 20 Task 4).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 20 validator - never under pytest. Every run
uses temp directories for both the control-plane store and the render
target repo root; the repository's own gitops/ tree is never touched.

Covers the Task 4 completion check on top of the Task 2 basics:

- timeout_rules of contracts/policy/APPROVAL_FLOW_V1.yaml are honored:
  an approval older than pending_timeout_minutes (60 for
  write.high-risk, 120 for write.critical) relative to now is denied
  as approval-invalid, boundary inclusive (exactly at the window is
  still valid, past it is not);
- escalation_rules are honored on timeout (on_timeout
  deny-and-escalate): the denial carries the default_escalation_chain,
  on_unresolved_after_chain deny, the notify channels, and
  escalation_audit_event_required verbatim from the contract, and the
  denial audit record (requires_audit_event) records the escalation;
- malformed and future decided_at values are approval-invalid;
- every transition audit record - applied, replayed, and denied -
  carries tenant_id, and denials surface audit_record_id on the error;
- emit_audit / ensure_required_fields reject records that violate the
  TR-09 invariants (empty tenant_id, unknown outcome, denials without
  a reason) instead of persisting them.

Timestamps in service-path tests are generated relative to the real
UTC clock because the service calls validate_approval without a now
argument (now=None means current UTC time); unit tests inject now for
determinism.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS = REPO_ROOT / "contracts"
LIFECYCLE_CONTRACT = (
    CONTRACTS / "tenancy" / "TENANT_LIFECYCLE_CONTRACT_V1.yaml"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "tenancy"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from tenantctl.approval import (  # noqa: E402
    ESCALATION_CHAIN,
    ESCALATION_NOTIFY_CHANNELS,
    ON_TIMEOUT,
    ON_UNRESOLVED_AFTER_CHAIN,
    PENDING_TIMEOUT_MINUTES,
    RISK_CRITICAL,
    RISK_HIGH,
    validate_approval,
)
from tenantctl.audit import (  # noqa: E402
    AuditContractViolation,
    OUTCOME_APPLIED,
    OUTCOME_DENIED,
    OUTCOME_REPLAYED,
    emit_audit,
    ensure_required_fields,
)
from tenantctl.models import (  # noqa: E402
    ApprovalInvalid,
    ApprovalRequired,
    ControlPlaneError,
)
from tenantctl.service import TenantControlPlaneService  # noqa: E402
from tenantctl.store import ControlPlaneStore  # noqa: E402

NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def high_risk_approval(decided_at: str) -> dict[str, Any]:
    return {
        "approval_id": "apr-100",
        "approver": "approver@example.com",
        "decision": "approved",
        "decided_at": decided_at,
    }


def critical_approval(decided_at: str) -> dict[str, Any]:
    return {
        **high_risk_approval(decided_at),
        "change_ticket": "chg-900",
    }


def expect_invalid(
    payload: dict[str, Any], risk_class: str, now: datetime
) -> ApprovalInvalid:
    try:
        validate_approval(payload, risk_class, now=now)
    except ApprovalInvalid as error:
        return error
    raise AssertionError(
        f"expected ApprovalInvalid for {risk_class} with decided_at "
        f"{payload.get('decided_at')!r} at now {now.isoformat()}"
    )


# -- validate_approval unit tests (injected now, deterministic) --------


def test_fresh_approval_within_window_valid() -> None:
    decided = iso(NOW - timedelta(minutes=59))
    record = validate_approval(
        high_risk_approval(decided), RISK_HIGH, now=NOW
    )
    assert record.approval_id == "apr-100"
    assert record.decided_at == decided
    record = validate_approval(
        critical_approval(iso(NOW - timedelta(minutes=119))),
        RISK_CRITICAL,
        now=NOW,
    )
    assert record.change_ticket == "chg-900"


def test_expired_approval_blocked_per_timeout_rules() -> None:
    # timeout_rules: write.high-risk pending_timeout_minutes 60.
    decided = iso(NOW - timedelta(minutes=61))
    error = expect_invalid(high_risk_approval(decided), RISK_HIGH, NOW)
    assert error.error_code == "approval-invalid"
    assert "timed out" in error.message
    assert "60-minute" in error.message
    # timeout_rules: write.critical pending_timeout_minutes 120.
    decided = iso(NOW - timedelta(minutes=121))
    error = expect_invalid(
        critical_approval(decided), RISK_CRITICAL, NOW
    )
    assert "120-minute" in error.message


def test_per_risk_class_windows_differ() -> None:
    # An approval aged 90 minutes: past the write.high-risk window,
    # inside the write.critical one - proves the per-class
    # pending_timeout_minutes values are honored, not a single window.
    decided = iso(NOW - timedelta(minutes=90))
    expect_invalid(high_risk_approval(decided), RISK_HIGH, NOW)
    record = validate_approval(
        critical_approval(decided), RISK_CRITICAL, now=NOW
    )
    assert record.decided_at == decided


def test_boundary_exact_window_edge() -> None:
    # The timeout fires only once the window has elapsed: an approval
    # exactly pending_timeout_minutes old is still valid, one second
    # past is not.
    assert PENDING_TIMEOUT_MINUTES[RISK_HIGH] == 60
    assert PENDING_TIMEOUT_MINUTES[RISK_CRITICAL] == 120
    at_edge = iso(NOW - timedelta(minutes=60))
    record = validate_approval(
        high_risk_approval(at_edge), RISK_HIGH, now=NOW
    )
    assert record.decided_at == at_edge
    past_edge = iso(NOW - timedelta(minutes=60, seconds=1))
    expect_invalid(high_risk_approval(past_edge), RISK_HIGH, NOW)
    at_edge = iso(NOW - timedelta(minutes=120))
    validate_approval(
        critical_approval(at_edge), RISK_CRITICAL, now=NOW
    )
    past_edge = iso(NOW - timedelta(minutes=120, seconds=1))
    expect_invalid(critical_approval(past_edge), RISK_CRITICAL, NOW)


def test_escalation_directive_on_timeout() -> None:
    # escalation_rules, verbatim: default_escalation_chain roles and
    # SLAs, on_unresolved_after_chain deny, notify channels, and the
    # required escalation audit event, all surfaced on the denial.
    decided = iso(NOW - timedelta(hours=3))
    error = expect_invalid(high_risk_approval(decided), RISK_HIGH, NOW)
    assert ON_TIMEOUT == "deny-and-escalate"
    assert "deny-and-escalate" in error.message
    assert "oncall-sre -> incident-commander -> platform-director" in (
        error.message
    )
    details = error.details
    assert details is not None
    assert details["on_timeout"] == "deny-and-escalate"
    assert details["escalation_chain"] == [
        {"role": "oncall-sre", "sla_minutes": 30},
        {"role": "incident-commander", "sla_minutes": 60},
        {"role": "platform-director", "sla_minutes": 120},
    ]
    assert details["on_unresolved_after_chain"] == "deny"
    assert ON_UNRESOLVED_AFTER_CHAIN == "deny"
    assert details["notify_channels"] == [
        "audit-log",
        "paging-service",
        "casefile-comment",
    ]
    assert tuple(details["notify_channels"]) == (
        ESCALATION_NOTIFY_CHANNELS
    )
    assert details["escalation_audit_event_required"] is True
    assert details["pending_timeout_minutes"] == 60
    assert details["decided_at"] == decided
    assert len(ESCALATION_CHAIN) == 3


def test_no_escalation_on_valid_approval() -> None:
    # Negative case: a fresh approval passes with no timeout, no
    # escalation, and no denial - the record is returned unchanged.
    decided = iso(NOW - timedelta(minutes=5))
    record = validate_approval(
        high_risk_approval(decided), RISK_HIGH, now=NOW
    )
    assert record.decision == "approved"
    assert record.approver == "approver@example.com"


def test_re_approval_after_timeout_accepted() -> None:
    # Escalation flow outcome: after a timeout the resulting record
    # requirement is a fresh approval decided within the window (the
    # record schema gains no extra fields; the API contract is
    # additionalProperties: false). The same validator accepts it.
    stale = iso(NOW - timedelta(hours=2))
    expect_invalid(high_risk_approval(stale), RISK_HIGH, NOW)
    renewed = high_risk_approval(iso(NOW - timedelta(minutes=1)))
    renewed["approval_id"] = "apr-101"
    renewed["approver"] = "platform-director@example.com"
    record = validate_approval(renewed, RISK_HIGH, now=NOW)
    assert record.approval_id == "apr-101"


def test_malformed_decided_at_rejected() -> None:
    # Fails the RFC 3339 shape outright.
    error = expect_invalid(
        high_risk_approval("not-a-timestamp"), RISK_HIGH, NOW
    )
    assert "RFC 3339" in error.message
    # Matches the shape but is not a real timestamp (month 13).
    error = expect_invalid(
        high_risk_approval("2026-13-05T00:00:00Z"), RISK_HIGH, NOW
    )
    assert "RFC 3339" in error.message


def test_future_decided_at_rejected() -> None:
    decided = iso(NOW + timedelta(minutes=10))
    error = expect_invalid(high_risk_approval(decided), RISK_HIGH, NOW)
    assert "postdate" in error.message


def test_default_now_is_current_utc() -> None:
    # service.py calls validate_approval without now: None must mean
    # the current UTC wall clock.
    fresh = high_risk_approval(iso(datetime.now(timezone.utc)))
    record = validate_approval(fresh, RISK_HIGH)
    assert record.approval_id == "apr-100"
    stale = high_risk_approval(
        iso(datetime.now(timezone.utc) - timedelta(hours=2))
    )
    try:
        validate_approval(stale, RISK_HIGH)
    except ApprovalInvalid as error:
        assert "timed out" in error.message
    else:
        raise AssertionError(
            "expected ApprovalInvalid for a stale approval with "
            "default now"
        )


def test_offset_timezone_decided_at_normalized() -> None:
    # A non-UTC offset is normalized before the age math.
    local = (NOW - timedelta(minutes=30)).astimezone(
        timezone(timedelta(hours=5, minutes=30))
    )
    decided = local.strftime("%Y-%m-%dT%H:%M:%S+05:30")
    record = validate_approval(
        high_risk_approval(decided), RISK_HIGH, now=NOW
    )
    assert record.decided_at == decided


# -- service-path tests (real store, real service, temp dirs) ----------


@dataclass
class FakeClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance_days(self, days: int) -> None:
        self.now = self.now + timedelta(days=days)


def tenant_document(tenant_id: str = "acme") -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "display_name": "Acme Corp",
        "tier": "enterprise",
        "isolation_class": "dedicated-stack",
        "residency": {
            "region": "region-a",
            "data_residency_required": True,
            "pool": "dedicated",
            "allowed_regions": ["region-a"],
        },
        "lifecycle_state": "provisioning",
        "owner": {"name": "Platform Team", "email": "owner@example.com"},
        "contacts": [
            {"role": "technical", "email": "tech@example.com"},
        ],
        "quotas": {
            "ingest": {
                "max_gb_per_day": 50,
                "max_events_per_second": 1000,
            },
            "retention": {
                "logs_days": 30,
                "metrics_days": 90,
                "traces_days": 14,
            },
        },
        "created_at": "2026-07-01T00:00:00Z",
    }


class Env:
    """One isolated service instance over temp store and repo roots."""

    def __init__(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="tenantctl-appr-"))
        self.repo_root = self._tmp / "repo"
        self.repo_root.mkdir()
        self.store = ControlPlaneStore(self._tmp / "store")
        self.clock = FakeClock(
            datetime(2026, 7, 10, 0, 0, 0, tzinfo=timezone.utc)
        )
        self.service = TenantControlPlaneService(
            store=self.store,
            repo_root=self.repo_root,
            lifecycle_contract_path=LIFECYCLE_CONTRACT,
            clock=self.clock,
        )

    def cleanup(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


def expect_error(
    env: Env,
    transition: str,
    tenant_id: str,
    payload: dict[str, Any],
    error_type: type[ControlPlaneError],
) -> ControlPlaneError:
    try:
        env.service.transition(transition, tenant_id, payload)
    except error_type as error:
        return error
    raise AssertionError(
        f"expected {error_type.__name__} for {transition} on "
        f"{tenant_id}"
    )


def provisioned_env(tenant_id: str = "acme") -> Env:
    env = Env()
    env.service.create_tenant(tenant_document(tenant_id))
    env.service.transition(
        "provision", tenant_id, {"actor": "op@example.com"}
    )
    return env


def wall_clock_approval(
    *, critical: bool = False, age: timedelta | None = None
) -> dict[str, Any]:
    """Approval decided relative to the real UTC clock.

    The service calls validate_approval without now, so service-path
    approvals must be fresh (or stale) against the wall clock, not the
    injected FakeClock.
    """
    decided = iso(datetime.now(timezone.utc) - (age or timedelta()))
    if critical:
        return critical_approval(decided)
    return high_risk_approval(decided)


def test_expired_approval_blocks_transition_and_is_audited() -> None:
    env = provisioned_env()
    try:
        error = expect_error(
            env,
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "contract ended",
                "approval": wall_clock_approval(age=timedelta(hours=2)),
            },
            ApprovalInvalid,
        )
        assert error.error_code == "approval-invalid"
        assert "timed out" in error.message
        # The transition was blocked: the tenant did not move.
        assert env.service.get_tenant("acme")["lifecycle_state"] == (
            "active"
        )
        # requires_audit_event + emit_audit_record_on_denial: the
        # denial audit record exists, is surfaced on the error, and
        # records the escalation (audit-log notify channel).
        assert error.audit_record_id
        records = {
            record["audit_record_id"]: record
            for record in env.store.load_audit_records()
        }
        denial = records[error.audit_record_id]
        assert denial["tenant_id"] == "acme"
        assert denial["outcome"] == "denied"
        assert denial["transition"] == "offboard"
        assert denial["error_code"] == "approval-invalid"
        assert "deny-and-escalate" in denial["message"]
        assert "platform-director" in denial["message"]
    finally:
        env.cleanup()


def test_missing_approval_denial_carries_tenant_id() -> None:
    env = provisioned_env()
    try:
        error = expect_error(
            env,
            "offboard",
            "acme",
            {"actor": "op@example.com", "reason": "bye"},
            ApprovalRequired,
        )
        assert error.error_code == "approval-required"
        assert error.audit_record_id
        records = {
            record["audit_record_id"]: record
            for record in env.store.load_audit_records()
        }
        denial = records[error.audit_record_id]
        assert denial["tenant_id"] == "acme"
        assert denial["outcome"] == "denied"
        assert denial["error_code"] == "approval-required"
    finally:
        env.cleanup()


def test_every_outcome_audit_record_carries_tenant_id() -> None:
    env = Env()
    try:
        env.service.create_tenant(tenant_document())
        # applied
        env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        # replayed
        replay = env.service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert replay.replay is True
        # applied (destructive, fresh wall-clock approval)
        env.service.transition(
            "offboard",
            "acme",
            {
                "actor": "op@example.com",
                "reason": "contract ended",
                "approval": wall_clock_approval(),
            },
        )
        # denied (purge before the retention window elapsed)
        expect_error(
            env,
            "purge",
            "acme",
            {
                "actor": "op@example.com",
                "approval": wall_clock_approval(critical=True),
            },
            ControlPlaneError,
        )
        records = env.store.load_audit_records()
        outcomes = {record["outcome"] for record in records}
        assert {
            OUTCOME_APPLIED,
            OUTCOME_REPLAYED,
            OUTCOME_DENIED,
        } <= outcomes
        for record in records:
            assert record["tenant_id"] == "acme", record
            assert record["audit_record_id"], record
            assert record["actor"] == "op@example.com", record
    finally:
        env.cleanup()


# -- emit_audit / ensure_required_fields unit tests --------------------


def audit_store() -> tuple[ControlPlaneStore, Path]:
    tmp = Path(tempfile.mkdtemp(prefix="tenantctl-audit-"))
    return ControlPlaneStore(tmp / "store"), tmp


def test_emit_audit_persists_and_returns_record_id() -> None:
    store, tmp = audit_store()
    try:
        record = emit_audit(
            store,
            tenant_id="acme",
            transition="provision",
            actor="op@example.com",
            replay=False,
            outcome=OUTCOME_APPLIED,
            recorded_at="2026-07-10T00:00:00Z",
            extra_fields={"requested_at": "2026-07-10T00:00:00Z"},
        )
        assert record["audit_record_id"] == "audit-000001"
        stored = store.load_audit_records()[0]
        assert stored["tenant_id"] == "acme"
        assert stored["requested_at"] == "2026-07-10T00:00:00Z"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def expect_violation(**overrides: Any) -> AuditContractViolation:
    store, tmp = audit_store()
    kwargs: dict[str, Any] = {
        "tenant_id": "acme",
        "transition": "provision",
        "actor": "op@example.com",
        "replay": False,
        "outcome": OUTCOME_APPLIED,
        "recorded_at": "2026-07-10T00:00:00Z",
    }
    kwargs.update(overrides)
    try:
        emit_audit(store, **kwargs)
    except AuditContractViolation as error:
        return error
    else:
        raise AssertionError(
            f"expected AuditContractViolation for {overrides}"
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        # The invariant failure must not have persisted anything.


def test_emit_audit_rejects_empty_tenant_id() -> None:
    error = expect_violation(tenant_id="")
    assert "tenant_id" in str(error)


def test_emit_audit_rejects_unknown_outcome() -> None:
    error = expect_violation(outcome="skipped")
    assert "outcome" in str(error)


def test_emit_audit_rejects_bad_recorded_at() -> None:
    error = expect_violation(recorded_at="yesterday")
    assert "recorded_at" in str(error)


def test_emit_audit_rejects_denial_without_reason() -> None:
    # Denials must carry the reason (error_code and message) the API
    # surfaces next to audit_record_id.
    error = expect_violation(outcome=OUTCOME_DENIED)
    assert "error_code" in str(error)
    # And a denial with the reason is accepted.
    store, tmp = audit_store()
    try:
        record = emit_audit(
            store,
            tenant_id="acme",
            transition="offboard",
            actor="op@example.com",
            replay=False,
            outcome=OUTCOME_DENIED,
            recorded_at="2026-07-10T00:00:00Z",
            extra_fields={
                "error_code": "approval-invalid",
                "message": "approval 'apr-100' timed out",
            },
        )
        assert record["tenant_id"] == "acme"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_emit_audit_rejects_required_field_emptied_by_extras() -> None:
    # extra_fields cannot blank out a base invariant.
    error = expect_violation(extra_fields={"actor": ""})
    assert "actor" in str(error)


def test_emit_audit_enforces_transition_field_list() -> None:
    error = expect_violation(
        required_fields=("tenant_id", "retention_window_ends_at")
    )
    assert "retention_window_ends_at" in str(error)


def test_ensure_required_fields_treats_empty_as_missing() -> None:
    record = {
        "tenant_id": "acme",
        "transition": "offboard",
        "actor": "",
        "replay": False,
        "approval_id": None,
    }
    try:
        ensure_required_fields(
            record, ("tenant_id", "actor", "approval_id", "replay")
        )
    except AuditContractViolation as error:
        message = str(error)
        assert "actor" in message
        assert "approval_id" in message
        # replay=False is a value, never "missing".
        assert "'replay'" not in message
    else:
        raise AssertionError("expected AuditContractViolation")


def test_change_management_callback_on_critical_timeout() -> None:
    # timeout_rules.write.critical.requires_change_management_callback
    # is true in APPROVAL_FLOW_V1.yaml; write.high-risk has no such
    # rule. The timeout-denial directive must carry the flag per class.
    decided = iso(NOW - timedelta(hours=5))
    critical_err = expect_invalid(
        critical_approval(decided), RISK_CRITICAL, NOW
    )
    assert critical_err.details is not None
    assert critical_err.details[
        "requires_change_management_callback"
    ] is True
    high_err = expect_invalid(high_risk_approval(decided), RISK_HIGH, NOW)
    assert high_err.details is not None
    assert high_err.details[
        "requires_change_management_callback"
    ] is False


def main() -> int:
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]
    for name, func in tests:
        func()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
