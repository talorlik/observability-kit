"""Audit-record construction (TR-09).

Every transition attempt - applied, replayed, or denied - emits one
audit record carrying the tenant id, per the lifecycle contract
invariants and its emit_audit_record_on_denial execution gate. Records
are control-plane data and never embed tenant telemetry payloads.

Batch 20 Task 4 hardens the invariants: the base fields (tenant_id,
transition, actor, replay) plus outcome and recorded_at are verified
on every record - not only when a per-transition required-field list
is supplied - with empty values treated as missing, and denial records
must carry the denial reason (error_code and message), matching what
the API contract's ErrorResponse surfaces next to audit_record_id and
what the approval flow contract's requires_audit_event /
escalation_audit_event_required timeout rules rely on. The emit_audit
interface and the persisted store schema are unchanged.
"""

from __future__ import annotations

from typing import Any, Mapping

from tenantctl.models import DATETIME_PATTERN
from tenantctl.store import ControlPlaneStore

# Fields present on every audit record, before per-transition extras.
BASE_FIELDS = ("tenant_id", "transition", "actor", "replay")

OUTCOME_APPLIED = "applied"
OUTCOME_REPLAYED = "replayed"
OUTCOME_DENIED = "denied"
OUTCOMES = (OUTCOME_APPLIED, OUTCOME_REPLAYED, OUTCOME_DENIED)

# Denial records additionally carry the denial reason: the
# contract-fixed error code and the human-readable message (which, for
# approval timeouts, is the escalation audit event required by
# contracts/policy/APPROVAL_FLOW_V1.yaml).
DENIAL_REASON_FIELDS = ("error_code", "message")


class AuditContractViolation(RuntimeError):
    """An audit record is missing contract-required fields.

    This is an internal invariant failure, not an operator error: the
    service must always assemble the per-transition required fields
    before emitting.
    """


def _is_missing(value: Any) -> bool:
    """A field is missing when absent, None, or an empty string.

    Booleans (replay=False) and numeric zeros are legitimate values
    and never count as missing.
    """
    return value is None or (isinstance(value, str) and not value)


def ensure_required_fields(
    record: Mapping[str, Any], required: tuple[str, ...]
) -> None:
    missing = sorted(
        key
        for key in set(required)
        if key not in record or _is_missing(record[key])
    )
    if missing:
        raise AuditContractViolation(
            f"audit record for transition "
            f"{record.get('transition')!r} is missing contract-required "
            f"field(s) {missing}"
        )


def _ensure_base_invariants(record: Mapping[str, Any]) -> None:
    """Verify the invariants every audit record must satisfy (TR-09).

    tenant_id, transition, and actor are non-empty strings; replay is a
    boolean; outcome is one of the fixed outcomes; recorded_at is an
    RFC 3339 timestamp; denied records carry the denial reason.
    """
    for key in ("tenant_id", "transition", "actor"):
        value = record.get(key)
        if not isinstance(value, str) or not value:
            raise AuditContractViolation(
                f"audit record field {key!r} must be a non-empty "
                f"string, got {value!r}"
            )
    if not isinstance(record.get("replay"), bool):
        raise AuditContractViolation(
            f"audit record field 'replay' must be a boolean, got "
            f"{record.get('replay')!r}"
        )
    outcome = record.get("outcome")
    if outcome not in OUTCOMES:
        raise AuditContractViolation(
            f"audit record outcome must be one of {OUTCOMES}, got "
            f"{outcome!r}"
        )
    recorded_at = record.get("recorded_at")
    if not isinstance(recorded_at, str) or not DATETIME_PATTERN.match(
        recorded_at
    ):
        raise AuditContractViolation(
            f"audit record recorded_at must be an RFC 3339 date-time, "
            f"got {recorded_at!r}"
        )
    if outcome == OUTCOME_DENIED:
        ensure_required_fields(record, DENIAL_REASON_FIELDS)


def emit_audit(
    store: ControlPlaneStore,
    *,
    tenant_id: str,
    transition: str,
    actor: str,
    replay: bool,
    outcome: str,
    recorded_at: str,
    extra_fields: Mapping[str, Any] | None = None,
    required_fields: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Build, verify, and persist one audit record.

    Returns the persisted record including its assigned
    audit_record_id. The base invariants (non-empty tenant_id,
    transition, actor; boolean replay; known outcome; RFC 3339
    recorded_at; denial reason on denied records) are verified on
    every record. required_fields, when given (applied and replayed
    attempts), is the lifecycle contract's audit field list for the
    transition and is verified before the write so a contract drift
    fails loudly instead of emitting a non-conformant record.
    """
    record: dict[str, Any] = {
        "tenant_id": tenant_id,
        "transition": transition,
        "actor": actor,
        "replay": replay,
        "outcome": outcome,
        "recorded_at": recorded_at,
    }
    if extra_fields:
        record.update(dict(extra_fields))
    _ensure_base_invariants(record)
    if required_fields is not None:
        ensure_required_fields(record, required_fields)
    audit_record_id = store.append_audit(record)
    return {"audit_record_id": audit_record_id, **record}
