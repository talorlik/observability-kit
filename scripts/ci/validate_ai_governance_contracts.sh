#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 2 security and governance contracts..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import json
import sys
from datetime import datetime, timezone

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
identity_path = root / "contracts" / "policy" / "IDENTITY_ACCESS_MATRIX_V1.yaml"
risk_path = root / "contracts" / "policy" / "TOOL_RISK_CLASSIFICATION_V1.yaml"
approval_path = root / "contracts" / "policy" / "APPROVAL_FLOW_V1.yaml"
decision_schema_path = (
    root / "contracts" / "policy" / "POLICY_DECISION_SCHEMA_V1.json"
)
audit_schema_path = root / "contracts" / "policy" / "AUDIT_EVENT_SCHEMA_V1.json"

for required in [
    identity_path,
    risk_path,
    approval_path,
    decision_schema_path,
    audit_schema_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 2 governance artifact: {required}")

identity = yaml.safe_load(identity_path.read_text())
risk = yaml.safe_load(risk_path.read_text())
approval = yaml.safe_load(approval_path.read_text())
decision_schema = json.loads(decision_schema_path.read_text())
audit_schema = json.loads(audit_schema_path.read_text())

# 1) Identity matrix coverage
agent_rows = identity.get("service_accounts", {}).get("agents", [])
mcp_rows = identity.get("service_accounts", {}).get("mcp_services", [])
if len(agent_rows) < 4:
    fail("Identity matrix must include coverage for core agent classes.")
if len(mcp_rows) < 3:
    fail("Identity matrix must include coverage for core MCP services.")

for row in agent_rows + mcp_rows:
    for field in ["component", "namespace", "serviceAccount", "allowedNamespaces"]:
        if field not in row:
            fail(
                f"Identity matrix row for {row.get('component', '<unknown>')} "
                f"is missing field: {field}"
            )
    if not row["allowedNamespaces"]:
        fail(f"Identity matrix row has empty allowedNamespaces: {row['component']}")

if identity.get("enforcement", {}).get("requires_network_policy") is not True:
    fail("Identity matrix must enforce NetworkPolicy requirement.")

# 2) Tool risk classification mapping
valid_classes = {
    "read.safe",
    "read.sensitive",
    "write.low-risk",
    "write.high-risk",
    "write.critical",
}
declared_classes = set(risk.get("risk_classes", []))
if declared_classes != valid_classes:
    fail("Tool risk classification must declare all required risk classes.")

tool_mappings = risk.get("tool_mappings", [])
if len(tool_mappings) < 9:
    fail("Tool risk classification must include complete tool mapping coverage.")

mapped_tools = set()
for entry in tool_mappings:
    tool = entry.get("tool", "")
    if not tool:
        fail("Tool mapping entry is missing tool identifier.")
    if tool in mapped_tools:
        fail(f"Duplicate tool mapping found: {tool}")
    mapped_tools.add(tool)
    risk_class = entry.get("risk_class")
    if risk_class not in valid_classes:
        fail(f"Tool {tool} has invalid risk class: {risk_class}")
    if risk_class in {"write.high-risk", "write.critical"} and (
        entry.get("requires_approval") is not True
    ):
        fail(f"Tool {tool} must require approval for risk class {risk_class}")

expected_tools = {
    "incident-search.v1",
    "graph-analysis.v1",
    "trace-investigation.v1",
    "metrics-correlation.v1",
    "change-intelligence.v1",
    "incident-casefile.read.v1",
    "incident-casefile.update.v1",
    "runbook-plan.v1",
    "remediation-execute.v1",
}
if mapped_tools != expected_tools:
    missing_tools = sorted(expected_tools - mapped_tools)
    unexpected_tools = sorted(mapped_tools - expected_tools)
    fail(
        "Tool risk classification coverage mismatch. "
        f"Missing: {missing_tools}; Unexpected: {unexpected_tools}"
    )

# 3) Approval policy preconditions
preconditions = approval.get("preconditions", {})
for key in ["write.low-risk", "write.high-risk", "write.critical"]:
    if key not in preconditions:
        fail(f"Approval flow missing precondition set for {key}")

if preconditions["write.high-risk"].get("requires_human_approval") is not True:
    fail("write.high-risk must require human approval.")
if preconditions["write.critical"].get("requires_manual_workflow") is not True:
    fail("write.critical must require manual workflow.")
if approval.get("execution_gates", {}).get("evaluate_policy_before_write") is not True:
    fail("Approval flow must require policy evaluation before write.")

# 4) Policy decision schema behavior
decision_required = set(decision_schema.get("required", []))
for field in [
    "schema_version",
    "decision",
    "tool",
    "risk_class",
    "reason",
    "evaluated_at",
    "requires_approval",
]:
    if field not in decision_required:
        fail(f"Policy decision schema missing required field: {field}")
decision_enum = (
    decision_schema.get("properties", {}).get("decision", {}).get("enum", [])
)
if set(decision_enum) != {"allow", "deny", "conditional"}:
    fail("Policy decision schema decision enum must be allow/deny/conditional.")

# 5) Audit field contract coverage
audit_required = set(audit_schema.get("required", []))
expected_audit_fields = {
    "invoker_identity",
    "agent_identity",
    "agent_version",
    "tool_call",
    "tool_parameters_redacted",
    "evidence_handles",
    "policy_decision",
    "approval_decision",
    "target_resources",
    "final_action_outcome",
    "latency_ms",
    "cost",
}
missing = sorted(expected_audit_fields - audit_required)
if missing:
    fail(f"Audit schema missing required governance fields: {missing}")

# 6) Identity allow/deny behavior checks
service_accounts = {}
for row in agent_rows + mcp_rows:
    service_accounts[row["serviceAccount"]] = {
        "namespace": row["namespace"],
        "allowedNamespaces": set(row["allowedNamespaces"]),
    }


def identity_allows(service_account: str, target_namespace: str) -> bool:
    details = service_accounts.get(service_account)
    if not details:
        return False
    # Deny-by-default if target is not explicitly allow-listed.
    return target_namespace in details["allowedNamespaces"]


if not identity_allows("sa-agent-ceo", "ai-gateway"):
    fail("Identity allow-test failed: sa-agent-ceo should access ai-gateway.")
if identity_allows("sa-agent-ceo", "mcp-services"):
    fail("Identity deny-test failed: sa-agent-ceo must not access mcp-services directly.")
if not identity_allows("sa-mcp-runbook-execution", "ai-policy"):
    fail("Identity allow-test failed: runbook execution MCP should access ai-policy.")
if identity_allows("sa-mcp-incident-search", "ai-policy"):
    fail("Identity deny-test failed: incident search MCP must not access ai-policy.")

# 7) Approval and audit contract path tests
required_approval_fields = set(
    preconditions["write.high-risk"].get("required_approval_fields", [])
)
high_risk_approval_payload = {
    "approval_id": "apr-001",
    "approver": "oncall-sre",
    "decision": "approved",
    "decided_at": datetime.now(timezone.utc).isoformat(),
}
if not required_approval_fields.issubset(high_risk_approval_payload.keys()):
    fail("Approval allow-path test failed: high-risk approval payload missing fields.")

denied_approval_payload = {
    "approval_id": "apr-002",
    "approver": "oncall-sre",
    "decision": "approved",
}
if required_approval_fields.issubset(denied_approval_payload.keys()):
    fail("Approval deny-path test failed: incomplete payload unexpectedly passed.")

audit_allow_event = {
    "schema_version": "v1",
    "invoker_identity": "user:sre@example.com",
    "agent_identity": "remediation-executor",
    "agent_version": "v1",
    "tool_call": "runbook-plan.v1",
    "tool_parameters_redacted": True,
    "evidence_handles": ["ev://case/INC-1001"],
    "policy_decision": "allow",
    "approval_decision": "approved",
    "target_resources": ["k8s://ns/prod/deploy/checkout"],
    "final_action_outcome": "executed",
    "latency_ms": 321,
    "cost": {"tokens": 1200, "estimated_usd": 0.03},
    "event_time": datetime.now(timezone.utc).isoformat(),
}
if not set(audit_schema.get("required", [])).issubset(audit_allow_event.keys()):
    fail("Audit allow-path test failed: required fields missing from audit event.")

audit_deny_event = dict(audit_allow_event)
del audit_deny_event["policy_decision"]
if set(audit_schema.get("required", [])).issubset(audit_deny_event.keys()):
    fail("Audit deny-path test failed: invalid event unexpectedly passed.")

# 8) CI governance gate enforcement
batch2_smoke = (root / "scripts" / "ci" / "validate_batch2_smoke.sh").read_text()
workflow = (root / ".github" / "workflows" / "ci.yaml").read_text()
if "validate_ai_governance_contracts.sh" not in batch2_smoke:
    fail("Batch 2 smoke bundle must run governance contract validator.")
if "validate_ai_governance_contracts.sh" not in workflow:
    fail("Main CI workflow must include governance contract validator.")

print("Batch 2 security and governance contract checks passed.")
PY
