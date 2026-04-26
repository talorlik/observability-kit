#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 3 shared state and envelope contracts..."

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
casefile_schema_path = root / "contracts" / "ai" / "CASEFILE_SCHEMA_V1.json"
casefile_lifecycle_path = root / "contracts" / "ai" / "CASEFILE_LIFECYCLE_V1.md"
envelope_path = root / "contracts" / "ai" / "AGENT_ENVELOPE_V1.json"
communication_path = root / "contracts" / "ai" / "COMMUNICATION_GRAPH_V1.yaml"
contradiction_path = root / "contracts" / "ai" / "CONTRADICTION_ROLLUP_RULES_V1.yaml"
replay_path = root / "contracts" / "ai" / "REPLAY_RESUME_RULES_V1.yaml"
fixtures_path = root / "contracts" / "ai" / "CASEFILE_FIXTURES_V1.json"
edge_policy_path = root / "agents" / "policies" / "edge-policy.rego"

for required in [
    casefile_schema_path,
    casefile_lifecycle_path,
    envelope_path,
    communication_path,
    contradiction_path,
    replay_path,
    fixtures_path,
    edge_policy_path,
]:
    if not required.exists():
        fail(f"Missing required Batch 3 contract artifact: {required}")

casefile_schema = json.loads(casefile_schema_path.read_text())
casefile_lifecycle = casefile_lifecycle_path.read_text()
envelope_schema = json.loads(envelope_path.read_text())
communication_graph = yaml.safe_load(communication_path.read_text())
contradiction_rules = yaml.safe_load(contradiction_path.read_text())
replay_rules = yaml.safe_load(replay_path.read_text())
fixtures = json.loads(fixtures_path.read_text())
edge_policy = edge_policy_path.read_text()

# 1) Case-file schema lifecycle coverage
case_required = set(casefile_schema.get("required", []))
for field in [
    "case_id",
    "status",
    "incident_context",
    "agent_outputs",
    "evidence_handles",
    "approval_state",
    "action_journal",
    "lineage",
]:
    if field not in case_required:
        fail(f"Case-file schema missing required field: {field}")

status_enum = (
    casefile_schema.get("properties", {}).get("status", {}).get("enum", [])
)
for status in [
    "open",
    "triaging",
    "investigating",
    "awaiting-approval",
    "executing",
    "resolved",
    "closed",
    "rejected",
]:
    if status not in status_enum:
        fail(f"Case-file schema missing lifecycle state: {status}")

for token in [
    "| `open` | `triaging` |",
    "| `triaging` | `investigating` |",
    "| `investigating` | `awaiting-approval` |",
    "| `awaiting-approval` | `executing` |",
    "| `resolved` | `closed` |",
]:
    if token not in casefile_lifecycle:
        fail("Case-file lifecycle markdown missing required transition table row.")

allowed_transitions = {
    ("open", "triaging"),
    ("triaging", "investigating"),
    ("investigating", "awaiting-approval"),
    ("investigating", "resolved"),
    ("awaiting-approval", "executing"),
    ("awaiting-approval", "rejected"),
    ("executing", "resolved"),
    ("resolved", "closed"),
}

# 1b) Case-file fixtures and lifecycle transition path tests
if fixtures.get("schema_version") != "v1":
    fail("Case-file fixtures must be versioned as v1.")

fixture_entries = fixtures.get("fixtures", {})
for required_fixture in ["create", "update", "resume", "close"]:
    if required_fixture not in fixture_entries:
        fail(f"Case-file fixtures missing scenario: {required_fixture}")

for name, fixture in fixture_entries.items():
    missing_fields = sorted(case_required - set(fixture.keys()))
    if missing_fields:
        fail(f"Case-file fixture '{name}' missing required fields: {missing_fields}")
    if fixture.get("schema_version") != "v1":
        fail(f"Case-file fixture '{name}' must use schema_version v1.")
    if fixture.get("status") not in status_enum:
        fail(f"Case-file fixture '{name}' has invalid status.")

for path in fixtures.get("transition_paths", []):
    if len(path) < 2:
        fail("Each transition path fixture must include at least two states.")
    for from_state, to_state in zip(path, path[1:]):
        if (from_state, to_state) not in allowed_transitions:
            fail(
                "Case-file lifecycle transition path contains forbidden edge: "
                f"{from_state} -> {to_state}"
            )

for sample in fixtures.get("invalid_transition_samples", []):
    if sample.get("type") == "communication-edge":
        continue
    from_state = sample.get("from")
    to_state = sample.get("to")
    if (from_state, to_state) in allowed_transitions:
        fail(
            "Invalid transition sample unexpectedly matches an allowed transition: "
            f"{from_state} -> {to_state}"
        )

