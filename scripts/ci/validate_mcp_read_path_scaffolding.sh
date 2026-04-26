#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 6 read-only MCP service scaffolding..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import json
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
response_schema = json.loads(
    (root / "contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json").read_text(encoding="utf-8")
)
required_response_fields = set(response_schema.get("required", []))
required_fields = {
    "summary",
    "structured_data",
    "evidence_handles",
    "confidence",
    "time_window",
    "safety_class",
    "next_recommended_tools",
}
if not required_fields.issubset(required_response_fields):
    fail("Tool response schema does not include all required read-path fields.")

expected_gateway_ref = {
    "name": "ai-gateway-catalog",
    "namespace": "ai-gateway",
}


def validate_gateway_and_bounds(contract_path: Path, service: dict) -> None:
    gateway_contract = service.get("gateway_contract", {})
    if gateway_contract.get("endpoint_mode") != "gateway":
        fail(f"{contract_path} must set gateway_contract.endpoint_mode to gateway.")
    remote_ref = gateway_contract.get("remote_mcp_server_ref", {})
    if remote_ref != expected_gateway_ref:
        fail(
            f"{contract_path} must reference ai-gateway-catalog in ai-gateway "
            "for remote MCP endpoint integration."
        )
    if gateway_contract.get("health_path") != "/healthz":
        fail(f"{contract_path} must define gateway health path /healthz.")

    bounds = service.get("execution_bounds", {})
    timeout_ms = bounds.get("timeout_ms")
    if not isinstance(timeout_ms, int) or timeout_ms <= 0:
        fail(f"{contract_path} must define a positive execution timeout_ms.")
    quota = bounds.get("quota", {})
    rpm = quota.get("max_requests_per_minute")
    concurrent = quota.get("max_concurrent_requests")
    if not isinstance(rpm, int) or rpm <= 0:
        fail(f"{contract_path} must define positive max_requests_per_minute.")
    if not isinstance(concurrent, int) or concurrent <= 0:
        fail(f"{contract_path} must define positive max_concurrent_requests.")


