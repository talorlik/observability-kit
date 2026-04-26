#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def main() -> None:
    fixture_path = Path(
        "tests/integration/agent_orchestration/READ_ONLY_CEO_SYNTHESIS_E2E_V1.json"
    )
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    if fixture.get("mode") != "read-only":
        fail("E2E fixture mode must be read-only.")

    if fixture.get("entry_agent") != "ops-ceo-agent":
        fail("E2E fixture entry agent must be ops-ceo-agent.")

    path = fixture.get("delegation_path", [])
    if not path or path[0] != "ops-ceo-agent" or path[-1] != "ops-ceo-agent":
        fail("Delegation path must start and end with ops-ceo-agent.")

    if fixture.get("specialist_peer_calls_blocked") is not True:
        fail("E2E fixture must assert specialist peer calls are blocked.")

    catalog = yaml.safe_load(
        Path("agents/catalog/AGENT_CATALOG_V1.yaml").read_text(encoding="utf-8")
    )
    bindings = yaml.safe_load(
        Path("agents/policies/TOOL_BINDINGS_V1.yaml").read_text(encoding="utf-8")
    )
    catalog_agents = {entry["name"]: entry for entry in catalog.get("agents", [])}
    policy_agents = bindings.get("agent_tool_bindings", {})
    if set(catalog_agents.keys()) != set(policy_agents.keys()):
        fail("Catalog-to-policy agent set mismatch.")
    for agent_name, entry in catalog_agents.items():
        expected_tools = set(entry.get("allowed_mcp_tools", []))
        actual_tools = set(policy_agents.get(agent_name, {}).get("tools", []))
        if expected_tools != actual_tools:
            fail(f"Catalog-to-policy tool mismatch for {agent_name}.")

    casefile_outputs = fixture.get("casefile", {}).get("outputs", [])
    if len(casefile_outputs) < 3:
        fail("Case-file outputs must include at least three specialist outputs.")

    synthesis = fixture.get("final_synthesis", {})
    if synthesis.get("agent") != "ops-ceo-agent":
        fail("Final synthesis must be produced by ops-ceo-agent.")

    evidence_handles = synthesis.get("evidence_handles", [])
    if len(evidence_handles) < 2:
        fail("Final synthesis must include evidence handles.")

    persistence = fixture.get("evidence_persistence", {})
    if persistence.get("persisted_to_casefile") is not True:
        fail("E2E fixture must assert evidence persistence to case-file.")
    required_fields = set(persistence.get("required_fields", []))
    if required_fields != {"handle", "source_agent", "recorded_at"}:
        fail("Evidence persistence required fields mismatch.")
    persisted_records = persistence.get("persisted_records", [])
    if len(persisted_records) < 2:
        fail("Evidence persistence must include at least two persisted records.")
    for record in persisted_records:
        if not required_fields.issubset(set(record.keys())):
            fail("Persisted evidence record missing required fields.")

    confidence = synthesis.get("confidence", -1)
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        fail("Final synthesis confidence must be numeric in [0,1].")

    print("Read-only CEO synthesis E2E fixture checks passed.")


if __name__ == "__main__":
    main()
