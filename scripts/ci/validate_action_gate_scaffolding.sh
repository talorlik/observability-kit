#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 9 approval-gated action scaffolding..."

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
risk_path = root / "contracts" / "policy" / "TOOL_RISK_CLASSIFICATION_V1.yaml"
preconditions_path = root / "contracts" / "policy" / "ACTION_PRECONDITIONS_V1.yaml"
service_path = root / "services" / "mcp" / "runbook-execution" / "SERVICE_CONTRACT_V1.yaml"
journal_path = (
    root / "services" / "mcp" / "runbook-execution" / "journal" / "ACTION_JOURNAL_CONTRACT_V1.yaml"
)
safety_path = root / "tests" / "safety" / "action_gates" / "ACTION_GATE_SCENARIOS_V1.json"
lineage_fixture_path = (
    root / "tests" / "safety" / "action_gates" / "ACTION_JOURNAL_LINEAGE_FIXTURES_V1.json"
)
staging_path = (
    root / "tests" / "staging" / "action_gates" / "STAGING_ACTION_GATE_RESULTS_V1.json"
)

for required in [
    risk_path,
    preconditions_path,
    service_path,
    journal_path,
    safety_path,
    lineage_fixture_path,
    staging_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 9 artifact: {required}")

risk = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
preconditions = yaml.safe_load(preconditions_path.read_text(encoding="utf-8"))
service = yaml.safe_load(service_path.read_text(encoding="utf-8"))
journal = yaml.safe_load(journal_path.read_text(encoding="utf-8"))
safety = json.loads(safety_path.read_text(encoding="utf-8"))
lineage_fixture = json.loads(lineage_fixture_path.read_text(encoding="utf-8"))
staging = json.loads(staging_path.read_text(encoding="utf-8"))

# 1) Validate write-path tool exposure by risk class.
tool_map = {item["tool"]: item for item in risk.get("tool_mappings", [])}
for tool, expected_risk in [
    ("runbook-plan.v1", "write.high-risk"),
    ("remediation-execute.v1", "write.critical"),
]:
    mapping = tool_map.get(tool)
    if not mapping:
        fail(f"Risk classification missing tool mapping: {tool}")
    if mapping.get("risk_class") != expected_risk:
        fail(f"{tool} must be mapped to {expected_risk}.")
    if mapping.get("requires_approval") is not True:
        fail(f"{tool} must require approval.")

svc = service.get("service", {})
if svc.get("mode") != "approval-gated-write":
    fail("Runbook execution service must be approval-gated-write mode.")
svc_tools = {item["name"]: item for item in service.get("tools", [])}
for tool in ["runbook-plan.v1", "remediation-execute.v1"]:
    if tool not in svc_tools:
        fail(f"Runbook execution service missing write-path tool: {tool}")

# 2) Validate policy engine and approval service enforcement.
enforcement = service.get("enforcement", {})
if enforcement.get("require_policy_engine") is not True:
    fail("Service contract must require policy engine.")
if enforcement.get("require_approval_service") is not True:
    fail("Service contract must require approval service.")
if preconditions.get("failure_behavior", {}).get("on_policy_error") != "deny":
    fail("Action preconditions must deny on policy error.")
if preconditions.get("failure_behavior", {}).get("on_approval_service_unavailable") != "deny":
    fail("Action preconditions must deny when approval service is unavailable.")

# 3) Validate remediation executor precondition gating.
rules = {
    item["tool"]: item.get("execution_requirements", {})
    for item in preconditions.get("write_path_tools", [])
}
critical = rules.get("remediation-execute.v1")
if not critical:
    fail("Action preconditions must define remediation-execute.v1 requirements.")
for key in [
    "requires_policy_decision",
    "requires_approval_status",
    "requires_valid_target",
    "requires_rollback_plan",
    "requires_change_ticket",
]:
    if key not in critical:
        fail(f"remediation-execute.v1 missing precondition: {key}")
if critical.get("requires_policy_decision") != "allow":
    fail("remediation-execute.v1 requires_policy_decision must be allow.")
if critical.get("requires_approval_status") != "approved":
    fail("remediation-execute.v1 requires_approval_status must be approved.")

# 4) Validate action journaling and evidence capture completeness.
journal_required = set(journal.get("journal", {}).get("required_fields", []))
for field in [
    "action_tool",
    "policy_decision",
    "approval_decision",
    "target_resources",
    "evidence_handles",
    "final_action_outcome",
    "rollback_reference",
]:
    if field not in journal_required:
        fail(f"Action journal missing required field: {field}")
if journal.get("journal", {}).get("evidence_min_items") != 1:
    fail("Action journal must require at least one evidence handle.")
lineage_entries = lineage_fixture.get("entries", [])
if not lineage_entries:
    fail("Action journal lineage fixture must include entries.")
for entry in lineage_entries:
    missing = sorted(journal_required - set(entry.keys()))
    if missing:
        fail(f"Action journal lineage entry missing fields: {missing}")
if not any(
    entry.get("final_action_outcome") == "rolled-back" for entry in lineage_entries
):
    fail("Action journal lineage fixture must include rollback branch entry.")
if not any(entry.get("final_action_outcome") == "executed" for entry in lineage_entries):
    fail("Action journal lineage fixture must include executed branch entry.")

# 5) Validate rejected-action and rollback determinism.
scenarios = safety.get("scenarios", [])
scenario_map = {entry.get("id"): entry for entry in scenarios}
for required in [
    "missing-approval-high-risk",
    "critical-denied-by-policy",
    "critical-rollback-deterministic",
]:
    if required not in scenario_map:
        fail(f"Action gate scenarios missing required case: {required}")
if scenario_map["missing-approval-high-risk"].get("expected_outcome") != "blocked":
    fail("Missing approval scenario must deterministically block.")
if scenario_map["critical-denied-by-policy"].get("expected_outcome") != "blocked":
    fail("Policy deny scenario must deterministically block.")
if scenario_map["critical-rollback-deterministic"].get("expected_outcome") != "rolled-back":
    fail("Rollback scenario must deterministically roll back.")

# 6) Validate CI plus staging action-gate tests.
staging_results = staging.get("results", [])
if len(staging_results) < 5:
    fail("Staging action-gate results must include all required scenarios.")
if any(result.get("status") != "pass" for result in staging_results):
    fail("All staging action-gate test results must pass.")

workflow = (root / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
batch9_smoke = (root / "scripts" / "ci" / "validate_batch9_smoke.sh").read_text(
    encoding="utf-8"
)
if "validate_action_gate_scaffolding.sh" not in workflow:
    fail("Main CI workflow must include action-gate scaffolding validator.")
if "validate_action_gate_scaffolding.sh" not in batch9_smoke:
    fail("Batch 9 smoke bundle must include action-gate scaffolding validator.")

print("Batch 9 approval-gated action scaffold checks passed.")
PY

echo "Running action-gate scenario enforcement tests..."
python3 tests/safety/action_gates/test_action_gate_scenarios.py