service_contracts = [
    root / "services/mcp/incident-search/SERVICE_CONTRACT_V1.yaml",
    root / "services/mcp/graph-analysis/SERVICE_CONTRACT_V1.yaml",
    root / "services/mcp/trace-investigation/SERVICE_CONTRACT_V1.yaml",
    root / "services/mcp/metrics-correlation/SERVICE_CONTRACT_V1.yaml",
    root / "services/mcp/change-intelligence/SERVICE_CONTRACT_V1.yaml",
]
for path in service_contracts:
    if not path.exists():
        fail(f"Missing read-path service contract: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    service = data.get("service", {})
    if service.get("gateway_served") is not True:
        fail(f"{path} must be gateway served.")
    if service.get("mode") != "read-only":
        fail(f"{path} must be read-only mode.")
    if service.get("response_schema") != "contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json":
        fail(f"{path} must reference TOOL_RESPONSE_SCHEMA_V1.")
    validate_gateway_and_bounds(path, service)

casefile_contract_path = (
    root / "services/mcp/incident-casefile/CASEFILE_ACCESS_CONTRACT_V1.yaml"
)
if not casefile_contract_path.exists():
    fail("Missing case-file MCP access contract.")
casefile = yaml.safe_load(casefile_contract_path.read_text(encoding="utf-8"))
svc = casefile.get("service", {})
if svc.get("casefile_schema") != "contracts/ai/CASEFILE_SCHEMA_V1.json":
    fail("Case-file MCP contract must bind to CASEFILE_SCHEMA_V1.")
if svc.get("casefile_lifecycle_contract") != "contracts/ai/CASEFILE_LIFECYCLE_V1.md":
    fail("Case-file MCP contract must bind to CASEFILE_LIFECYCLE_V1.")
if svc.get("resume_contract") != "contracts/ai/REPLAY_RESUME_RULES_V1.yaml":
    fail("Case-file MCP contract must bind to REPLAY_RESUME_RULES_V1.")
validate_gateway_and_bounds(casefile_contract_path, svc)
ops = set(
    svc.get("persistence_contract", {}).get("required_operations", [])
)
if ops != {"casefile.create.v1", "casefile.read.v1", "casefile.update.v1"}:
    fail("Case-file persistence operations are incomplete.")
retrieval = set(
    svc.get("persistence_contract", {}).get("retrieval_guarantees", [])
)
if retrieval != {"by_case_id", "by_correlation_id"}:
    fail("Case-file retrieval guarantees are incomplete.")

casefile_lifecycle = (root / "contracts/ai/CASEFILE_LIFECYCLE_V1.md").read_text(
    encoding="utf-8"
)
for transition in [
    "| `open` | `triaging` |",
    "| `triaging` | `investigating` |",
    "| `awaiting-approval` | `executing` |",
    "| `resolved` | `closed` |",
]:
    if transition not in casefile_lifecycle:
        fail("Case-file lifecycle contract missing required transition row.")

resume_rules = yaml.safe_load(
    (root / "contracts/ai/REPLAY_RESUME_RULES_V1.yaml").read_text(encoding="utf-8")
)
if resume_rules.get("resume_source", {}).get("required") != "casefile_persistent_store":
    fail("Resume contract must require casefile_persistent_store.")
for forbidden in ["transient_agent_memory", "ephemeral_prompt_state"]:
    if forbidden not in set(resume_rules.get("resume_source", {}).get("forbidden", [])):
        fail(f"Resume contract missing forbidden resume source: {forbidden}")

scope_profile_path = root / "services/mcp/common/REDACTION_SCOPE_PROFILE_V1.yaml"
if not scope_profile_path.exists():
    fail("Missing redaction scope profile.")
scope_profile = yaml.safe_load(scope_profile_path.read_text(encoding="utf-8"))
required_scopes = set(scope_profile.get("scope_controls", {}).get("required", []))
if required_scopes != {"namespace", "tenant", "team"}:
    fail("Redaction scope profile must enforce namespace, tenant, and team.")
redaction = scope_profile.get("redaction_controls", {})
if redaction.get("field_level_redaction") is not True:
    fail("Redaction profile must enable field-level redaction.")
if redaction.get("secret_masking") is not True:
    fail("Redaction profile must enable secret masking.")

# timeout and quota behavior checks
for path in service_contracts + [casefile_contract_path]:
    service = yaml.safe_load(path.read_text(encoding="utf-8")).get("service", {})
    bounds = service.get("execution_bounds", {})
    timeout_ms = bounds.get("timeout_ms", 0)
    quota = bounds.get("quota", {})
    rpm = quota.get("max_requests_per_minute", 0)
    concurrent = quota.get("max_concurrent_requests", 0)
    if timeout_ms > 5000:
        fail(f"{path} timeout_ms exceeds baseline limit of 5000ms.")
    if rpm > 300:
        fail(f"{path} max_requests_per_minute exceeds baseline limit of 300.")
    if concurrent > 50:
        fail(f"{path} max_concurrent_requests exceeds baseline limit of 50.")

bundle = json.loads(
    (
        root / "tests/smoke/mcp_read_path_bundle/GATEWAY_READ_RESPONSES_V1.json"
    ).read_text(encoding="utf-8")
)
responses = bundle.get("responses", [])
if len(responses) != 5:
    fail("Read-path smoke bundle must include exactly five service responses.")
for entry in responses:
    response = entry.get("response", {})
    missing = sorted(required_fields - set(response.keys()))
    if missing:
        fail(f"Gateway response fixture missing required fields: {missing}")
    confidence = response.get("confidence", -1)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        fail("Gateway response confidence must be numeric in [0,1].")
    tw = response.get("time_window", {})
    if "start" not in tw or "end" not in tw:
        fail("Gateway response time_window must include start and end.")

workflow = (root / ".github/workflows/ci.yaml").read_text(encoding="utf-8")
batch6 = (root / "scripts/ci/validate_batch6_smoke.sh").read_text(encoding="utf-8")
if "validate_mcp_read_path_scaffolding.sh" not in workflow:
    fail("Main CI workflow must include read-path MCP scaffold gate.")
if "validate_mcp_read_path_scaffolding.sh" not in batch6:
    fail("Batch 6 smoke must include read-path MCP scaffold gate.")

print("Batch 6 read-path scaffold checks passed.")
PY

echo "Running MCP read-path contract suite..."
python3 tests/contracts/mcp/test_mcp_read_path_contracts.py
