#!/usr/bin/env bash

set -euo pipefail

echo "Validating optional IKAD-01 provider event-source adapters..."

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
contract_path = root / "adapters" / "providers" / "EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml"
rollback_notes_path = root / "adapters" / "providers" / "ROLLBACK_UNINSTALL_NOTES.md"
hook_catalog_path = root / "triggers" / "khook" / "hooks" / "HOOK_CATALOG_V1.yaml"

for required in [contract_path, rollback_notes_path, hook_catalog_path]:
    if not required.exists():
        fail(f"Missing required IKAD-01 artifact: {required}")

contract = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
hook_catalog = yaml.safe_load(hook_catalog_path.read_text(encoding="utf-8"))
rollback_notes = rollback_notes_path.read_text(encoding="utf-8")
rollback_notes_lc = rollback_notes.lower()

if contract.get("scope", {}).get("core_contracts_unchanged") is not True:
    fail("Adapter contract must state that core contracts remain unchanged.")

known_hooks = {item.get("id") for item in hook_catalog.get("hooks", [])}
providers = contract.get("providers", [])
if len(providers) < 1:
    fail("Provider adapter contract must define at least one provider.")

for provider in providers:
    name = provider.get("name")
    if not name:
        fail("Provider adapter entry missing provider name.")
    for source in provider.get("supported_event_sources", []):
        src_name = source.get("source")
        if not src_name:
            fail(f"Provider {name} has source missing source name.")
        hook_ids = set(source.get("normalized_hook_ids", []))
        if not hook_ids:
            fail(f"Provider {name}/{src_name} missing normalized hook ids.")
        unknown_hooks = sorted(hook_ids - known_hooks)
        if unknown_hooks:
            fail(f"Provider {name}/{src_name} references unknown hooks: {unknown_hooks}")

for token in [
    "core contracts remain unchanged",
    "rollback procedure",
    "uninstall procedure",
    "validate_provider_event_source_adapters.sh",
]:
    if token not in rollback_notes_lc:
        fail(f"Rollback/uninstall notes missing required token: {token}")

print("IKAD-01 provider adapter contract checks passed.")
PY

echo "Running IKAD-01 bounded integration tests..."
python3 tests/integration/adapters/providers/test_provider_event_source_adapters.py