# 2) Inter-agent envelope compatibility
envelope_required = set(envelope_schema.get("required", []))
for field in [
    "objective",
    "findings",
    "evidence_handles",
    "assumptions",
    "confidence",
    "risk_level",
    "recommended_next_action",
]:
    if field not in envelope_required:
        fail(f"Agent envelope schema missing required field: {field}")

confidence = envelope_schema.get("properties", {}).get("confidence", {})
if confidence.get("minimum") != 0 or confidence.get("maximum") != 1:
    fail("Agent envelope confidence must be bounded between 0 and 1.")

# 3) Contradiction handling and confidence rollup determinism
steps = contradiction_rules.get("deterministic_resolution", {}).get("steps", [])
if len(steps) < 3:
    fail("Contradiction rules must define deterministic multi-step resolution.")
if (
    contradiction_rules.get("confidence_rollup", {})
    .get("deterministic_rounding", {})
    .get("precision")
    != 4
):
    fail("Confidence rollup must define deterministic rounding precision.")

# 4) Restart-safe replay behavior
resume_required = replay_rules.get("resume_source", {}).get("required")
if resume_required != "casefile_persistent_store":
    fail("Replay rules must require persistent case-file as resume source.")

forbidden_resume = set(replay_rules.get("resume_source", {}).get("forbidden", []))
for token in ["transient_agent_memory", "ephemeral_prompt_state"]:
    if token not in forbidden_resume:
        fail(f"Replay rules missing forbidden resume source: {token}")

if replay_rules.get("replay_behavior", {}).get("unknown_state") != "fail_closed":
    fail("Replay behavior must fail closed on unknown state.")

# 5) Communication graph policy enforcement
if communication_graph.get("metadata", {}).get("default_edge_policy") != "deny":
    fail("Communication graph must enforce deny-by-default.")
allowed_edges = {
    (edge.get("from"), edge.get("to"))
    for edge in communication_graph.get("allowed_edges", [])
}
for edge in [("ceo", "manager"), ("manager", "specialist"), ("ceo", "specialist")]:
    if edge not in allowed_edges:
        fail(f"Communication graph missing required allowed edge: {edge}")
denied_edges = {
    (edge.get("from"), edge.get("to"))
    for edge in communication_graph.get("denied_edges", [])
}
if ("specialist", "specialist") not in denied_edges:
    fail("Communication graph must explicitly deny specialist->specialist.")

if not re.search(r"default allow = false", edge_policy):
    fail("Edge policy rego must enforce deny-by-default.")
for pattern in [
    r'input\.from == "ceo"\s+input\.to == "manager"',
    r'input\.from == "manager"\s+input\.to == "specialist"',
    r'input\.from == "ceo"\s+input\.to == "specialist"',
]:
    if not re.search(pattern, edge_policy, flags=re.MULTILINE):
        fail("Edge policy rego missing required allow path.")
if not re.search(
    r'input\.from == "specialist"\s+input\.to == "specialist"',
    edge_policy,
    flags=re.MULTILINE,
):
    fail("Edge policy rego missing specialist->specialist deny coverage.")

# 5b) Forbidden communication-edge policy denials
deny_by_default = communication_graph.get("metadata", {}).get("default_edge_policy") == "deny"
if not deny_by_default:
    fail("Communication edge tests require deny-by-default policy.")


def policy_allows(from_role: str, to_role: str) -> bool:
    return (from_role, to_role) in allowed_edges


for forbidden in [("specialist", "specialist"), ("specialist", "ceo"), ("manager", "ceo")]:
    if policy_allows(*forbidden):
        fail(f"Forbidden communication edge unexpectedly allowed: {forbidden}")

for allowed in [("ceo", "manager"), ("manager", "specialist"), ("ceo", "specialist")]:
    if not policy_allows(*allowed):
        fail(f"Required communication edge unexpectedly denied: {allowed}")

# 6) CI schema gate results (enforcement in smoke + workflow)
batch3_smoke = (root / "scripts" / "ci" / "validate_batch3_smoke.sh").read_text()
workflow = (root / ".github" / "workflows" / "ci.yaml").read_text()
if "validate_ai_state_contracts.sh" not in batch3_smoke:
    fail("Batch 3 smoke bundle must run state/envelope contract validator.")
if "validate_ai_state_contracts.sh" not in workflow:
    fail("Main CI workflow must include state/envelope contract validator.")

print("Batch 3 shared state and envelope contract checks passed.")
PY
