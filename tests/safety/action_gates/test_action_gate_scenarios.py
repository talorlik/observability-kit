#!/usr/bin/env python3

import json
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


def evaluate_outcome(scenario: dict) -> str:
    if scenario.get("policy_decision") != "allow":
        return "blocked"
    if scenario.get("approval_status") != "approved":
        return "blocked"
    if scenario.get("valid_target") is not True:
        return "blocked"
    if scenario.get("rollback_plan_present") is not True:
        return "blocked"
    if scenario.get("tool") == "remediation-execute.v1" and scenario.get(
        "change_ticket_present"
    ) is not True:
        return "blocked"
    if scenario.get("simulate_runtime_failure") is True:
        return "rolled-back"
    return "executed"


def main() -> None:
    preconditions = yaml.safe_load(
        Path("contracts/policy/ACTION_PRECONDITIONS_V1.yaml").read_text(encoding="utf-8")
    )
    scenarios = json.loads(
        Path("tests/safety/action_gates/ACTION_GATE_SCENARIOS_V1.json").read_text(
            encoding="utf-8"
        )
    ).get("scenarios", [])
    lineage_fixture = json.loads(
        Path("tests/safety/action_gates/ACTION_JOURNAL_LINEAGE_FIXTURES_V1.json").read_text(
            encoding="utf-8"
        )
    )
    journal_contract = yaml.safe_load(
        Path(
            "services/mcp/runbook-execution/journal/ACTION_JOURNAL_CONTRACT_V1.yaml"
        ).read_text(encoding="utf-8")
    )

    if not scenarios:
        fail("Action gate scenarios cannot be empty.")

    required_fields = set(
        journal_contract.get("journal", {}).get("required_fields", [])
    )
    entries = lineage_fixture.get("entries", [])
    if len(entries) < 2:
        fail("Action journal lineage fixture must include at least two entries.")

    for entry in entries:
        missing = sorted(required_fields - set(entry.keys()))
        if missing:
            fail(f"Action journal lineage entry missing required fields: {missing}")
    if not any(item.get("final_action_outcome") == "rolled-back" for item in entries):
        fail("Action journal lineage fixture must include rolled-back outcome entry.")

    execution_requirements = {
        item.get("tool"): item.get("execution_requirements", {})
        for item in preconditions.get("write_path_tools", [])
    }
    if execution_requirements.get("runbook-plan.v1", {}).get(
        "requires_approval_status"
    ) != "approved":
        fail("runbook-plan.v1 requires_approval_status must be approved.")
    if execution_requirements.get("remediation-execute.v1", {}).get(
        "requires_change_ticket"
    ) is not True:
        fail("remediation-execute.v1 must require change ticket.")

    for scenario in scenarios:
        expected = scenario.get("expected_outcome")
        actual = evaluate_outcome(scenario)
        if actual != expected:
            fail(
                f"Scenario {scenario.get('id')} expected {expected}, evaluated {actual}."
            )

    print("Action gate scenario enforcement tests passed.")


if __name__ == "__main__":
    main()
