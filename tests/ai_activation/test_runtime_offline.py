"""Offline tests for the Batch 24 AI/MCP runtime.

Plain python3 script: test_* functions with bare asserts, no pytest,
no cluster, no docker. Drives the whole controller flow in-process
with SqliteStore and a FakeGateway that routes envelopes through the
real mcpserver envelope builder.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(
    0, str(Path(__file__).resolve().parents[2] / "services" / "ai")
)

from airuntime import contracts, gateway, khook, mcpserver, policy  # noqa: E402
from airuntime.kagent import Kagent, run_investigation  # noqa: E402
from airuntime.modelprovider import get_provider  # noqa: E402
from airuntime.store import SqliteStore  # noqa: E402

T0 = "2026-07-10T00:00:00+00:00"


def _iso_plus(base: str, minutes: int) -> str:
    return (
        datetime.fromisoformat(base) + timedelta(minutes=minutes)
    ).isoformat()


class FakeGateway:
    """Routes agent_to_mcp envelopes straight into the mcpserver
    envelope builder, recording every envelope it sees."""

    def __init__(self) -> None:
        self.envelopes: list[dict[str, Any]] = []

    def __call__(
        self, envelope: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        self.envelopes.append(envelope)
        service = contracts.TOOL_TO_SERVICE.get(envelope["tool"])
        if service is None:
            return 403, {"decision": "deny", "reason": "unknown tool"}
        tool = contracts.MCP_CATALOG[service]["tool"]
        return 200, mcpserver.handle_invoke(tool, envelope)


def _trigger_body(correlation_id: str = "corr-0123456789abcdef") -> dict[str, Any]:
    return {
        "edge_version": "v1",
        "correlation_id": correlation_id,
        "event_type": "oom-kill",
        "source_namespace": "payments",
        "risk_class": "read.safe",
        "payload": {
            "event_id": "uid-1",
            "event_timestamp": T0,
            "cluster": "harness",
            "namespace": "payments",
            "object_kind": "Pod",
            "object_name": "checkout-7f9",
            "reason": "OOMKilled",
            "message": "container killed",
            "severity": "critical",
            "incident_correlation_key": correlation_id,
        },
    }


def _investigated_service(
    correlation_id: str = "corr-0123456789abcdef",
) -> tuple[Kagent, dict[str, Any], FakeGateway]:
    store = SqliteStore()
    store.init_schema()
    fake = FakeGateway()
    service = Kagent(store, {}, gateway_invoke=fake, auto_investigate=False)
    status, response = service.api.dispatch(
        "POST", "/triggers", _trigger_body(correlation_id)
    )
    assert status == 202, response
    casefile = run_investigation(service, response["casefile"])
    return service, casefile, fake


def test_casefile_schema_conformance() -> None:
    service, casefile, fake = _investigated_service()
    for field in contracts.CASEFILE_REQUIRED_FIELDS:
        assert field in casefile, f"casefile missing {field}"
    assert casefile["status"] == "awaiting-approval"
    assert casefile["evidence_handles"], "no evidence handles collected"
    assert casefile["approval_state"]["status"] == "pending"
    # All five read specialists plus CEO and summarizer reported.
    agents = [entry["agent"] for entry in casefile["agent_outputs"]]
    for specialist in contracts.SPECIALIST_TOOLS:
        assert specialist in agents
    assert contracts.CEO_AGENT in agents
    assert contracts.EVIDENCE_SUMMARIZER in agents
    # Dispatched tools match the specialists' bindings.
    dispatched = {f"{e['tool']}.{e['tool_version']}" for e in fake.envelopes}
    assert dispatched == set(contracts.SPECIALIST_TOOLS.values())
    # Trigger dedupe: same correlation id returns the active casefile.
    status, response = service.api.dispatch(
        "POST", "/triggers", _trigger_body()
    )
    assert status == 200 and response["deduplicated"]
    assert response["casefile"]["case_id"] == casefile["case_id"]


def test_approval_flow_grant() -> None:
    service, casefile, _fake = _investigated_service()
    approval = service.store.list_approvals(state="pending")[0]
    status, response = service.api.dispatch(
        "POST",
        f"/approvals/{approval['approval_id']}/decision",
        {"approver": "human-oncall", "decision": "approved"},
    )
    assert status == 200, response
    final = service.store.get_casefile(casefile["case_id"])
    assert final["status"] == "resolved"
    assert final["action_journal"][-1]["outcome"] == "executed"
    assert final["action_journal"][-1]["action"] == "runbook-plan.v1"
    stored = service.store.get_approval(approval["approval_id"])
    assert stored["state"] == "approved"
    decisions = [
        record["payload"].get("approval_decision")
        for record in service.store.audit_records()
        if record["event_type"] in ("approval-decision", "action-executed")
    ]
    assert "approved" in decisions


def test_approval_flow_reject() -> None:
    service, casefile, _fake = _investigated_service()
    approval = service.store.list_approvals(state="pending")[0]
    status, response = service.api.dispatch(
        "POST",
        f"/approvals/{approval['approval_id']}/decision",
        {"approver": "human-oncall", "decision": "rejected"},
    )
    assert status == 200, response
    final = service.store.get_casefile(casefile["case_id"])
    assert final["status"] == "rejected"
    assert final["action_journal"][-1]["outcome"] == "blocked"


def test_approval_self_approval_denied() -> None:
    service, _casefile, _fake = _investigated_service()
    approval = service.store.list_approvals(state="pending")[0]
    assert approval["requested_by"] == contracts.CEO_AGENT
    status, response = service.api.dispatch(
        "POST",
        f"/approvals/{approval['approval_id']}/decision",
        {"approver": contracts.CEO_AGENT, "decision": "approved"},
    )
    assert status == 400, response
    assert "self-approval" in response["error"]
    # The pure function raises too.
    try:
        policy.decide_approval(
            approval, contracts.CEO_AGENT, "approved", _iso_plus(T0, 1)
        )
        raise AssertionError("self-approval must raise")
    except ValueError:
        pass


def test_timeout_evaluation() -> None:
    approval = policy.new_approval(
        "case-1", "runbook-plan.v1", "write.high-risk", contracts.CEO_AGENT, T0
    )
    assert approval["deadline_at"] == _iso_plus(T0, 60)
    assert approval["warning_at"] == _iso_plus(T0, 30)
    # Escalation clock: role i escalates at deadline + cumulative SLA
    # of the roles before it -> +60, +90, +150 minutes from request.
    escalate_ats = [
        entry["escalate_at"] for entry in approval["escalation"]["chain"]
    ]
    assert escalate_ats == [
        _iso_plus(T0, 60), _iso_plus(T0, 90), _iso_plus(T0, 150)
    ]

    assert policy.evaluate_timeout(approval, _iso_plus(T0, 10))["status"] == "not_due"
    warning = policy.evaluate_timeout(approval, _iso_plus(T0, 31))
    assert warning["status"] == "warning"

    expired = policy.evaluate_timeout(approval, _iso_plus(T0, 61))
    assert expired["status"] == "expired"
    assert expired["outcome"] == "deny-and-escalate"
    roles = [event["role"] for event in expired["escalation_events"]]
    assert roles == ["oncall-sre"], roles
    assert expired["escalation_events"][0]["channels"] == list(
        contracts.NOTIFY_CHANNELS
    )
    assert not expired["final_denial"]

    whole_chain = policy.evaluate_timeout(approval, _iso_plus(T0, 151))
    assert [e["role"] for e in whole_chain["escalation_events"]] == [
        "oncall-sre", "incident-commander", "platform-director"
    ]
    assert whole_chain["final_denial"]

    # API path against the REAL stored approval.
    service, casefile, _fake = _investigated_service()
    stored = service.store.list_approvals(state="pending")[0]
    as_of = _iso_plus(stored["deadline_at"], 1)
    status, evaluation = service.api.dispatch(
        "POST",
        f"/approvals/{stored['approval_id']}/evaluate-timeout",
        {"as_of": as_of},
    )
    assert status == 200 and evaluation["status"] == "expired"
    final = service.store.get_casefile(casefile["case_id"])
    assert final["status"] == "rejected"
    assert final["action_journal"][-1]["outcome"] == "blocked"
    assert service.store.get_approval(stored["approval_id"])["state"] == "expired"
    escalation_audits = [
        record for record in service.store.audit_records()
        if record["event_type"] == "approval-escalation"
    ]
    assert len(escalation_audits) == 1
    assert escalation_audits[0]["payload"]["role"] == "oncall-sre"


def test_policy_unclassified_tool_denied() -> None:
    assert policy.classify_tool("made-up-tool.v1") is None
    decision, reason = policy.policy_decision("made-up-tool.v1", True)
    assert decision == "deny"
    assert "unclassified" in reason


def test_redaction_masks_and_denies() -> None:
    structured = {
        "credentials_probe": {"api_key": "sample-key-material"},
        "password": "hunter2",
        "records": [
            {"domain": "credentials", "value": "leak"},
            {"domain": "metrics", "value": "ok"},
        ],
    }
    redacted, metadata = policy.redact(structured)
    assert redacted["credentials_probe"]["api_key"] == "***redacted***"
    assert redacted["password"] == "***redacted***"
    assert redacted["records"] == [{"domain": "metrics", "value": "ok"}]
    assert "api_key" in metadata["masked_fields"]
    assert "password" in metadata["masked_fields"]
    assert metadata["denied_domains"] == ["credentials"]
    assert metadata["field_level_redaction"] and metadata["secret_masking"]


def test_tool_response_validation_catches_missing_fields() -> None:
    violations = policy.validate_tool_response({})
    assert len(violations) == len(contracts.TOOL_RESPONSE_REQUIRED_FIELDS)
    good = mcpserver.handle_invoke(
        "incident-search",
        {
            "tenant_scope": {"namespace": "n", "tenant": "t", "team": "x"},
            "input": {"object_name": "pod-a"},
        },
    )
    assert policy.validate_tool_response(good) == []
    bad = dict(good)
    bad["confidence"] = 1.5
    assert any("confidence" in v for v in policy.validate_tool_response(bad))
    bad = dict(good)
    bad["safety_class"] = "read.reckless"
    assert any("safety_class" in v for v in policy.validate_tool_response(bad))
    bad = dict(good)
    bad["time_window"] = {"start": T0}
    assert any("time_window" in v for v in policy.validate_tool_response(bad))


def test_action_preconditions() -> None:
    ok, reasons = policy.check_action_preconditions(
        "runbook-plan.v1",
        {
            "policy_decision": "allow",
            "approval": None,
            "rollback_plan_present": True,
            "valid_target": True,
        },
    )
    assert not ok and any("approval" in r for r in reasons)
    approved = {"state": "approved"}
    ok, reasons = policy.check_action_preconditions(
        "remediation-execute.v1",
        {
            "policy_decision": "allow",
            "approval": approved,
            "rollback_plan_present": True,
            "change_ticket_present": False,
            "valid_target": True,
        },
    )
    assert not ok and any("change ticket" in r for r in reasons)
    ok, reasons = policy.check_action_preconditions(
        "runbook-plan.v1",
        {
            "policy_decision": "allow",
            "approval": approved,
            "rollback_plan_present": True,
            "valid_target": True,
        },
    )
    assert ok and reasons == []
    ok, _reasons = policy.check_action_preconditions(
        "incident-casefile.update.v1",
        {"policy_decision": "allow", "approval": None, "valid_target": True},
    )
    assert ok


def _invoke_body(
    tool: str,
    tool_version: str = "v1",
    caller_agent: str = "incident-investigator",
) -> dict[str, Any]:
    return {
        "edge_version": "v1",
        "caller_agent": caller_agent,
        "tool": tool,
        "tool_version": tool_version,
        "tenant_scope": {
            "namespace": "payments",
            "tenant": "tenant-demo",
            "team": "sre",
        },
        "input": {"object_name": "checkout-7f9"},
    }


def test_gateway_offline() -> None:
    gw = gateway.Gateway({"HEARTBEAT_DISABLED": "1"})
    original_http_json = gateway.http_json

    def fake_http_json(
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        service = url.split("//", 1)[1].split(".", 1)[0]
        tool = contracts.MCP_CATALOG[service]["tool"]
        return 200, mcpserver.handle_invoke(tool, body or {})

    gateway.http_json = fake_http_json
    try:
        # Read-path invoke: valid envelope, redaction provably applied.
        status, response = gw.api.dispatch(
            "POST", "/invoke", _invoke_body("incident-search")
        )
        assert status == 200, response
        assert policy.validate_tool_response(response) == []
        assert response["redaction_metadata"]["secret_masking"]
        probe = response["structured_data"]["credentials_probe"]
        assert probe["api_key"] == "***redacted***"
        assert "api_key" in response["redaction_metadata"]["masked_fields"]

        # Envelope validation: missing field denied.
        incomplete = _invoke_body("incident-search")
        del incomplete["tenant_scope"]
        status, response = gw.api.dispatch("POST", "/invoke", incomplete)
        assert status == 400

        # Scope mismatch: incomplete tenant_scope denied.
        unscoped = _invoke_body("incident-search")
        del unscoped["tenant_scope"]["team"]
        status, response = gw.api.dispatch("POST", "/invoke", unscoped)
        assert status == 403 and response["decision"] == "deny"

        # Unknown tool denied + audited.
        status, response = gw.api.dispatch(
            "POST", "/invoke", _invoke_body("made-up-tool")
        )
        assert status == 403 and response["decision"] == "deny"

        # Write tool without approval_context blocked (caller must be
        # the bound agent, or the binding check denies first).
        status, response = gw.api.dispatch(
            "POST",
            "/invoke",
            _invoke_body("runbook-plan", caller_agent="runbook-planner"),
        )
        assert status == 403 and "approval_context" in response["reason"]

        # Redaction query bound: a window wider than 24h is denied.
        wide = _invoke_body("incident-search")
        wide["input"]["window"] = {
            "start": T0,
            "end": _iso_plus(T0, 60 * 25),
        }
        status, response = gw.api.dispatch("POST", "/invoke", wide)
        assert status == 403 and "time window" in response["reason"]

        # Transport failure maps to timeout posture: deny, no retries.
        calls = {"count": 0}

        def raising_http_json(*args: Any, **kwargs: Any) -> tuple[int, dict]:
            calls["count"] += 1
            raise TimeoutError("simulated tool timeout")

        gateway.http_json = raising_http_json
        status, response = gw.api.dispatch(
            "POST", "/invoke", _invoke_body("incident-search")
        )
        assert status == 504 and response["decision"] == "deny"
        assert calls["count"] == 1, "retry_attempts must be 0"

        # Every denial and success above produced an audit event.
        status, journal = gw.api.dispatch("GET", "/journal", {})
        assert status == 200
        outcomes = [e["final_action_outcome"] for e in journal["events"]]
        assert "executed" in outcomes and "blocked" in outcomes
        assert "failed" in outcomes
        for event in journal["events"]:
            for field in contracts.AUDIT_REQUIRED_FIELDS:
                assert field in event, f"audit event missing {field}"

        # Catalog surface: all seven services, fingerprint stable.
        status, catalog = gw.api.dispatch("GET", "/catalog", {})
        assert status == 200 and len(catalog["services"]) == 7
        assert catalog["contract_fingerprint"] == gateway.contract_fingerprint()
    finally:
        gateway.http_json = original_http_json


def test_agent_binding_enforcement() -> None:
    gw = gateway.Gateway({"HEARTBEAT_DISABLED": "1"})
    original_http_json = gateway.http_json

    def fake_http_json(
        method: str,
        url: str,
        body: dict[str, Any] | None = None,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        service = url.split("//", 1)[1].split(".", 1)[0]
        tool = contracts.MCP_CATALOG[service]["tool"]
        return 200, mcpserver.handle_invoke(tool, body or {})

    gateway.http_json = fake_http_json
    try:
        # (a) The CEO class denies write.high-risk: even with a valid
        # approval_context, ops-ceo-agent cannot invoke runbook-plan.
        approved = {"state": "approved"}
        ceo_body = _invoke_body(
            "runbook-plan", caller_agent=contracts.CEO_AGENT
        )
        ceo_body["approval_context"] = {
            "policy_decision": "allow",
            "approval": approved,
            "rollback_plan_present": True,
            "valid_target": True,
        }
        status, response = gw.api.dispatch("POST", "/invoke", ceo_body)
        assert status == 403 and response["decision"] == "deny"
        # The tool-list check trips first: runbook-plan.v1 is not
        # among the CEO's bound tools (default deny).
        assert "no binding" in response["reason"]

        # (b) runbook-planner is the bound specialist_action agent:
        # with a satisfied approval_context the call goes through.
        planner_body = _invoke_body(
            "runbook-plan", caller_agent="runbook-planner"
        )
        planner_body["input"].update(
            approval=approved, rollback_plan={"steps": ["undo"]}
        )
        planner_body["approval_context"] = {
            "policy_decision": "allow",
            "approval": approved,
            "rollback_plan_present": True,
            "valid_target": True,
        }
        status, response = gw.api.dispatch("POST", "/invoke", planner_body)
        assert status == 200, response
        assert response["structured_data"]["outcome"] == "executed"

        # (c) Unknown agent: default_tool_policy deny.
        status, response = gw.api.dispatch(
            "POST",
            "/invoke",
            _invoke_body("incident-search", caller_agent="rogue-agent"),
        )
        assert status == 403 and "unknown caller" in response["reason"]

        # (d) Bound agent, unbound tool: incident-investigator has no
        # binding for trace-investigation.v1.
        status, response = gw.api.dispatch(
            "POST",
            "/invoke",
            _invoke_body(
                "trace-investigation", caller_agent="incident-investigator"
            ),
        )
        assert status == 403 and "no binding" in response["reason"]

        # Pure-function surface agrees with the gateway.
        allowed, _ = policy.check_agent_binding(
            "trace-analyst", "trace-investigation.v1", "read.sensitive"
        )
        assert allowed
        # deny_risk_classes guards upward reclassification drift: a
        # bound tool whose risk class lands in the class deny set is
        # still denied.
        denied, reason = policy.check_agent_binding(
            contracts.CEO_AGENT,
            "incident-casefile.update.v1",
            "write.high-risk",
        )
        assert not denied and "denies risk class" in reason
    finally:
        gateway.http_json = original_http_json


def _raw_event(
    uid: str,
    reason: str = "OOMKilled",
    name: str = "checkout-7f9",
    ts: str = T0,
) -> dict[str, Any]:
    return {
        "metadata": {"uid": uid, "creationTimestamp": ts, "namespace": "payments"},
        "involvedObject": {
            "kind": "Pod",
            "namespace": "payments",
            "name": name,
        },
        "reason": reason,
        "message": f"{reason} on {name}",
        "lastTimestamp": ts,
    }


def test_khook_matching_and_dedupe() -> None:
    processor = khook.EventProcessor("harness")
    envelope = processor.process(_raw_event("uid-1"), now_ts=0.0)
    assert envelope is not None
    assert envelope["event_type"] == "oom-kill"
    assert envelope["risk_class"] == "read.safe"
    assert len(envelope["correlation_id"]) >= 8
    assert envelope["payload"]["severity"] == "critical"
    for field in contracts.REQUIRED_EVENT_FIELDS:
        assert field in envelope["payload"]

    # Identical incident within the dedupe window: suppressed.
    assert processor.process(_raw_event("uid-2"), now_ts=10.0) is None
    assert processor.counters["deduped"] == 1
    # Same Event object re-listed on the next poll: never re-dispatched.
    assert processor.process(_raw_event("uid-1"), now_ts=20.0) is None
    assert processor.counters["duplicate_uid"] == 1
    # Non-matching reason ignored.
    assert (
        processor.process(_raw_event("uid-3", reason="Scheduled"), now_ts=30.0)
        is None
    )
    assert processor.counters["ignored"] == 1
    # Correlation key is stable across identical incidents.
    key_a = khook.correlation_key(
        khook.normalize_event(_raw_event("uid-a"), "harness")
    )
    key_b = khook.correlation_key(
        khook.normalize_event(_raw_event("uid-b"), "harness")
    )
    assert key_a == key_b

    # Burst: 11 events for one key inside 60s -> one aggregate summary.
    burst = khook.EventProcessor("harness")
    dispatches: list[dict[str, Any]] = []
    for index in range(11):
        result = burst.process(
            _raw_event(f"burst-{index}"), now_ts=float(index)
        )
        if result is not None:
            dispatches.append(result)
    assert len(dispatches) == 2  # initial dispatch + burst summary
    summary = dispatches[-1]
    assert summary["payload"]["burst"]
    assert summary["payload"]["suppressed_event_count"] == 10
    assert summary["payload"]["first_seen_at"] == T0
    assert summary["payload"]["last_seen_at"] == T0
    assert burst.counters["burst_summaries"] == 1
    # A 12th event within the same window stays suppressed.
    assert burst.process(_raw_event("burst-11"), now_ts=11.0) is None
    assert burst.counters["burst_suppressed"] == 1


def test_mcpserver_tools() -> None:
    scope = {"namespace": "payments", "tenant": "tenant-demo", "team": "sre"}
    read_tools = (
        "incident-search",
        "graph-analysis",
        "trace-investigation",
        "metrics-correlation",
        "change-intelligence",
    )
    for tool in read_tools:
        envelope = mcpserver.handle_invoke(
            tool,
            {"tenant_scope": scope, "input": {"object_name": "checkout-7f9"}},
        )
        assert policy.validate_tool_response(envelope) == [], tool
        assert envelope["safety_class"] == contracts.TOOL_RISK_CLASSES[
            f"{tool}.v1"
        ]
        # Scope fields mirrored into every finding item.
        for value in envelope["structured_data"].values():
            if isinstance(value, list):
                for item in value:
                    assert item["namespace"] == "payments"
                    assert item["tenant"] == "tenant-demo"
                    assert item["team"] == "sre"
        # The masked-content demo field is always present (raw here;
        # the gateway masks it before anything leaves the boundary).
        assert (
            envelope["structured_data"]["credentials_probe"]["api_key"]
            == "sample-key-material"
        )

    read_case = mcpserver.handle_invoke(
        "incident-casefile",
        {
            "tenant_scope": scope,
            "input": {"op": "read", "casefile": {"case_id": "c1"}},
        },
    )
    assert policy.validate_tool_response(read_case) == []
    assert read_case["structured_data"]["casefile"] == {"case_id": "c1"}
    assert read_case["safety_class"] == "read.sensitive"

    update_case = mcpserver.handle_invoke(
        "incident-casefile",
        {
            "tenant_scope": scope,
            "input": {"op": "update", "update": {"status": "triaging"}},
        },
    )
    assert policy.validate_tool_response(update_case) == []
    assert update_case["safety_class"] == "write.low-risk"
    assert update_case["structured_data"]["acknowledged"]

    executed = mcpserver.handle_invoke(
        "runbook-execution",
        {
            "tool": "runbook-plan",
            "tool_version": "v1",
            "tenant_scope": scope,
            "input": {
                "object_name": "checkout-7f9",
                "approval": {"state": "approved"},
                "rollback_plan": {"steps": ["undo"]},
            },
        },
    )
    assert policy.validate_tool_response(executed) == []
    assert executed["structured_data"]["outcome"] == "executed"
    assert executed["structured_data"]["plan_steps"]
    assert executed["safety_class"] == "write.high-risk"

    # The same service host answers remediation-execute.v1 with the
    # REQUEST's classification, not a hardcoded runbook-plan class.
    remediation = mcpserver.handle_invoke(
        "runbook-execution",
        {
            "tool": "remediation-execute",
            "tool_version": "v1",
            "tenant_scope": scope,
            "input": {
                "object_name": "checkout-7f9",
                "approval": {"state": "approved"},
                "rollback_plan": {"steps": ["undo"]},
            },
        },
    )
    assert policy.validate_tool_response(remediation) == []
    assert remediation["safety_class"] == "write.critical"

    blocked = mcpserver.handle_invoke(
        "runbook-execution",
        {
            "tool": "runbook-plan",
            "tool_version": "v1",
            "tenant_scope": scope,
            "input": {"object_name": "checkout-7f9"},
        },
    )
    assert policy.validate_tool_response(blocked) == []
    assert blocked["structured_data"]["outcome"] == "blocked"
    assert blocked["confidence"] == 1.0
    assert blocked["safety_class"] == "write.high-risk"


def test_model_provider_deterministic() -> None:
    provider = get_provider("local-stub")
    request = {
        "provider": "local-stub",
        "model_ref": "rehearsal-default",
        "tenant_id": "tenant-demo",
        "redaction_profile": "standard-v1",
        "casefile_id": "case-1",
        "max_output_tokens": 512,
        "intent": "analyze OOMKilled on checkout-7f9",
    }
    first = provider.complete(dict(request))
    second = provider.complete(dict(request))
    assert first == second
    for field in contracts.MODEL_RESPONSE_FIELDS:
        assert field in first
    assert first["usage"]["input_tokens"] > 0
    assert first["stop_reason"] == "end_turn"
    # Missing contract field fails loudly.
    try:
        provider.complete({"provider": "local-stub"})
        raise AssertionError("missing request fields must raise")
    except ValueError:
        pass
    # The reference provider must never run from this codebase.
    try:
        get_provider("anthropic-reference")
        raise AssertionError("anthropic-reference must raise")
    except NotImplementedError as exc:
        assert "secrets backend adapter" in str(exc)


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
