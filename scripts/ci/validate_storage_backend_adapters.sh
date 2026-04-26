#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-04 storage backend adapters..."

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
    root / "adapters" / "storage" / "STORAGE_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml"
)
rollback_notes_path = root / "adapters" / "storage" / "ROLLBACK_UNINSTALL_NOTES.md"
readme_path = root / "adapters" / "storage" / "README.md"

for required in [contract_path, rollback_notes_path, readme_path]:
    if not required.exists():
        fail(f"Missing required IKAD-04 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8").lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("Storage adapter contract must state that core contracts remain unchanged.")
if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
    fail("Storage adapter contract must enforce read-only dispatch mode.")
if contract.get("constraints", {}).get("preserve_core_index_templates") is not True:
    fail("Storage adapter contract must preserve core index templates.")

backends = contract.get("storage_backends", [])
if len(backends) < 1:
    fail("Storage adapter contract must define at least one backend.")

for backend in backends:
    name = backend.get("name")
    if not name:
        fail("Storage backend entry missing name.")
    generated_values = set(
        backend.get("outputs", {}).get("generated_values", [])
    )
    for required_value in ["storage.enabled", "storage.mode"]:
        if required_value not in generated_values:
            fail(f"Storage backend {name} missing generated value: {required_value}")
    max_templates = int(
        backend.get("outputs", {}).get("bounded_policies", {}).get("max_templates", 0)
    )
    if max_templates <= 0:
        fail(f"Storage backend {name} must set bounded max_templates.")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_storage_backend_adapters.sh",
]:
    if token not in rollback_notes:
        fail(f"Rollback/uninstall notes missing required token: {token}")

print("IKAD-04 storage adapter contract checks passed.")
PY

echo "Running IKAD-04 bounded integration tests..."
python3 tests/integration/adapters/storage/test_storage_backend_adapters.py
