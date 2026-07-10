"""Store round-trip tests for the AI runtime persistence layer.

Plain python3 script: test_* functions with bare asserts, run directly.
Exercises the SqliteStore (interface-identical to the contracted
PostgresStore) and the write-once audit posture.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "services" / "ai")
)

from airuntime.store import AuditRecord, SqliteStore  # noqa: E402


def _store() -> SqliteStore:
    store = SqliteStore()
    store.init_schema()
    return store


def _casefile(case_id: str, status: str = "open") -> dict[str, Any]:
    return {
        "schema_version": "v1",
        "case_id": case_id,
        "casefile_id": case_id,
        "tenant_id": "tenant-demo",
        "status": status,
        "incident_context": {"summary": "s"},
        "agent_outputs": [],
        "evidence_handles": [],
        "approval_state": {"required": False, "status": "not-required"},
        "action_journal": [],
        "lineage": {"correlation_id": f"corr-{case_id}"},
        "created_at": f"2026-07-10T00:00:0{case_id[-1]}+00:00",
        "updated_at": "2026-07-10T00:00:00+00:00",
    }


def _approval(approval_id: str, state: str = "pending") -> dict[str, Any]:
    return {
        "approval_id": approval_id,
        "casefile_id": "case-1",
        "tool": "runbook-plan.v1",
        "risk_class": "write.high-risk",
        "requested_by": "ops-ceo-agent",
        "requested_at": "2026-07-10T00:00:00+00:00",
        "deadline_at": "2026-07-10T01:00:00+00:00",
        "warning_at": "2026-07-10T00:30:00+00:00",
        "state": state,
        "approver": None,
        "decision": None,
        "decided_at": None,
        "escalation": {"chain": [], "notify_channels": [], "on_unresolved": "deny"},
    }


def test_casefile_upsert_get_list() -> None:
    store = _store()
    store.upsert_casefile(_casefile("case-1"))
    store.upsert_casefile(_casefile("case-2"))
    fetched = store.get_casefile("case-1")
    assert fetched is not None and fetched["case_id"] == "case-1"
    assert store.get_casefile("missing") is None
    assert [c["case_id"] for c in store.list_casefiles()] == [
        "case-1", "case-2"
    ]
    # Upsert replaces: status change survives the round trip.
    store.upsert_casefile(_casefile("case-1", status="resolved"))
    assert store.get_casefile("case-1")["status"] == "resolved"
    assert len(store.list_casefiles()) == 2


def test_approval_insert_update_get_list() -> None:
    store = _store()
    store.insert_approval(_approval("appr-1"))
    store.insert_approval(_approval("appr-2"))
    fetched = store.get_approval("appr-1")
    assert fetched is not None
    assert fetched["state"] == "pending"
    assert isinstance(fetched["escalation"], dict)
    assert store.get_approval("missing") is None

    decided = dict(fetched)
    decided.update(
        state="approved",
        approver="human-oncall",
        decision="approved",
        decided_at="2026-07-10T00:10:00+00:00",
        change_ticket="CHG-2026-0042",
    )
    store.update_approval(decided)
    stored = store.get_approval("appr-1")
    assert stored["state"] == "approved"
    assert stored["approver"] == "human-oncall"
    assert stored["decided_at"] == "2026-07-10T00:10:00+00:00"
    # APPROVAL_FLOW_V1 required_approval_fields: the change_ticket of
    # an approved record survives the round trip; undecided records
    # carry it as NULL.
    assert stored["change_ticket"] == "CHG-2026-0042"
    assert store.get_approval("appr-2")["change_ticket"] is None

    assert [a["approval_id"] for a in store.list_approvals()] == [
        "appr-1", "appr-2"
    ]
    pending = store.list_approvals(state="pending")
    assert [a["approval_id"] for a in pending] == ["appr-2"]
    approved = store.list_approvals(state="approved")
    assert [a["approval_id"] for a in approved] == ["appr-1"]


def test_audit_append_and_ordering() -> None:
    store = _store()
    for index in range(3):
        store.append_audit(
            AuditRecord(
                event_type=f"event-{index}",
                actor="kagent-controller",
                payload={"index": index},
                casefile_id="case-1",
                tenant_id="tenant-demo",
            )
        )
    records = store.audit_records()
    assert len(records) == 3
    # Insertion order preserved via monotonically increasing record_id.
    assert [r["event_type"] for r in records] == [
        "event-0", "event-1", "event-2"
    ]
    assert [r["record_id"] for r in records] == sorted(
        r["record_id"] for r in records
    )
    assert records[0]["payload"] == {"index": 0}
    assert records[0]["casefile_id"] == "case-1"
    assert records[0]["tenant_id"] == "tenant-demo"


def test_audit_write_once_posture() -> None:
    # The audit namespace exposes append + select only: no update or
    # delete surface exists on the store API.
    store = _store()
    audit_methods = [
        name
        for name in dir(store)
        if "audit" in name and not name.startswith("_")
    ]
    assert sorted(audit_methods) == ["append_audit", "audit_records"]


def main() -> int:
    tests = [
        (name, fn)
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    failures = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS {name}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"FAIL {name}: {exc!r}")
    print(f"{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
