#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-05 network and ingress adapters..."

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
    root / "adapters" / "network" / "NETWORK_INGRESS_ADAPTER_COMPATIBILITY_V1.yaml"
)
rollback_notes_path = root / "adapters" / "network" / "ROLLBACK_UNINSTALL_NOTES.md"
stub_path = root / "adapters" / "network" / "STUB_METADATA.json"

for required in [contract_path, rollback_notes_path, stub_path]:
    if not required.exists():
        fail(f"Missing required IKAD-05 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8").lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("Network adapter contract must state that core contracts remain unchanged.")
if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
    fail("Network adapter contract must enforce read-only dispatch mode.")
if contract.get("constraints", {}).get("requires_network_policy") is not True:
    fail("Network adapter contract must enforce network policy requirement.")

backends = contract.get("network_ingress_backends", [])
if len(backends) < 1:
    fail("Network adapter contract must define at least one backend.")

for backend in backends:
    name = backend.get("name")
    if not name:
        fail("Network backend entry missing name.")
    generated_values = set(
        backend.get("outputs", {}).get("generated_values", [])
    )
    for required_value in ["network.enabled", "network.mode"]:
        if required_value not in generated_values:
            fail(f"Network backend {name} missing generated value: {required_value}")
    max_routes = int(
        backend.get("outputs", {}).get("bounded_rules", {}).get("max_routes", 0)
    )
    if max_routes <= 0:
        fail(f"Network backend {name} must set bounded max_routes.")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_network_ingress_adapters.sh",
]:
    if token not in rollback_notes:
        fail(f"Rollback/uninstall notes missing required token: {token}")

print("IKAD-05 network adapter contract checks passed.")
PY

echo "Running IKAD-05 bounded integration tests..."
python3 tests/integration/adapters/network/test_network_ingress_adapters.py
