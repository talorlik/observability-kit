"""Seeded denial fixtures for the tenant control plane (Batch 20
Task 5).

Plain python3 script with test_* functions and bare asserts, invoked
directly by scripts/ci/validate_tenant_control_plane.sh - never under
pytest. Every fixture run uses a fresh service instance over temp
directories for both the control-plane store and the render target
repo root; the repository's own gitops/ tree is never touched.

Each JSON fixture under tests/controlplane/fixtures/seeded_denials/
declares one denial scenario: declarative setup steps, one attempted
operation, and the expected contract-fixed error_code. The driver
replays the scenario against the real TenantControlPlaneService and
asserts, per TR-16's deny-by-default posture and the lifecycle
contract's emit_audit_record_on_denial gate:

- the attempt raises the exact expected error_code (never succeeds);
- the error message carries the seeded reason;
- transition denials produce a denial audit record carrying the
  addressed tenant_id and the error_code (TR-09);
- no state is mutated by the denied attempt (the tenant's
  lifecycle_state is unchanged; a rejected create registers nothing).

Approval timeout windows in APPROVAL_FLOW_V1.yaml are evaluated
against the wall clock (the service calls validate_approval without a
now anchor), so fixtures that need an in-window approval carry the
__FRESH_UTC_NOW__ placeholder, substituted at load time; the seeded
timed-out approval carries a static decided_at that is permanently
outside every window.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURES_DIR = TESTS_DIR / "fixtures" / "seeded_denials"
CONTRACTS = REPO_ROOT / "contracts"
LIFECYCLE_CONTRACT = (
    CONTRACTS / "tenancy" / "TENANT_LIFECYCLE_CONTRACT_V1.yaml"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "tenancy"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from tenantctl.models import (  # noqa: E402
    ControlPlaneError,
    TenantNotFound,
)
from tenantctl.service import TenantControlPlaneService  # noqa: E402
from tenantctl.store import ControlPlaneStore  # noqa: E402

FRESH_DECIDED_AT_TOKEN = "__FRESH_UTC_NOW__"

# Every denial scenario Task 5 requires; the corpus must cover all of
# them (test_required_scenarios_covered).
REQUIRED_SCENARIOS: tuple[str, ...] = (
    "unapproved-offboard",
    "unapproved-purge",
    "wrong-risk-class-purge-approval",
    "timed-out-approval",
    "illegal-transition",
    "purge-before-retention-window",
    "purge-with-legal-hold",
    "cross-tenant-denial",
    "malformed-tenant-document-create",
)


@dataclass
class FakeClock:
    now: datetime

    def __call__(self) -> datetime:
        return self.now

    def advance_days(self, days: int) -> None:
        self.now = self.now + timedelta(days=days)


def tenant_document(tenant_id: str) -> dict[str, Any]:
    """A valid dedicated-stack tenant contract document."""
    return {
        "tenant_id": tenant_id,
        "display_name": f"Tenant {tenant_id}",
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


def fresh_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fresh_high_risk_approval(approval_id: str) -> dict[str, str]:
    """A write.high-risk approval decided now (inside the 60-minute
    pending timeout window, which runs against the wall clock)."""
    return {
        "approval_id": approval_id,
        "approver": "approver@example.com",
        "decision": "approved",
        "decided_at": fresh_utc_now(),
    }


def substitute_fresh_timestamps(node: Any) -> Any:
    """Replace every __FRESH_UTC_NOW__ placeholder with the current
    wall-clock UTC time so seeded in-window approvals never expire."""
    if isinstance(node, dict):
        return {
            key: substitute_fresh_timestamps(value)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [substitute_fresh_timestamps(item) for item in node]
    if node == FRESH_DECIDED_AT_TOKEN:
        return fresh_utc_now()
    return node


class Env:
    """One isolated service instance over temp store and repo roots."""

    def __init__(self) -> None:
        self._tmp = Path(tempfile.mkdtemp(prefix="tenantctl-seeded-"))
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


def load_fixtures() -> list[tuple[Path, dict[str, Any]]]:
    paths = sorted(FIXTURES_DIR.glob("*.json"))
    assert paths, f"no seeded denial fixtures under {FIXTURES_DIR}"
    return [
        (path, json.loads(path.read_text(encoding="utf-8")))
        for path in paths
    ]


def run_setup(env: Env, steps: list[dict[str, Any]]) -> None:
    """Drive the tenant into the state the denial scenario needs."""
    for index, step in enumerate(steps):
        kind = step["step"]
        if kind == "create_tenant":
            env.service.create_tenant(
                tenant_document(step["tenant_id"])
            )
        elif kind == "provision":
            env.service.transition(
                "provision",
                step["tenant_id"],
                {"actor": "op@example.com"},
            )
        elif kind == "offboard_approved":
            env.service.transition(
                "offboard",
                step["tenant_id"],
                {
                    "actor": "op@example.com",
                    "reason": "seeded denial scenario setup",
                    "approval": fresh_high_risk_approval(
                        f"apr-setup-{index}"
                    ),
                },
            )
        elif kind == "advance_days":
            env.clock.advance_days(int(step["days"]))
        elif kind == "set_legal_hold":
            env.service.set_legal_hold(step["tenant_id"], True)
        else:
            raise AssertionError(f"unknown setup step {kind!r}")


def run_attempt(env: Env, attempt: dict[str, Any]) -> None:
    """Execute the seeded attempt; a denial propagates as the raised
    ControlPlaneError."""
    kind = attempt["kind"]
    caller_scope = attempt.get("caller_scope")
    if kind == "transition":
        env.service.transition(
            attempt["transition"],
            attempt["tenant_id"],
            attempt["payload"],
            caller_scope=caller_scope,
        )
    elif kind == "create_tenant":
        env.service.create_tenant(
            attempt["document"], caller_scope=caller_scope
        )
    else:
        raise AssertionError(f"unknown attempt kind {kind!r}")


def lifecycle_state_or_none(env: Env, tenant_id: str) -> str | None:
    try:
        return str(env.service.get_tenant(tenant_id)["lifecycle_state"])
    except TenantNotFound:
        return None


def test_fixture_corpus_well_formed() -> None:
    scenario_ids: set[str] = set()
    for path, fixture in load_fixtures():
        assert fixture.get("schema_version") == "v1", (
            f"{path.name}: schema_version must be 'v1'"
        )
        scenario_id = fixture.get("scenario_id", "")
        assert scenario_id.startswith("SDN-B20-"), (
            f"{path.name}: scenario_id must carry the SDN-B20- prefix"
        )
        assert scenario_id not in scenario_ids, (
            f"{path.name}: duplicate scenario_id {scenario_id}"
        )
        scenario_ids.add(scenario_id)
        assert fixture.get("scenario") in REQUIRED_SCENARIOS, (
            f"{path.name}: unknown scenario {fixture.get('scenario')!r}"
        )
        assert "TR-16" in fixture.get("requirement_markers", []), (
            f"{path.name}: seeded denials prove TR-16 deny-by-default"
        )
        expected = fixture.get("expected", {})
        # Deny-by-default proof (TR-16): a seeded fixture may only ever
        # expect a denial - never a success outcome.
        assert expected.get("outcome") == "denied", (
            f"{path.name}: expected.outcome must be 'denied'"
        )
        assert expected.get("error_code"), (
            f"{path.name}: expected.error_code is required"
        )
        assert expected.get("message_substring"), (
            f"{path.name}: expected.message_substring is required"
        )
        assert isinstance(expected.get("denial_audit_record"), bool), (
            f"{path.name}: expected.denial_audit_record must be a bool"
        )
        attempt = fixture.get("attempt", {})
        assert attempt.get("kind") in ("transition", "create_tenant"), (
            f"{path.name}: attempt.kind must be transition or "
            "create_tenant"
        )
        assert attempt.get("tenant_id") == fixture.get("tenant_id"), (
            f"{path.name}: attempt.tenant_id must match the fixture's "
            "tenant_id"
        )
    print(f"{len(scenario_ids)} fixtures well-formed")


def test_required_scenarios_covered() -> None:
    covered = {fixture["scenario"] for _, fixture in load_fixtures()}
    missing = set(REQUIRED_SCENARIOS) - covered
    assert not missing, f"missing required denial scenarios: {missing}"
    print(f"all {len(REQUIRED_SCENARIOS)} required scenarios covered")


def test_seeded_denials_are_denied_with_audit() -> None:
    for path, fixture in load_fixtures():
        env = Env()
        try:
            run_setup(env, fixture["setup"])
            attempt = substitute_fresh_timestamps(fixture["attempt"])
            expected = fixture["expected"]
            tenant_id = attempt["tenant_id"]
            state_before = lifecycle_state_or_none(env, tenant_id)
            audit_count_before = len(env.store.load_audit_records())
            try:
                run_attempt(env, attempt)
            except ControlPlaneError as error:
                assert error.error_code == expected["error_code"], (
                    f"{path.name}: expected error_code "
                    f"{expected['error_code']!r}, got "
                    f"{error.error_code!r}"
                )
                assert expected["message_substring"] in error.message, (
                    f"{path.name}: message {error.message!r} does not "
                    f"carry {expected['message_substring']!r}"
                )
                if expected["denial_audit_record"]:
                    # emit_audit_record_on_denial (TR-09): the error
                    # carries the id of a persisted denial record with
                    # the addressed tenant_id and the error_code.
                    assert error.audit_record_id is not None, (
                        f"{path.name}: denial produced no audit record"
                    )
                    records = {
                        record["audit_record_id"]: record
                        for record in env.store.load_audit_records()
                    }
                    record = records.get(error.audit_record_id)
                    assert record is not None, (
                        f"{path.name}: audit record "
                        f"{error.audit_record_id} was not persisted"
                    )
                    assert record["outcome"] == "denied", (
                        f"{path.name}: audit outcome is "
                        f"{record['outcome']!r}, expected 'denied'"
                    )
                    assert record["tenant_id"] == tenant_id, (
                        f"{path.name}: denial audit record carries "
                        f"tenant_id {record['tenant_id']!r}, expected "
                        f"{tenant_id!r}"
                    )
                    assert record["error_code"] == (
                        expected["error_code"]
                    ), (
                        f"{path.name}: audit error_code "
                        f"{record['error_code']!r} != expected"
                    )
                    assert record["replay"] is False
                else:
                    # Creation denials happen before a tenant exists;
                    # the attempt must not have appended audit records.
                    assert len(env.store.load_audit_records()) == (
                        audit_count_before
                    ), (
                        f"{path.name}: unexpected audit records for a "
                        "pre-registration denial"
                    )
            else:
                raise AssertionError(
                    f"{path.name}: seeded denial was not denied "
                    f"(expected {expected['error_code']!r})"
                )
            # Deny-by-default: the denied attempt mutated nothing.
            state_after = lifecycle_state_or_none(env, tenant_id)
            assert state_after == state_before, (
                f"{path.name}: lifecycle_state changed on a denial: "
                f"{state_before!r} -> {state_after!r}"
            )
            print(
                f"DENIED as seeded: {fixture['scenario_id']} "
                f"({fixture['scenario']}) -> {expected['error_code']}"
            )
        finally:
            env.cleanup()


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
