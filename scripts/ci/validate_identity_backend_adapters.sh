#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-02 identity backend adapters..."

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
    root / "adapters" / "identity" / "IDENTITY_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml"
)
rollback_notes_path = root / "adapters" / "identity" / "ROLLBACK_UNINSTALL_NOTES.md"
identity_matrix_path = root / "contracts" / "policy" / "IDENTITY_ACCESS_MATRIX_V1.yaml"

for required in [contract_path, rollback_notes_path, identity_matrix_path]:
    if not required.exists():
        fail(f"Missing required IKAD-02 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
identity_matrix = yaml.safe_load(identity_matrix_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8")
rollback_notes_lc = rollback_notes.lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("Identity adapter contract must state that core contracts remain unchanged.")
if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
    fail("Identity adapter contract must enforce read-only dispatch mode.")

known_service_accounts = {
    item.get("serviceAccount")
    for section in ["agents", "mcp_services"]
    for item in identity_matrix.get("service_accounts", {}).get(section, [])
}

backends = contract.get("identity_backends", [])
if len(backends) < 1:
    fail("Identity adapter contract must define at least one backend.")

for backend in backends:
    name = backend.get("name")
    if not name:
        fail("Identity backend entry missing name.")
    generated_values = set(
        backend.get("outputs", {}).get("generated_values", [])
    )
    for required_value in [
        "identity.enabled",
        "identity.mode",
        "identity.serviceAccountAnnotations",
    ]:
        if required_value not in generated_values:
            fail(f"Identity backend {name} missing generated value: {required_value}")
    max_entries = int(
        backend.get("outputs", {}).get("bounded_annotations", {}).get("max_entries", 0)
    )
    if max_entries <= 0:
        fail(f"Identity backend {name} must set bounded annotation max_entries.")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_identity_backend_adapters.sh",
]:
    if token not in rollback_notes_lc:
        fail(f"Rollback/uninstall notes missing required token: {token}")

if not known_service_accounts:
    fail("Identity access matrix must include service accounts for binding checks.")

print("IKAD-02 identity adapter contract checks passed.")
PY

echo "Running IKAD-02 bounded integration tests..."
python3 tests/integration/adapters/identity/test_identity_backend_adapters.py
