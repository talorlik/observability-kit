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
    "docs/adapters/ADAPTER_ENABLEMENT_GUIDE.md",
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

schema_coverage = json.loads(Path("contracts/adapters/ADAPTER_CONTRACT_SCHEMA_COVERAGE.json").read_text())
required_classes = {
    "provider",
    "backend",
    "identity",
    "secrets",
    "network",
    "cicd",
}
if set(schema_coverage.get("required_adapter_classes", [])) != required_classes:
    print("ERROR: Adapter schema coverage must include provider/backend/identity/secrets/network/cicd.")
    sys.exit(1)

activation = json.loads(Path("contracts/adapters/PROFILE_ACTIVATION_SAFETY_VALIDATION.json").read_text())
if set(activation.get("activation_modes_validated", [])) != {"adapter-enabled", "adapter-disabled"}:
    print("ERROR: Profile activation safety must validate enabled and disabled modes.")
    sys.exit(1)
if len(activation.get("core_paths_verified", [])) < 3:
    print("ERROR: Profile activation safety must verify core path stability.")
    sys.exit(1)

stub_validation = json.loads(
    Path("contracts/adapters/IDENTITY_SECRETS_NETWORK_STUB_METADATA_VALIDATION.json").read_text()
)
required_stub_fields = set(stub_validation.get("required_metadata_fields", []))

for stub in [
    "adapters/identity/STUB_METADATA.json",
    "adapters/secrets/STUB_METADATA.json",
    "adapters/network/STUB_METADATA.json",
]:
    data = json.loads(Path(stub).read_text())
    missing_fields = sorted(required_stub_fields - set(data.keys()))
    if missing_fields:
        print(f"ERROR: Stub metadata missing required fields in {stub}: {missing_fields}")
        sys.exit(1)
    if not data.get("prerequisites") or not data.get("generated_values"):
        print(f"ERROR: Stub metadata incomplete: {stub}")
        sys.exit(1)

ci_gating = json.loads(Path("contracts/adapters/ADAPTER_CI_CONTRACT_GATING_VALIDATION.json").read_text())
if len(ci_gating.get("required_ci_gates", [])) < 3:
    print("ERROR: Adapter CI contract gating must include core, neutrality, and smoke gates.")
    sys.exit(1)

runbook = Path("docs/runbooks/CORE_ADAPTER_INTEGRATIONS_OPERATOR_GUIDE.md").read_text()
guide = Path("docs/adapters/ADAPTER_ENABLEMENT_GUIDE.md").read_text()
for token in ("enable", "validate", "disable", "rollback"):
    if token not in runbook.lower():
        print(f"ERROR: Runbook missing operations guidance token: {token}")
        sys.exit(1)
    if token not in guide.lower():
        print(f"ERROR: Adapter guide missing operations guidance token: {token}")
        sys.exit(1)

print("Batch 13 adapter integration checks passed.")
PY

bash scripts/ci/validate_gitops_neutrality.sh
