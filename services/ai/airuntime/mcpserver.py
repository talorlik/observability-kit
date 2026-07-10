"""MCP tool host: one process serves one catalog tool.

Every response is a deterministic, contract-shaped McpToolResponseV1
envelope. The structured_data is a declared sample journal (the real
read-path data tier attaches in Batch 25); it is honest about that via
an explicit source marker, so evidence readers cannot mistake rehearsal
findings for live telemetry.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from airuntime.contracts import MCP_CATALOG, TOOL_RISK_CLASSES
from airuntime.httpd import JsonApi, serve

TOOL_NAMES: tuple[str, ...] = tuple(
    spec["tool"] for spec in MCP_CATALOG.values()
)

# Sample-journal provenance marker attached to every structured payload.
_SAMPLE_SOURCE = {
    "source": "declared-sample-journal",
    "note": "read-path data tier ships with Batch 25 attach path",
}

_NEXT_TOOLS: dict[str, list[str]] = {
    "incident-search": ["trace-investigation", "metrics-correlation"],
    "graph-analysis": ["change-intelligence", "incident-search"],
    "trace-investigation": ["graph-analysis", "metrics-correlation"],
    "metrics-correlation": ["trace-investigation", "graph-analysis"],
    "change-intelligence": ["incident-search", "graph-analysis"],
    "incident-casefile": ["runbook-execution"],
    "runbook-execution": ["incident-casefile"],
}


def _scope(request: dict[str, Any]) -> dict[str, Any]:
    tenant_scope = request.get("tenant_scope") or {}
    return {
        "namespace": tenant_scope.get("namespace"),
        "tenant": tenant_scope.get("tenant"),
        "team": tenant_scope.get("team"),
    }


def _time_window(request: dict[str, Any]) -> dict[str, str]:
    window = (request.get("input") or {}).get("window") or {}
    if window.get("start") and window.get("end"):
        return {"start": window["start"], "end": window["end"]}
    end = datetime.now(timezone.utc)
    return {
        "start": (end - timedelta(hours=1)).isoformat(),
        "end": end.isoformat(),
    }


def _evidence_handle(tool: str, request_input: dict[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(request_input, sort_keys=True).encode()
    ).hexdigest()[:12]
    return f"evidence://{tool}/{digest}"


def _findings(tool: str, request: dict[str, Any]) -> dict[str, Any]:
    """Tool-specific deterministic sample findings."""
    scope = _scope(request)
    request_input = request.get("input") or {}
    obj = request_input.get("object_name", "unknown-object")
    items_by_tool: dict[str, tuple[str, list[dict[str, Any]]]] = {
        "incident-search": (
            "matched_incidents",
            [
                {"incident_id": f"inc-{obj}-001", "similarity": 0.91, **scope},
                {"incident_id": f"inc-{obj}-002", "similarity": 0.84, **scope},
            ],
        ),
        "graph-analysis": (
            "impacted_services",
            [
                {"service": f"{obj}-upstream", "impact": "degraded", **scope},
                {"service": f"{obj}-downstream", "impact": "at-risk", **scope},
            ],
        ),
        "trace-investigation": (
            "slow_spans",
            [
                {"span": f"{obj}/handler", "p99_ms": 2140, **scope},
                {"span": f"{obj}/db-query", "p99_ms": 1730, **scope},
            ],
        ),
        "metrics-correlation": (
            "correlated_metrics",
            [
                {"metric": "container_memory_working_set_bytes",
                 "correlation": 0.93, **scope},
                {"metric": "kube_pod_container_status_restarts_total",
                 "correlation": 0.88, **scope},
            ],
        ),
        "change-intelligence": (
            "recent_changes",
            [
                {"change": f"deploy/{obj}", "age_minutes": 22, **scope},
                {"change": f"configmap/{obj}-config", "age_minutes": 47,
                 **scope},
            ],
        ),
    }
    key, items = items_by_tool[tool]
    return {key: items}


def handle_invoke(tool: str, request: dict[str, Any]) -> dict[str, Any]:
    """Pure envelope builder; the HTTP route is a thin wrapper."""
    if tool not in TOOL_NAMES:
        raise ValueError(f"unknown tool {tool!r}")
    request_input = request.get("input") or {}
    scope = _scope(request)
    obj = request_input.get("object_name", "unknown-object")
    namespace = scope.get("namespace") or "unknown-namespace"

    envelope: dict[str, Any] = {
        "schema_version": "v1",
        "evidence_handles": [_evidence_handle(tool, request_input)],
        "confidence": 0.75,
        "time_window": _time_window(request),
        "next_recommended_tools": list(_NEXT_TOOLS[tool]),
    }

    if tool == "incident-casefile":
        op = request_input.get("op")
        if op == "read":
            envelope["summary"] = (
                f"incident-casefile: read casefile for {obj} in {namespace}"
            )
            envelope["structured_data"] = {
                "casefile": request_input.get("casefile"),
                **_SAMPLE_SOURCE,
            }
            envelope["safety_class"] = TOOL_RISK_CLASSES[
                "incident-casefile.read.v1"
            ]
        elif op == "update":
            update = request_input.get("update")
            if not isinstance(update, dict) or not update:
                raise ValueError(
                    "incident-casefile update requires a non-empty "
                    "input.update payload"
                )
            envelope["summary"] = (
                f"incident-casefile: applied update for {obj} in {namespace}"
            )
            envelope["structured_data"] = {
                "acknowledged": True,
                "updated_fields": sorted(update),
                **_SAMPLE_SOURCE,
            }
            envelope["safety_class"] = TOOL_RISK_CLASSES[
                "incident-casefile.update.v1"
            ]
        else:
            raise ValueError(
                f"incident-casefile op must be read|update, got {op!r}"
            )
    elif tool == "runbook-execution":
        approval = request_input.get("approval") or {}
        rollback_plan = request_input.get("rollback_plan")
        # This service hosts two classified tools (runbook-plan.v1 is
        # write.high-risk, remediation-execute.v1 is write.critical);
        # the safety class must come from the tool the REQUEST names.
        requested_tool_id = f"{request['tool']}.{request['tool_version']}"
        envelope["safety_class"] = TOOL_RISK_CLASSES[requested_tool_id]
        if approval.get("state") == "approved" and rollback_plan:
            if request_input.get("simulate_runtime_failure"):
                # Deterministic rollback: a runtime failure during an
                # approved execution replays the attached rollback
                # plan and reports rolled-back (the action-gate
                # scenario critical-rollback-deterministic).
                envelope["summary"] = (
                    f"runbook-execution: runtime failure for {obj}, "
                    f"rollback plan executed"
                )
                envelope["confidence"] = 1.0
                envelope["structured_data"] = {
                    "outcome": "rolled-back",
                    "rollback_steps": list(
                        rollback_plan.get("steps", [])
                    ) if isinstance(rollback_plan, dict) else [],
                    **_SAMPLE_SOURCE,
                }
            else:
                envelope["summary"] = (
                    f"runbook-execution: executed plan for {obj} "
                    f"in {namespace}"
                )
                envelope["structured_data"] = {
                    "outcome": "executed",
                    "plan_steps": [
                        f"scale {obj} to safe replica count",
                        f"restart {obj} with rollout watch",
                        f"verify {obj} readiness and error budget",
                    ],
                    **_SAMPLE_SOURCE,
                }
        else:
            # A blocked execution is still a valid envelope: the block
            # is a definitive finding, hence confidence 1.0.
            envelope["summary"] = (
                f"runbook-execution: blocked plan for {obj} in {namespace}"
            )
            envelope["confidence"] = 1.0
            envelope["structured_data"] = {
                "outcome": "blocked",
                "reason": (
                    "approval missing or not approved"
                    if approval.get("state") != "approved"
                    else "rollback plan missing"
                ),
                **_SAMPLE_SOURCE,
            }
    else:
        envelope["summary"] = (
            f"{tool}: findings for {obj} in {namespace}"
        )
        envelope["structured_data"] = {
            **_findings(tool, request),
            **_SAMPLE_SOURCE,
        }
        envelope["safety_class"] = TOOL_RISK_CLASSES[f"{tool}.v1"]

    # Deliberate masked-content demo: every tool response carries one
    # secret-shaped field so the gateway's redaction provably masks it
    # in committed evidence (the gateway never returns this raw).
    envelope["structured_data"]["credentials_probe"] = {
        "api_key": "sample-key-material"
    }
    return envelope


def run(env: dict[str, str]) -> int:
    tool = env["TOOL"]  # required: fail loudly when absent
    if tool not in TOOL_NAMES:
        raise ValueError(
            f"TOOL={tool!r} is not a catalog tool; expected one of "
            f"{sorted(TOOL_NAMES)}"
        )
    api = JsonApi(f"mcpserver-{tool}")

    def invoke(
        _subpath: str, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        return 200, handle_invoke(tool, body)

    api.route("POST", "/invoke", invoke)
    serve(api, int(env.get("MCP_PORT", "8443")))
    return 0  # unreachable: serve() blocks forever
