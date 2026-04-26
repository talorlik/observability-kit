#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    service_contract_paths = [
        Path("services/mcp/incident-search/SERVICE_CONTRACT_V1.yaml"),
        Path("services/mcp/graph-analysis/SERVICE_CONTRACT_V1.yaml"),
        Path("services/mcp/trace-investigation/SERVICE_CONTRACT_V1.yaml"),
        Path("services/mcp/metrics-correlation/SERVICE_CONTRACT_V1.yaml"),
        Path("services/mcp/change-intelligence/SERVICE_CONTRACT_V1.yaml"),
    ]

    for path in service_contract_paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        service = data.get("service", {})
        if service.get("mode") != "read-only":
            fail(f"{path} must be read-only mode.")
        if service.get("gateway_served") is not True:
            fail(f"{path} must be gateway served.")
        if service.get("response_schema") != "contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json":
            fail(f"{path} must bind TOOL_RESPONSE_SCHEMA_V1.")
        gateway = service.get("gateway_contract", {})
        remote_ref = gateway.get("remote_mcp_server_ref", {})
        if gateway.get("endpoint_mode") != "gateway":
            fail(f"{path} must set gateway endpoint mode.")
        if remote_ref != {"name": "ai-gateway-catalog", "namespace": "ai-gateway"}:
            fail(f"{path} must use ai-gateway-catalog remote ref.")
        if gateway.get("health_path") != "/healthz":
            fail(f"{path} must define /healthz gateway path.")

        bounds = service.get("execution_bounds", {})
        timeout_ms = bounds.get("timeout_ms", 0)
        quota = bounds.get("quota", {})
        if not isinstance(timeout_ms, int) or timeout_ms <= 0 or timeout_ms > 5000:
            fail(f"{path} must define timeout_ms within baseline range.")
        if (
            not isinstance(quota.get("max_requests_per_minute"), int)
            or quota["max_requests_per_minute"] <= 0
            or quota["max_requests_per_minute"] > 300
        ):
            fail(f"{path} must define bounded max_requests_per_minute.")
        if (
            not isinstance(quota.get("max_concurrent_requests"), int)
            or quota["max_concurrent_requests"] <= 0
            or quota["max_concurrent_requests"] > 50
        ):
            fail(f"{path} must define bounded max_concurrent_requests.")

    casefile = yaml.safe_load(
        Path("services/mcp/incident-casefile/CASEFILE_ACCESS_CONTRACT_V1.yaml").read_text(
            encoding="utf-8"
        )
    )
    required_ops = {"casefile.create.v1", "casefile.read.v1", "casefile.update.v1"}
    actual_ops = set(
        casefile.get("service", {})
        .get("persistence_contract", {})
        .get("required_operations", [])
    )
    if actual_ops != required_ops:
        fail("Case-file contract required operations are incomplete.")
    case_service = casefile.get("service", {})
    if case_service.get("casefile_lifecycle_contract") != "contracts/ai/CASEFILE_LIFECYCLE_V1.md":
        fail("Case-file lifecycle contract binding missing.")
    if case_service.get("resume_contract") != "contracts/ai/REPLAY_RESUME_RULES_V1.yaml":
        fail("Case-file resume contract binding missing.")

    lifecycle_doc = Path("contracts/ai/CASEFILE_LIFECYCLE_V1.md").read_text(encoding="utf-8")
    for required_transition in [
        "| `open` | `triaging` |",
        "| `triaging` | `investigating` |",
        "| `awaiting-approval` | `executing` |",
        "| `resolved` | `closed` |",
    ]:
        if required_transition not in lifecycle_doc:
            fail("Case-file lifecycle transitions are incomplete.")

    resume_rules = yaml.safe_load(
        Path("contracts/ai/REPLAY_RESUME_RULES_V1.yaml").read_text(encoding="utf-8")
    )
    if resume_rules.get("resume_source", {}).get("required") != "casefile_persistent_store":
        fail("Resume contract required source mismatch.")
    forbidden_sources = set(resume_rules.get("resume_source", {}).get("forbidden", []))
    for forbidden in ["transient_agent_memory", "ephemeral_prompt_state"]:
        if forbidden not in forbidden_sources:
            fail(f"Resume contract missing forbidden source: {forbidden}")

    responses = json.loads(
        Path(
            "tests/smoke/mcp_read_path_bundle/GATEWAY_READ_RESPONSES_V1.json"
        ).read_text(encoding="utf-8")
    )["responses"]
    if len(responses) != 5:
        fail("Gateway read response bundle must include five read-path services.")

    print("MCP read-path contract suite passed.")


if __name__ == "__main__":
    main()
