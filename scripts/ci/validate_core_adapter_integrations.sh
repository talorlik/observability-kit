#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 13 core adapter integrations..."

python3 - <<'PY'
from pathlib import Path
import json
import sys

required = [
    "install/profiles/adapters/ADAPTER_CONTRACT.schema.json",
    "contracts/adapters/ADAPTER_CONTRACT_SCHEMA_COVERAGE.json",
    "contracts/adapters/PROFILE_ACTIVATION_SAFETY_VALIDATION.json",
    "contracts/adapters/IDENTITY_SECRETS_NETWORK_STUB_METADATA_VALIDATION.json",
    "contracts/adapters/ADAPTER_CI_CONTRACT_GATING_VALIDATION.json",
    "contracts/adapters/CICD_ADAPTER_NEUTRALITY_VALIDATION.json",
    "adapters/identity/STUB_METADATA.json",
    "adapters/secrets/STUB_METADATA.json",
    "adapters/network/STUB_METADATA.json",
    "docs/runbooks/CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md",
]

for path in required:
    if not Path(path).exists():
        print(f"ERROR: Missing required Batch 13 artifact: {path}")
        sys.exit(1)

for contract_path in required[1:6]:
    payload = json.loads(Path(contract_path).read_text())
    if payload.get("validation_result", {}).get("status") != "pass":
        print(f"ERROR: Contract does not pass: {contract_path}")
        sys.exit(1)

for stub in [
    "adapters/identity/STUB_METADATA.json",
    "adapters/secrets/STUB_METADATA.json",
    "adapters/network/STUB_METADATA.json",
]:
    data = json.loads(Path(stub).read_text())
    if not data.get("prerequisites") or not data.get("generated_values"):
        print(f"ERROR: Stub metadata incomplete: {stub}")
        sys.exit(1)

print("Batch 13 adapter integration checks passed.")
PY

bash scripts/ci/validate_gitops_neutrality.sh
