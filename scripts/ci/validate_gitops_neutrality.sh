#!/usr/bin/env bash

set -euo pipefail

echo "Validating CI/CD neutrality constraints..."

python3 - <<'PY'
from pathlib import Path
import json
import sys

contract = json.loads(
    Path("contracts/adapters/CICD_ADAPTER_NEUTRALITY_VALIDATION.json").read_text()
)

if contract.get("validation_result", {}).get("status") != "pass":
    print("ERROR: CI/CD neutrality contract must pass.")
    sys.exit(1)

checks = set(contract.get("checks", []))
required = {
    "argocd_reference_default_preserved",
    "no_vendor_specific_core_manifest_dependencies",
    "neutrality_valid_with_and_without_adapters",
}
missing = required - checks
if missing:
    print(f"ERROR: Missing neutrality checks: {sorted(missing)}")
    sys.exit(1)

print("CI/CD neutrality validation passed.")
PY
