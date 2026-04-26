#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-03 secrets backend adapters..."

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
    root / "adapters" / "secrets" / "SECRETS_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml"
)
rollback_notes_path = root / "adapters" / "secrets" / "ROLLBACK_UNINSTALL_NOTES.md"
stub_path = root / "adapters" / "secrets" / "STUB_METADATA.json"

for required in [contract_path, rollback_notes_path, stub_path]:
    if not required.exists():
        fail(f"Missing required IKAD-03 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8")
rollback_notes_lc = rollback_notes.lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("Secrets adapter contract must state that core contracts remain unchanged.")
if contract.get("constraints", {}).get("dispatch_mode") != "read-only":
    fail("Secrets adapter contract must enforce read-only dispatch mode.")
if contract.get("constraints", {}).get("requires_secret_store_refs_only") is not True:
    fail("Secrets adapter contract must require secret-store references only.")

backends = contract.get("secrets_backends", [])
if len(backends) < 1:
    fail("Secrets adapter contract must define at least one backend.")

for backend in backends:
    name = backend.get("name")
    if not name:
        fail("Secrets backend entry missing name.")
    generated_values = set(
        backend.get("outputs", {}).get("generated_values", [])
    )
    for required_value in [
        "secrets.enabled",
        "secrets.mode",
        "secrets.externalRef",
    ]:
        if required_value not in generated_values:
            fail(f"Secrets backend {name} missing generated value: {required_value}")
    max_entries = int(
        backend.get("outputs", {}).get("bounded_mappings", {}).get("max_entries", 0)
    )
    if max_entries <= 0:
        fail(f"Secrets backend {name} must set bounded mapping max_entries.")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_secrets_backend_adapters.sh",
]:
    if token not in rollback_notes_lc:
        fail(f"Rollback/uninstall notes missing required token: {token}")

print("IKAD-03 secrets adapter contract checks passed.")
PY

echo "Running IKAD-03 bounded integration tests..."
python3 tests/integration/adapters/secrets/test_secrets_backend_adapters.py
