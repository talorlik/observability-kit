#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 7 multi-agent scaffolding..."

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
catalog_path = root / "agents" / "catalog" / "AGENT_CATALOG_V1.yaml"
bindings_path = root / "agents" / "policies" / "TOOL_BINDINGS_V1.yaml"
prompt_fragments_path = (
    root / "agents" / "prompts" / "fragments" / "REQUIRED_PROMPT_FRAGMENTS_V1.yaml"
)
communication_path = root / "contracts" / "ai" / "COMMUNICATION_GRAPH_V1.yaml"
risk_path = root / "contracts" / "policy" / "TOOL_RISK_CLASSIFICATION_V1.yaml"
e2e_path = (
    root
    / "tests"
    / "integration"
    / "agent_orchestration"
    / "READ_ONLY_CEO_SYNTHESIS_E2E_V1.json"
)

for required in [
    catalog_path,
    bindings_path,
    prompt_fragments_path,
    communication_path,
    risk_path,
    e2e_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 7 artifact: {required}")

catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
bindings = yaml.safe_load(bindings_path.read_text(encoding="utf-8"))
prompt_fragments = yaml.safe_load(prompt_fragments_path.read_text(encoding="utf-8"))
communication = yaml.safe_load(communication_path.read_text(encoding="utf-8"))
risk = yaml.safe_load(risk_path.read_text(encoding="utf-8"))
e2e = json.loads(e2e_path.read_text(encoding="utf-8"))

# 1) Validate CEO and manager invocation policy alignment.
agents = {entry["name"]: entry for entry in catalog.get("agents", [])}
required_managers = {"triage-director", "investigation-manager", "action-governor"}
if not required_managers.issubset(set(catalog.get("roles", {}).get("manager", []))):
    fail("Manager role set must include triage-director, investigation-manager, and action-governor.")

ceo = agents.get("ops-ceo-agent")
if not ceo:
    fail("Agent catalog must include ops-ceo-agent.")
ceo_invocations = set(ceo.get("allowed_agent_invocations", []))
if not required_managers.issubset(ceo_invocations):
    fail("ops-ceo-agent must be able to invoke all manager agents.")

allowed_edges = {
    (edge.get("from"), edge.get("to"))
    for edge in communication.get("allowed_edges", [])
}
if ("ceo", "manager") not in allowed_edges:
    fail("Communication graph must allow CEO -> manager edge.")
for manager_name in required_managers:
    manager = agents.get(manager_name)
    if not manager:
        fail(f"Agent catalog missing manager: {manager_name}")
    if manager.get("role") != "manager":
        fail(f"{manager_name} must be registered with manager role.")

# 1b) Validate catalog-to-policy conformance for all agents.
catalog_agent_names = set(agents.keys())
binding_agent_names = set(bindings.get("agent_tool_bindings", {}).keys())
if catalog_agent_names != binding_agent_names:
    missing_bindings = sorted(catalog_agent_names - binding_agent_names)
    extra_bindings = sorted(binding_agent_names - catalog_agent_names)
    fail(
        "Catalog-to-policy conformance mismatch. "
        f"Missing bindings: {missing_bindings}; Extra bindings: {extra_bindings}"
    )

for agent_name, agent in agents.items():
    binding = bindings.get("agent_tool_bindings", {}).get(agent_name, {})
    catalog_tools = set(agent.get("allowed_mcp_tools", []))
    policy_tools = set(binding.get("tools", []))
    if catalog_tools != policy_tools:
        fail(
            f"Catalog-to-policy tool mismatch for {agent_name}. "
            f"Catalog: {sorted(catalog_tools)} Policy: {sorted(policy_tools)}"
        )

# 2) Validate specialist read-only tool binding restrictions.
tool_to_risk = {entry["tool"]: entry["risk_class"] for entry in risk.get("tool_mappings", [])}
read_only_agents = {
    "incident-investigator",
    "logs-analyst",
    "trace-analyst",
    "metrics-correlator",
    "graph-analyst",
    "change-correlator",
    "evidence-summarizer",
}
agent_tool_bindings = bindings.get("agent_tool_bindings", {})
for specialist in read_only_agents:
    binding = agent_tool_bindings.get(specialist)
    if not binding:
        fail(f"Tool bindings missing read-only specialist: {specialist}")
    if binding.get("class") != "specialist_read_only":
        fail(f"{specialist} must be bound to specialist_read_only class.")
    for tool in binding.get("tools", []):
        risk_class = tool_to_risk.get(tool)
        if risk_class in {"write.high-risk", "write.critical"}:
            fail(f"{specialist} cannot mount high-risk or critical write tool: {tool}")

# 3) Validate action specialist approval blocks.
for specialist in ["runbook-planner", "remediation-executor"]:
    binding = agent_tool_bindings.get(specialist)
    if not binding:
        fail(f"Tool bindings missing action specialist: {specialist}")
    gate = binding.get("approval_gate", {})
    if gate.get("required") is not True:
        fail(f"{specialist} must require an approval gate.")
    allowed_values = set(gate.get("allowed_values", []))
    if allowed_values != {"approved"}:
        fail(f"{specialist} approval gate must allow only approved state.")
if "rollback_plan.present == true" not in agent_tool_bindings.get(
    "remediation-executor", {}
).get("action_preconditions", []):
    fail("remediation-executor must require rollback plan precondition.")

# 4) Validate required prompt-fragment coverage.
required_prompt_ids = {
    "role_definition",
    "allowed_tools",
    "prohibited_actions",
    "casefile_behavior",
    "escalation_rules",
}
declared_fragment_ids = {
    item.get("id") for item in prompt_fragments.get("required_fragments", [])
}
if declared_fragment_ids != required_prompt_ids:
    fail("Prompt fragments must declare the required fragment IDs exactly.")
coverage = prompt_fragments.get("role_fragment_coverage", {})
for agent_name in agents.keys():
    includes = set(coverage.get(agent_name, {}).get("includes", []))
    missing = sorted(required_prompt_ids - includes)
    if missing:
        fail(f"Prompt fragment coverage missing for {agent_name}: {missing}")

# 5) Validate end-to-end read-only orchestration synthesis with evidence handles.
if e2e.get("mode") != "read-only":
    fail("E2E orchestration fixture must be read-only mode.")
if e2e.get("entry_agent") != "ops-ceo-agent":
    fail("E2E orchestration fixture entry_agent must be ops-ceo-agent.")
path = e2e.get("delegation_path", [])
if not path or path[0] != "ops-ceo-agent" or path[-1] != "ops-ceo-agent":
    fail("E2E delegation path must start and end with ops-ceo-agent.")
if e2e.get("specialist_peer_calls_blocked") is not True:
    fail("E2E fixture must assert specialist peer-call blocking.")
final = e2e.get("final_synthesis", {})
if final.get("agent") != "ops-ceo-agent":
    fail("Final synthesis must be produced by ops-ceo-agent.")
if len(final.get("evidence_handles", [])) < 2:
    fail("Final synthesis must include at least two evidence handles.")
if e2e.get("evidence_persistence", {}).get("persisted_to_casefile") is not True:
    fail("E2E fixture must assert evidence persistence to case-file.")
evidence_fields = set(e2e.get("evidence_persistence", {}).get("required_fields", []))
if evidence_fields != {"handle", "source_agent", "recorded_at"}:
    fail("E2E fixture evidence persistence fields are incomplete.")

# 6) Validate CI topology policy checks.
workflow = (root / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
batch7_smoke = (root / "scripts" / "ci" / "validate_batch7_smoke.sh").read_text(
    encoding="utf-8"
)
if "validate_multi_agent_scaffolding.sh" not in workflow:
    fail("Main CI workflow must include multi-agent scaffolding validator.")
if "validate_multi_agent_scaffolding.sh" not in batch7_smoke:
    fail("Batch 7 smoke bundle must include multi-agent scaffolding validator.")
denied_edges = {
    (edge.get("from"), edge.get("to"))
    for edge in communication.get("denied_edges", [])
}
if ("specialist", "specialist") not in denied_edges:
    fail("Communication graph must explicitly deny specialist -> specialist.")

print("Batch 7 multi-agent scaffold checks passed.")
PY

echo "Running Batch 7 orchestration integration fixture checks..."
python3 tests/integration/agent_orchestration/test_read_only_ceo_synthesis.py
