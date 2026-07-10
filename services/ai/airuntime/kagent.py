"""KAgent controller: casefile orchestration, the CEO/manager/specialist
investigation run, action-gate approvals, and the audit trail (TR-15).

The investigation is a module-level function taking the service and a
casefile so offline tests drive it directly with a fake gateway; the
HTTP trigger route runs the same function in a background thread so the
POST returns fast with the casefile id.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable

from airuntime import contracts, policy
from airuntime.httpd import JsonApi, http_json, serve
from airuntime.modelprovider import get_provider
from airuntime.store import AuditRecord, Store, store_from_env, utc_now

GatewayInvoke = Callable[[dict[str, Any]], tuple[int, dict[str, Any]]]

_TERMINAL_STATUSES = ("resolved", "closed", "rejected")
_REDACTION_PROFILE = "standard-v1"


class Kagent:
    """Controller state + JsonApi routes over the persistence layer."""

    def __init__(
        self,
        store: Store,
        env: dict[str, str],
        gateway_invoke: GatewayInvoke | None = None,
        auto_investigate: bool = True,
    ) -> None:
        self.store = store
        self.gateway_url = env.get(
            "GATEWAY_URL",
            "http://ai-gateway.ai-gateway.svc.cluster.local:8082",
        )
        self.tenant_id = env.get("TENANT_ID", "tenant-demo")
        self.team = env.get("TEAM", "sre")
        self.model_ref = env.get("MODEL_REF", "rehearsal-default")
        self.provider = get_provider(
            env.get("MODEL_PROVIDER", contracts.REHEARSAL_PROVIDER)
        )
        self.gateway_invoke = gateway_invoke or self._http_gateway_invoke
        self.auto_investigate = auto_investigate
        self.usage_totals = {"input_tokens": 0, "output_tokens": 0}
        self.api = JsonApi("kagent")
        self.api.route("POST", "/triggers", self._handle_trigger)
        self.api.route("POST", "/approvals", self._handle_approval_action)
        self.api.route("GET", "/casefiles", self._handle_get_casefiles)
        self.api.route("GET", "/approvals", self._handle_get_approvals)
        self.api.route("GET", "/audit", self._handle_get_audit)
        self.api.route("GET", "/state", self._handle_get_state)

    # -- plumbing ------------------------------------------------------

    def _http_gateway_invoke(
        self, envelope: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        # Timeout above the gateway's own upper bound so the gateway,
        # not this client, is the component that times a tool out.
        return http_json(
            "POST", f"{self.gateway_url}/invoke", envelope, timeout=35.0
        )

    def _save(self, casefile: dict[str, Any]) -> None:
        casefile["updated_at"] = utc_now()
        self.store.upsert_casefile(casefile)

    def _audit(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        casefile_id: str | None,
    ) -> None:
        self.store.append_audit(
            AuditRecord(
                event_type=event_type,
                actor=actor,
                payload=payload,
                casefile_id=casefile_id,
                tenant_id=self.tenant_id,
            )
        )

    def _record_usage(self, usage: dict[str, int]) -> int:
        self.usage_totals["input_tokens"] += usage["input_tokens"]
        self.usage_totals["output_tokens"] += usage["output_tokens"]
        return usage["input_tokens"] + usage["output_tokens"]

    def _complete(self, intent: str, casefile_id: str) -> tuple[str, int]:
        """Model call via the configured provider; returns (text, tokens)."""
        response = self.provider.complete(
            {
                "provider": self.provider.name,
                "model_ref": self.model_ref,
                "tenant_id": self.tenant_id,
                "redaction_profile": _REDACTION_PROFILE,
                "casefile_id": casefile_id,
                "max_output_tokens": 512,
                "intent": intent,
            }
        )
        return response["content"], self._record_usage(response["usage"])

    # -- routes --------------------------------------------------------

    def _handle_trigger(
        self, _subpath: str, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        missing = [
            f for f in contracts.KHOOK_TO_KAGENT_FIELDS if f not in body
        ]
        if missing:
            return 400, {
                "error": f"khook_to_kagent envelope missing fields: {missing}"
            }
        correlation_id = body["correlation_id"]
        if len(str(correlation_id)) < 8:
            return 400, {"error": "correlation_id must be >= 8 chars"}
        # Controller-side dedupe: an active casefile for the same
        # correlation id absorbs the trigger instead of forking a
        # duplicate investigation.
        for existing in self.store.list_casefiles():
            if (
                existing.get("lineage", {}).get("correlation_id")
                == correlation_id
                and existing["status"] not in _TERMINAL_STATUSES
            ):
                return 200, {"casefile": existing, "deduplicated": True}

        payload = body["payload"]
        case_id = str(uuid.uuid4())
        now = utc_now()
        casefile: dict[str, Any] = {
            "schema_version": "v1",
            "case_id": case_id,
            "status": "open",
            "incident_context": {
                "tenant": self.tenant_id,
                "namespace": payload.get("namespace", ""),
                "summary": (
                    f"{payload.get('reason', body['event_type'])}: "
                    f"{payload.get('message', '')}"
                ),
                "object_name": payload.get("object_name", ""),
                "reason": payload.get("reason", ""),
                "severity": payload.get("severity", ""),
            },
            "agent_outputs": [],
            "evidence_handles": [],
            "approval_state": {"required": False, "status": "not-required"},
            "action_journal": [],
            "lineage": {
                "correlation_id": correlation_id,
                "workflow_id": str(uuid.uuid4()),
            },
            "created_at": now,
            "updated_at": now,
            # Store-column aliases: the persistence contract keys rows
            # by casefile_id/tenant_id; the casefile schema uses
            # case_id and incident_context.tenant.
            "casefile_id": case_id,
            "tenant_id": self.tenant_id,
        }
        self.store.upsert_casefile(casefile)
        self._audit(
            "casefile-created",
            "kagent-controller",
            {"correlation_id": correlation_id, "event_type": body["event_type"]},
            case_id,
        )
        if self.auto_investigate:
            threading.Thread(
                target=run_investigation,
                args=(self, casefile),
                daemon=True,
            ).start()
        return 202, {"case_id": case_id, "casefile": casefile}

    def _handle_approval_action(
        self, subpath: str, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        parts = subpath.split("/")
        if len(parts) != 2 or parts[1] not in ("decision", "evaluate-timeout"):
            return 404, {
                "error": "expected /approvals/<id>/{decision|evaluate-timeout}"
            }
        approval_id, action = parts
        approval = self.store.get_approval(approval_id)
        if approval is None:
            return 404, {"error": f"no approval {approval_id}"}
        if action == "decision":
            return self._decide(approval, body)
        return self._evaluate_timeout(approval, body)

    def _decide(
        self, approval: dict[str, Any], body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        try:
            updated = policy.decide_approval(
                approval,
                approver=body["approver"],
                decision=body["decision"],
                decided_at=utc_now(),
                change_ticket=body.get("change_ticket"),
            )
        except ValueError as exc:
            return 400, {"error": str(exc)}
        self.store.update_approval(updated)
        casefile = self.store.get_casefile(updated["casefile_id"])
        if casefile is None:
            raise RuntimeError(
                f"approval {updated['approval_id']} references missing "
                f"casefile {updated['casefile_id']}"
            )
        self._audit(
            "approval-decision",
            updated["approver"],
            policy.build_audit_event(
                invoker_identity=updated["approver"],
                agent_identity=contracts.CEO_AGENT,
                tool_call=updated["tool"],
                tool_parameters_redacted={},
                policy_decision="allow",
                approval_decision=updated["decision"],
                final_action_outcome=(
                    "executed"
                    if updated["decision"] == "approved"
                    else "blocked"
                ),
                latency_ms=0,
                event_time=utc_now(),
            ),
            casefile["case_id"],
        )
        if updated["decision"] == "approved":
            return self._execute_approved_action(casefile, updated)
        # execution_gates.feed_rejection_into_casefile: the rejection is
        # part of the case record, not a silent drop.
        casefile["approval_state"] = {
            "required": True,
            "status": "rejected",
            "approval_ref": updated["approval_id"],
        }
        casefile["action_journal"].append(
            {
                "action": updated["tool"],
                "outcome": "blocked",
                "recorded_at": utc_now(),
            }
        )
        casefile["status"] = "rejected"
        self._save(casefile)
        return 200, {"approval": updated, "casefile": casefile}

    def _execute_approved_action(
        self, casefile: dict[str, Any], approval: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        casefile["status"] = "executing"
        casefile["approval_state"] = {
            "required": True,
            "status": "approved",
            "approval_ref": approval["approval_id"],
        }
        self._save(casefile)
        context = casefile["incident_context"]
        tool, tool_version = approval["tool"].rsplit(".", 1)
        rollback_plan = {
            "steps": [
                f"roll back {context.get('object_name', 'target')} to the "
                f"previous revision",
                "re-verify readiness probes",
            ]
        }
        # The CEO class denies write.high-risk/write.critical, so the
        # approved action executes as runbook-planner - the only agent
        # bound to runbook-plan.v1 (specialist_action, approval-gated).
        # The human approver remains invoker_identity in the audit.
        envelope = {
            "edge_version": contracts.EDGE_VERSION,
            "caller_agent": "runbook-planner",
            "tool": tool,
            "tool_version": tool_version,
            "tenant_scope": {
                "namespace": context["namespace"],
                "tenant": self.tenant_id,
                "team": self.team,
            },
            "input": {
                "object_name": context.get("object_name", ""),
                "approval": approval,
                "rollback_plan": rollback_plan,
            },
            "approval_context": {
                "policy_decision": "allow",
                "approval": approval,
                "rollback_plan_present": True,
                "valid_target": True,
            },
        }
        started = time.monotonic()
        status, payload = self.gateway_invoke(envelope)
        latency_ms = int((time.monotonic() - started) * 1000)
        if status == 200:
            outcome = payload.get("structured_data", {}).get(
                "outcome", "executed"
            )
        else:
            outcome = "blocked"
        self._audit(
            "action-executed",
            "runbook-planner",
            policy.build_audit_event(
                invoker_identity=approval["approver"],
                # The executing agent identity, not the orchestrator:
                # the dispatch runs as runbook-planner (the only agent
                # bound to runbook-plan.v1).
                agent_identity="runbook-planner",
                tool_call=approval["tool"],
                tool_parameters_redacted={"object_name": context.get(
                    "object_name", ""
                )},
                policy_decision="allow",
                approval_decision="approved",
                final_action_outcome=outcome,
                latency_ms=latency_ms,
                event_time=utc_now(),
                evidence_handles=list(payload.get("evidence_handles", [])),
                target_resources=[
                    f"{context['namespace']}/{context.get('object_name', '*')}"
                ],
            ),
            casefile["case_id"],
        )
        casefile["action_journal"].append(
            {
                "action": approval["tool"],
                "outcome": outcome,
                "recorded_at": utc_now(),
            }
        )
        casefile["evidence_handles"].extend(
            payload.get("evidence_handles", [])
        )
        casefile["status"] = "resolved" if outcome == "executed" else "rejected"
        self._save(casefile)
        return 200, {"casefile": casefile, "outcome": outcome}

    def _evaluate_timeout(
        self, approval: dict[str, Any], body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        as_of = body.get("as_of")
        if not as_of:
            return 400, {"error": "as_of is required"}
        evaluation = policy.evaluate_timeout(approval, as_of)
        if evaluation["status"] != "expired":
            return 200, evaluation
        approval["state"] = "expired"
        self.store.update_approval(approval)
        casefile = self.store.get_casefile(approval["casefile_id"])
        if casefile is None:
            raise RuntimeError(
                f"approval {approval['approval_id']} references missing "
                f"casefile {approval['casefile_id']}"
            )
        for event in evaluation["escalation_events"]:
            self._audit(
                "approval-escalation",
                "kagent-controller",
                {
                    "approval_id": approval["approval_id"],
                    "role": event["role"],
                    "escalated_at": event["escalated_at"],
                    "channels": event["channels"],
                },
                casefile["case_id"],
            )
        self._audit(
            "approval-timeout-deny",
            "kagent-controller",
            policy.build_audit_event(
                invoker_identity="kagent-controller",
                agent_identity=contracts.CEO_AGENT,
                tool_call=approval["tool"],
                tool_parameters_redacted={},
                policy_decision="deny",
                approval_decision="rejected",
                final_action_outcome="blocked",
                latency_ms=0,
                event_time=as_of,
            ),
            casefile["case_id"],
        )
        casefile["approval_state"] = {
            "required": True,
            "status": "expired",
            "approval_ref": approval["approval_id"],
        }
        casefile["action_journal"].append(
            {
                "action": approval["tool"],
                "outcome": "blocked",
                "recorded_at": as_of,
            }
        )
        casefile["status"] = "rejected"
        self._save(casefile)
        return 200, evaluation

    def _handle_get_casefiles(
        self, subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        if subpath:
            casefile = self.store.get_casefile(subpath)
            if casefile is None:
                return 404, {"error": f"no casefile {subpath}"}
            return 200, {"casefile": casefile}
        return 200, {"casefiles": self.store.list_casefiles()}

    def _handle_get_approvals(
        self, subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        if subpath:
            approval = self.store.get_approval(subpath)
            if approval is None:
                return 404, {"error": f"no approval {subpath}"}
            return 200, {"approval": approval}
        return 200, {"approvals": self.store.list_approvals()}

    def _handle_get_audit(
        self, _subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        return 200, {"records": self.store.audit_records()}

    def _handle_get_state(
        self, _subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        approvals_by_state: dict[str, int] = {}
        for approval in self.store.list_approvals():
            state = approval["state"]
            approvals_by_state[state] = approvals_by_state.get(state, 0) + 1
        return 200, {
            "casefiles": len(self.store.list_casefiles()),
            "approvals_by_state": approvals_by_state,
            "audit_records": len(self.store.audit_records()),
            "model_usage": dict(self.usage_totals),
        }


def run_investigation(
    service: Kagent, casefile: dict[str, Any]
) -> dict[str, Any]:
    """Execute the multi-agent investigation plan for one casefile.

    Communication edges honored: ceo->manager (delegation),
    manager->specialist (dispatch); specialists never talk to each
    other - each reports back through its agent_outputs entry.
    """
    store = service.store
    case_id = casefile["case_id"]
    context = casefile["incident_context"]

    casefile["status"] = "triaging"
    service._save(casefile)
    service._audit(
        "status-transition", contracts.CEO_AGENT, {"status": "triaging"}, case_id
    )

    # ceo -> manager delegation (agent_to_agent edge).
    delegation_ref = str(uuid.uuid4())
    delegation = {
        "edge_version": contracts.EDGE_VERSION,
        "from_agent": contracts.CEO_AGENT,
        "to_agent": contracts.INVESTIGATION_MANAGER,
        "objective": f"investigate: {context['summary']}",
        "findings": [],
        "evidence_handles": [],
        "confidence": 0.0,
    }
    casefile["agent_outputs"].append(
        {
            "agent": contracts.CEO_AGENT,
            "output_ref": delegation_ref,
            "recorded_at": utc_now(),
        }
    )
    service._audit(
        "agent-delegation",
        contracts.CEO_AGENT,
        {"output_ref": delegation_ref, "envelope": delegation},
        case_id,
    )

    casefile["status"] = "investigating"
    service._save(casefile)
    service._audit(
        "status-transition",
        contracts.INVESTIGATION_MANAGER,
        {"status": "investigating"},
        case_id,
    )

    # manager -> specialist dispatch, sequential per the plan.
    for specialist, tool_id in contracts.SPECIALIST_TOOLS.items():
        tool, tool_version = tool_id.rsplit(".", 1)
        envelope = {
            "edge_version": contracts.EDGE_VERSION,
            "caller_agent": specialist,
            "tool": tool,
            "tool_version": tool_version,
            "tenant_scope": {
                "namespace": context["namespace"],
                "tenant": service.tenant_id,
                "team": service.team,
            },
            "input": {
                "object_name": context.get("object_name", ""),
                "reason": context.get("reason", ""),
                "summary": context["summary"],
            },
        }
        started = time.monotonic()
        status, payload = service.gateway_invoke(envelope)
        latency_ms = int((time.monotonic() - started) * 1000)
        if status != 200:
            raise RuntimeError(
                f"specialist {specialist} tool {tool_id} denied by "
                f"gateway ({status}): {payload}"
            )
        finding, tokens = service._complete(
            f"{specialist} findings for {context['summary']}", case_id
        )
        output_ref = str(uuid.uuid4())
        casefile["evidence_handles"].extend(
            payload.get("evidence_handles", [])
        )
        casefile["agent_outputs"].append(
            {
                "agent": specialist,
                "output_ref": output_ref,
                "recorded_at": utc_now(),
            }
        )
        service._audit(
            "specialist-finding",
            specialist,
            {
                "output_ref": output_ref,
                "finding": finding,
                **policy.build_audit_event(
                    invoker_identity=specialist,
                    agent_identity=specialist,
                    tool_call=tool_id,
                    tool_parameters_redacted=policy.redact(
                        envelope["input"]
                    )[0],
                    policy_decision="allow",
                    approval_decision="not-required",
                    final_action_outcome="executed",
                    latency_ms=latency_ms,
                    event_time=utc_now(),
                    evidence_handles=list(
                        payload.get("evidence_handles", [])
                    ),
                    tokens=tokens,
                ),
            },
            case_id,
        )
        service._save(casefile)

    # Synthesis: evidence-summarizer has no tool binding.
    synthesis, tokens = service._complete(
        f"synthesize evidence for {context['summary']}", case_id
    )
    summarizer_ref = str(uuid.uuid4())
    casefile["agent_outputs"].append(
        {
            "agent": contracts.EVIDENCE_SUMMARIZER,
            "output_ref": summarizer_ref,
            "recorded_at": utc_now(),
        }
    )
    service._audit(
        "evidence-synthesis",
        contracts.EVIDENCE_SUMMARIZER,
        {"output_ref": summarizer_ref, "synthesis": synthesis,
         "tokens": tokens},
        case_id,
    )

    # CEO proposes the write-path action; the gate stops here until a
    # human decision arrives via the approvals API.
    tool_id = "runbook-plan.v1"
    risk_class = policy.classify_tool(tool_id)
    if risk_class is None:
        raise RuntimeError(f"{tool_id} lost its risk classification")
    decision, reason = policy.policy_decision(tool_id, True)
    if decision != "allow":
        raise RuntimeError(f"CEO action proposal denied: {reason}")
    if not policy.approval_required(risk_class):
        raise RuntimeError(
            f"{tool_id} is {risk_class} and must require approval"
        )
    approval = policy.new_approval(
        case_id, tool_id, risk_class, contracts.CEO_AGENT, utc_now()
    )
    store.insert_approval(approval)
    casefile["approval_state"] = {
        "required": True,
        "status": "pending",
        "approval_ref": approval["approval_id"],
    }
    casefile["status"] = "awaiting-approval"
    service._save(casefile)
    service._audit(
        "approval-requested",
        contracts.CEO_AGENT,
        {
            "approval_id": approval["approval_id"],
            "tool": tool_id,
            "risk_class": risk_class,
        },
        case_id,
    )
    return casefile


def run(env: dict[str, str]) -> int:
    store = store_from_env(env)
    store.init_schema()
    service = Kagent(store, env)
    serve(service.api, int(env.get("KAGENT_PORT", "8080")))
    return 0  # unreachable: serve() blocks forever
