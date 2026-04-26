#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-06 CI/CD adapter templates..."

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
from pathlib import Path
import sys

import yaml


def fail(message: str) -> None:
    print(f"ERROR: {message}")
    sys.exit(1)


root = Path(".")
contract_path = (
    root / "adapters" / "cicd" / "CICD_ADAPTER_TEMPLATE_COMPATIBILITY_V1.yaml"
)
rollback_notes_path = root / "adapters" / "cicd" / "ROLLBACK_UNINSTALL_NOTES.md"
readme_path = root / "adapters" / "cicd" / "README.md"

for required in [contract_path, rollback_notes_path, readme_path]:
    if not required.exists():
        fail(f"Missing required IKAD-06 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8").lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("CI/CD adapter contract must state that core contracts remain unchanged.")
if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
    fail("CI/CD adapter contract must enforce read-only dispatch mode.")
if contract.get("constraints", {}).get("requires_validation_before_deploy") is not True:
    fail("CI/CD adapter contract must enforce validation before deploy.")

templates = contract.get("cicd_templates", [])
if len(templates) < 1:
    fail("CI/CD adapter contract must define at least one template provider.")

for item in templates:
    name = item.get("name")
    if not name:
        fail("CI/CD template entry missing name.")
    generated_values = set(
        item.get("outputs", {}).get("generated_values", [])
    )
    for required_value in ["cicd.enabled", "cicd.mode", "cicd.pipelineTemplateRef"]:
        if required_value not in generated_values:
            fail(f"CI/CD provider {name} missing generated value: {required_value}")
    max_steps = int(
        item.get("outputs", {}).get("bounded_steps", {}).get("max_validation_steps", 0)
    )
    if max_steps <= 0:
        fail(f"CI/CD provider {name} must set bounded max_validation_steps.")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_cicd_adapter_templates.sh",
]:
    if token not in rollback_notes:
        fail(f"Rollback/uninstall notes missing required token: {token}")

print("IKAD-06 CI/CD adapter contract checks passed.")
PY

echo "Running IKAD-06 bounded integration tests..."
python3 tests/integration/adapters/cicd/test_cicd_adapter_templates.py
