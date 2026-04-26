#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 4 MCP catalog and tool contracts..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import json
import re
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
catalog_path = root / "contracts" / "mcp" / "MCP_CATALOG_V1.yaml"
response_schema_path = root / "contracts" / "mcp" / "TOOL_RESPONSE_SCHEMA_V1.json"
tenancy_path = root / "contracts" / "mcp" / "TENANCY_REDACTION_RULES_V1.yaml"
gateway_path = root / "contracts" / "mcp" / "GATEWAY_DISCOVERY_CONTRACT_V1.yaml"
semver_path = root / "contracts" / "mcp" / "SEMVER_COMPATIBILITY_POLICY_V1.yaml"

for required in [
    catalog_path,
    response_schema_path,
    tenancy_path,
    gateway_path,
    semver_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 4 MCP artifact: {required}")

catalog = yaml.safe_load(catalog_path.read_text())
response_schema = json.loads(response_schema_path.read_text())
tenancy = yaml.safe_load(tenancy_path.read_text())
gateway = yaml.safe_load(gateway_path.read_text())
semver = yaml.safe_load(semver_path.read_text())

# 1) Versioned MCP catalog completeness
services = catalog.get("services", [])
expected_services = {
    "incident-search-mcp",
    "graph-analysis-mcp",
    "trace-investigation-mcp",
    "metrics-correlation-mcp",
    "change-intelligence-mcp",
    "runbook-execution-mcp",
    "incident-casefile-mcp",
}
actual_services = {svc.get("service") for svc in services}
if actual_services != expected_services:
    fail("MCP catalog service set is incomplete or mismatched.")

expected_service_tools = {
    "incident-search-mcp": {"incident-search"},
    "graph-analysis-mcp": {"graph-analysis"},
    "trace-investigation-mcp": {"trace-investigation"},
    "metrics-correlation-mcp": {"metrics-correlation"},
    "change-intelligence-mcp": {"change-intelligence"},
    "runbook-execution-mcp": {"runbook-execution"},
    "incident-casefile-mcp": {"incident-casefile"},
}

for svc in services:
    service_name = svc.get("service")
    if not svc.get("owner"):
        fail(f"MCP catalog service missing owner: {service_name}")
    tools = svc.get("tools", [])
    if not tools:
        fail(f"MCP catalog service missing tools: {service_name}")
    bound_tools = {tool.get("name") for tool in tools}
    if bound_tools != expected_service_tools.get(service_name, set()):
        fail(
            f"MCP catalog service tool binding mismatch for {service_name}. "
            f"Expected {sorted(expected_service_tools.get(service_name, set()))}, "
            f"got {sorted(bound_tools)}."
        )
    for tool in tools:
        if tool.get("version") != "v1":
            fail(
                f"MCP tool must use version v1 for this contract set: "
                f"{service_name}::{tool.get('name')}"
            )
        if tool.get("response_schema") != "TOOL_RESPONSE_SCHEMA_V1.json":
            fail("MCP tool response schema binding is not aligned.")
        if tool.get("tenancy_profile") != "TENANCY_REDACTION_RULES_V1.yaml":
            fail("MCP tool tenancy profile binding is not aligned.")

# 2) Common response schema compliance
required_response_fields = {
    "summary",
    "structured_data",
    "evidence_handles",
    "confidence",
    "time_window",
    "safety_class",
    "next_recommended_tools",
}
actual_required_response_fields = set(response_schema.get("required", []))
missing_fields = sorted(required_response_fields - actual_required_response_fields)
if missing_fields:
    fail(f"Response schema missing required fields: {missing_fields}")

# 3) Tenancy and redaction boundaries
required_scopes = set(tenancy.get("scope_enforcement", {}).get("required_scopes", []))
if required_scopes != {"namespace", "tenant", "team"}:
    fail("Tenancy rules must enforce namespace, tenant, and team scopes.")
if tenancy.get("redaction_controls", {}).get("field_level_redaction") is not True:
    fail("Tenancy rules must enforce field-level redaction.")
if tenancy.get("redaction_controls", {}).get("secret_masking") is not True:
    fail("Tenancy rules must enforce secret masking.")
if tenancy.get("scope_enforcement", {}).get("query_bounds", {}).get("max_time_window_hours") != 24:
    fail("Tenancy rules must define max query time window bounds.")

def tenancy_allows(request: dict, rules: dict) -> bool:
    scope = request.get("scope", {})
    required = rules.get("scope_enforcement", {}).get("required_scopes", [])
    for key in required:
        if not scope.get(key):
            return False

    time_window_hours = int(request.get("query", {}).get("time_window_hours", 0))
    max_time = int(
        rules.get("scope_enforcement", {})
        .get("query_bounds", {})
        .get("max_time_window_hours", 0)
    )
    if time_window_hours <= 0 or time_window_hours > max_time:
        return False

    response_items = int(request.get("query", {}).get("response_items", 0))
    max_items = int(
        rules.get("scope_enforcement", {})
        .get("query_bounds", {})
        .get("max_response_items", 0)
    )
    if response_items <= 0 or response_items > max_items:
        return False
    return True


def redact_record(record: dict, rules: dict) -> dict:
    redacted = dict(record)
    for key in ["secret", "api_key", "password", "token"]:
        if key in redacted and rules.get("redaction_controls", {}).get("secret_masking"):
            redacted[key] = "***REDACTED***"

    deny_list = set(
        rules.get("redaction_controls", {}).get("restricted_domain_deny_list", [])
    )
    if redacted.get("domain") in deny_list:
        redacted["blocked"] = True
    return redacted


allow_request = {
    "scope": {"namespace": "team-a", "tenant": "tenant-a", "team": "sre"},
    "query": {"time_window_hours": 4, "response_items": 20},
}
deny_scope_request = {
    "scope": {"namespace": "team-a", "tenant": "tenant-a"},
    "query": {"time_window_hours": 4, "response_items": 20},
}
deny_window_request = {
    "scope": {"namespace": "team-a", "tenant": "tenant-a", "team": "sre"},
    "query": {"time_window_hours": 72, "response_items": 20},
}
deny_size_request = {
    "scope": {"namespace": "team-a", "tenant": "tenant-a", "team": "sre"},
    "query": {"time_window_hours": 4, "response_items": 999},
}

if not tenancy_allows(allow_request, tenancy):
    fail("Tenancy boundary allow-path test failed for valid scoped request.")
if tenancy_allows(deny_scope_request, tenancy):
    fail("Tenancy boundary deny-path failed: request missing team scope passed.")
if tenancy_allows(deny_window_request, tenancy):
    fail("Tenancy boundary deny-path failed: oversized time window passed.")
if tenancy_allows(deny_size_request, tenancy):
    fail("Tenancy boundary deny-path failed: oversized response size passed.")

redacted = redact_record(
    {"domain": "credentials", "secret": "abc", "summary": "x"},
    tenancy,
)
if redacted.get("secret") != "***REDACTED***":
    fail("Redaction boundary test failed: secret masking not applied.")
if redacted.get("blocked") is not True:
    fail("Redaction boundary test failed: restricted domain record not blocked.")

# 4) Gateway registration and discovery constraints
if (
    gateway.get("discovery_constraints", {})
    .get("direct_discovery_disabled_for_backend_mcpserver")
    is not True
):
    fail("Gateway contract must disable direct backend MCP discovery.")
if gateway.get("discovery_constraints", {}).get("remote_mcpserver_reference_required") is not True:
    fail("Gateway contract must require RemoteMCPServer references.")

# 5) Semantic versioning policy checks
if semver.get("versioning_rules", {}).get("breaking_change_requires_new_major") is not True:
    fail("Semver policy must require a new major on breaking changes.")
pattern = semver.get("versioning_rules", {}).get("tool_name_suffix_pattern", "")
if not pattern.startswith(".v"):
    fail("Semver policy must define versioned tool suffix pattern.")
if semver.get("compatibility_checks", {}).get("fail_on_unversioned_tool_name") is not True:
    fail("Semver policy must fail on unversioned tool names.")

for svc in services:
    for tool in svc.get("tools", []):
        tool_name = tool.get("name", "")
        version = tool.get("version", "")
        if not re.match(r"^v[0-9]+$", version):
            fail(f"Invalid tool version format for {tool_name}: {version}")

# 6) CI MCP contract gating
batch4_smoke = (root / "scripts" / "ci" / "validate_batch4_smoke.sh").read_text()
workflow = (root / ".github" / "workflows" / "ci.yaml").read_text()
if "validate_mcp_contracts.sh" not in batch4_smoke:
    fail("Batch 4 smoke bundle must run MCP contract validator.")
if "validate_mcp_contracts.sh" not in workflow:
    fail("Main CI workflow must include MCP contract validator.")

print("Batch 4 MCP catalog and tool contract checks passed.")
PY
