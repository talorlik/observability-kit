"""MCP gateway: explicit catalog registration, heartbeat health,
policy-gated routing, envelope validation, redaction, and a full audit
journal per invocation.

Failover posture is the contract's: deny. No retries, unhealthy
services deny, timeouts deny, invalid upstream envelopes deny.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Any

from airuntime import contracts, policy
from airuntime.httpd import JsonApi, http_json, serve
from airuntime.store import utc_now

_TOOL_VERSION_RE = re.compile(r"^v\d+$")


def contract_fingerprint() -> str:
    """Stable digest of the embedded routing-relevant constants, so
    evidence can prove which contract snapshot the gateway enforced."""
    material = json.dumps(
        {
            "catalog": contracts.MCP_CATALOG,
            "risk": contracts.TOOL_RISK_CLASSES,
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _truncate_lists(node: Any) -> tuple[Any, int]:
    """Cap every list inside structured_data at MAX_RESPONSE_ITEMS.

    Returns (bounded_copy, number_of_lists_truncated). Truncation is a
    contract query bound, not an error - the metadata records it.
    """
    truncated = 0
    if isinstance(node, dict):
        result: dict[str, Any] = {}
        for key, value in node.items():
            child, child_truncated = _truncate_lists(value)
            truncated += child_truncated
            result[key] = child
        return result, truncated
    if isinstance(node, list):
        if len(node) > contracts.MAX_RESPONSE_ITEMS:
            node = node[: contracts.MAX_RESPONSE_ITEMS]
            truncated += 1
        children = []
        for item in node:
            child, child_truncated = _truncate_lists(item)
            truncated += child_truncated
            children.append(child)
        return children, truncated
    return node, truncated


class Gateway:
    """Holds registry + journal state and owns the JsonApi routes."""

    def __init__(self, env: dict[str, str]) -> None:
        self.toolhost_template = env.get(
            "TOOLHOST_URL_TEMPLATE",
            "http://{service}.mcp-services.svc.cluster.local:443/invoke",
        )
        self.heartbeat_template = env.get(
            "HEARTBEAT_URL_TEMPLATE",
            "http://{service}.mcp-services.svc.cluster.local:443/healthz",
        )
        self.heartbeat_disabled = bool(env.get("HEARTBEAT_DISABLED", ""))
        # Explicit registration of every catalog service at startup
        # (registration_mode: explicit in the discovery contract).
        self.registry: dict[str, dict[str, Any]] = {
            service: {
                "service_name": service,
                "tool": spec["tool"],
                "gateway_endpoint": self.toolhost_template.format(
                    service=service
                ),
                "catalog_visibility": "internal",
                "tenancy_profile": "scoped",
                "tool_response_schema": "TOOL_RESPONSE_SCHEMA_V1",
                "registration_mode": "explicit",
                "healthy": True,
                "missed_heartbeats": 0,
                "registered": True,
            }
            for service, spec in contracts.MCP_CATALOG.items()
        }
        self.journal: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self.api = JsonApi("gateway")
        self.api.route("GET", "/catalog", self._handle_catalog)
        self.api.route("POST", "/invoke", self._handle_invoke)
        self.api.route("GET", "/journal", self._handle_journal)

    # -- audit ---------------------------------------------------------

    def _audit(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.journal.append(event)
        # JSON line on stdout: pod logs are the live-evidence channel.
        print(json.dumps({"gateway_audit": event}, sort_keys=True))

    # -- routes --------------------------------------------------------

    def _handle_catalog(
        self, _subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        services = [
            {
                "service": entry["service_name"],
                "tool": entry["tool"],
                "healthy": entry["healthy"],
                "missed_heartbeats": entry["missed_heartbeats"],
                "registered": entry["registered"],
            }
            for entry in self.registry.values()
        ]
        return 200, {
            "services": services,
            "contract_fingerprint": contract_fingerprint(),
        }

    def _handle_journal(
        self, _subpath: str, _body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        with self._lock:
            return 200, {"events": list(self.journal)}

    def _deny(
        self,
        status: int,
        reason: str,
        body: dict[str, Any],
        tool_id: str,
        outcome: str,
        policy_decision: str = "deny",
        started: float | None = None,
        extra: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        latency_ms = int((time.monotonic() - started) * 1000) if started else 0
        redacted_params, _meta = policy.redact(body.get("input", {}))
        self._audit(
            policy.build_audit_event(
                invoker_identity=body.get("caller_agent", "unknown"),
                agent_identity=body.get("caller_agent", "unknown"),
                tool_call=tool_id,
                tool_parameters_redacted=redacted_params,
                policy_decision=policy_decision,
                approval_decision="not-required",
                final_action_outcome=outcome,
                latency_ms=latency_ms,
                event_time=utc_now(),
            )
        )
        payload = {"decision": "deny", "reason": reason}
        if extra:
            payload.update(extra)
        return status, payload

    def _handle_invoke(
        self, _subpath: str, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        started = time.monotonic()
        missing = [
            f for f in contracts.AGENT_TO_MCP_FIELDS if f not in body
        ]
        if missing:
            return 400, {
                "decision": "deny",
                "reason": f"agent_to_mcp envelope missing fields: {missing}",
            }
        tool = body["tool"]
        tool_version = body["tool_version"]
        if not _TOOL_VERSION_RE.match(str(tool_version)):
            return 400, {
                "decision": "deny",
                "reason": f"tool_version {tool_version!r} must match v<digits>",
            }
        tool_id = f"{tool}.{tool_version}"

        tenant_scope = body.get("tenant_scope") or {}
        missing_scopes = [
            s for s in contracts.REQUIRED_SCOPES if not tenant_scope.get(s)
        ]
        if missing_scopes:
            # deny_on_scope_mismatch: an incomplete scope is a mismatch.
            return self._deny(
                403,
                f"tenant_scope missing required scopes: {missing_scopes}",
                body,
                tool_id,
                "blocked",
                started=started,
            )

        service_name = contracts.TOOL_TO_SERVICE.get(tool)
        if service_name is None:
            return self._deny(
                403,
                f"unknown tool {tool!r}: not in gateway catalog",
                body,
                tool_id,
                "blocked",
                started=started,
            )
        risk_class = policy.classify_tool(tool_id)
        if risk_class is None:
            # UNCLASSIFIED_TOOL_BEHAVIOR = deny
            return self._deny(
                403,
                f"tool {tool_id} is unclassified: default deny",
                body,
                tool_id,
                "blocked",
                started=started,
            )

        # TOOL_BINDINGS_V1: the caller must be explicitly bound to the
        # tool and its class must not deny the risk class
        # (default_tool_policy: deny).
        allowed, binding_reason = policy.check_agent_binding(
            body["caller_agent"], tool_id, risk_class
        )
        if not allowed:
            return self._deny(
                403,
                binding_reason,
                body,
                tool_id,
                "blocked",
                started=started,
            )

        # Redaction query bound: a request window wider than the
        # contract maximum is denied outright, not clipped.
        window = (body.get("input") or {}).get("window") or {}
        if window.get("start") and window.get("end"):
            try:
                span = datetime.fromisoformat(
                    window["end"]
                ) - datetime.fromisoformat(window["start"])
            except ValueError as exc:
                return self._deny(
                    400,
                    f"unparseable time window: {exc}",
                    body,
                    tool_id,
                    "blocked",
                    started=started,
                )
            if span > timedelta(hours=contracts.MAX_TIME_WINDOW_HOURS):
                return self._deny(
                    403,
                    f"time window {span} exceeds max "
                    f"{contracts.MAX_TIME_WINDOW_HOURS}h",
                    body,
                    tool_id,
                    "blocked",
                    started=started,
                )

        approval_decision = "not-required"
        # Write-path tools are exactly the tools with action
        # preconditions; every one of them must arrive with an
        # approval_context (even not-required updates carry the policy
        # decision and target validity).
        if tool_id in contracts.ACTION_PRECONDITIONS:
            approval_context = body.get("approval_context")
            if approval_context is None:
                return self._deny(
                    403,
                    f"write-path tool {tool_id} requires approval_context",
                    body,
                    tool_id,
                    "blocked",
                    started=started,
                )
            ok, blocked_reasons = policy.check_action_preconditions(
                tool_id,
                {
                    "policy_decision": approval_context.get(
                        "policy_decision"
                    ),
                    "approval": approval_context.get("approval"),
                    "rollback_plan_present": approval_context.get(
                        "rollback_plan_present", False
                    ),
                    "change_ticket_present": approval_context.get(
                        "change_ticket_present",
                        bool(
                            (approval_context.get("approval") or {}).get(
                                "change_ticket"
                            )
                        ),
                    ),
                    "valid_target": approval_context.get(
                        "valid_target", False
                    ),
                },
            )
            if not ok:
                return self._deny(
                    403,
                    "action preconditions failed",
                    body,
                    tool_id,
                    "blocked",
                    started=started,
                    extra={"blocked_reasons": blocked_reasons},
                )
            approval = approval_context.get("approval")
            if approval and approval.get("state") == "approved":
                approval_decision = "approved"

        entry = self.registry[service_name]
        if not entry["healthy"] or not entry["registered"]:
            # fallback_mode: deny - no rerouting to another service.
            return self._deny(
                503,
                f"service {service_name} is unhealthy: failover denies",
                body,
                tool_id,
                "failed",
                started=started,
            )

        timeout_ms = min(
            int(body.get("timeout_ms", contracts.DEFAULT_REQUEST_TIMEOUT_MS)),
            contracts.UPPER_BOUND_REQUEST_TIMEOUT_MS,
        )
        try:
            status, payload = http_json(
                "POST",
                entry["gateway_endpoint"],
                body,
                timeout=timeout_ms / 1000.0,
            )
        except Exception as exc:
            # Any transport failure maps to the timeout posture:
            # deny, zero retries (retry_attempts: 0).
            return self._deny(
                504,
                f"tool call failed ({exc}); on_timeout=deny, no retries",
                body,
                tool_id,
                "failed",
                started=started,
            )
        if status != 200:
            return self._deny(
                502,
                f"tool service returned {status}",
                body,
                tool_id,
                "failed",
                started=started,
            )
        violations = policy.validate_tool_response(payload)
        if violations:
            return self._deny(
                502,
                "tool response violates TOOL_RESPONSE_SCHEMA_V1",
                body,
                tool_id,
                "failed",
                started=started,
                extra={"violations": violations},
            )

        redacted_data, redaction_metadata = policy.redact(
            payload["structured_data"]
        )
        redacted_data, truncated_lists = _truncate_lists(redacted_data)
        # MAX_RESPONSE_ITEMS is a redaction query bound: record any
        # truncation so consumers know the payload is partial.
        redaction_metadata["max_response_items"] = (
            contracts.MAX_RESPONSE_ITEMS
        )
        redaction_metadata["truncated_lists"] = truncated_lists
        response = dict(payload)
        response["structured_data"] = redacted_data
        response["redaction_metadata"] = redaction_metadata

        latency_ms = int((time.monotonic() - started) * 1000)
        redacted_params, _meta = policy.redact(body.get("input", {}))
        self._audit(
            policy.build_audit_event(
                invoker_identity=body["caller_agent"],
                agent_identity=body["caller_agent"],
                tool_call=tool_id,
                tool_parameters_redacted=redacted_params,
                policy_decision="allow",
                approval_decision=approval_decision,
                final_action_outcome="executed",
                latency_ms=latency_ms,
                event_time=utc_now(),
                evidence_handles=list(payload.get("evidence_handles", [])),
                target_resources=[
                    f"{tenant_scope['namespace']}/"
                    f"{body.get('input', {}).get('object_name', '*')}"
                ],
            )
        )
        return 200, response

    # -- heartbeat -----------------------------------------------------

    def heartbeat_once(self) -> None:
        for service, entry in self.registry.items():
            url = self.heartbeat_template.format(service=service)
            try:
                status, _payload = http_json("GET", url, timeout=5.0)
                healthy_now = status == 200
            except Exception:
                healthy_now = False
            if healthy_now:
                if not entry["registered"]:
                    # Recovery re-registers the service.
                    self._audit_heartbeat(service, "re-registered")
                entry["missed_heartbeats"] = 0
                entry["healthy"] = True
                entry["registered"] = True
                continue
            entry["missed_heartbeats"] += 1
            if (
                entry["missed_heartbeats"]
                >= contracts.UNHEALTHY_THRESHOLD_MISSED_HEARTBEATS
                and entry["healthy"]
            ):
                entry["healthy"] = False
                entry["registered"] = False
                self._audit_heartbeat(service, "marked-unhealthy")

    def _audit_heartbeat(self, service: str, action: str) -> None:
        self._audit(
            policy.build_audit_event(
                invoker_identity="gateway-heartbeat",
                agent_identity="gateway-heartbeat",
                tool_call=f"heartbeat:{service}",
                tool_parameters_redacted={},
                policy_decision="allow",
                approval_decision="not-required",
                final_action_outcome=(
                    "failed" if action == "marked-unhealthy" else "executed"
                ),
                latency_ms=0,
                event_time=utc_now(),
                target_resources=[service],
            )
        )

    def _heartbeat_loop(self) -> None:
        while True:
            time.sleep(contracts.HEARTBEAT_INTERVAL_SECONDS)
            self.heartbeat_once()


def run(env: dict[str, str]) -> int:
    gateway = Gateway(env)
    if not gateway.heartbeat_disabled:
        threading.Thread(
            target=gateway._heartbeat_loop, daemon=True
        ).start()
    serve(gateway.api, int(env.get("GATEWAY_PORT", "8082")))
    return 0  # unreachable: serve() blocks forever
