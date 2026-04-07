#!/usr/bin/env bash

set -euo pipefail

echo "Validating Batch 9A visualization and admin access artifacts..."

python3 - <<'PY'
from pathlib import Path
import json
import sys

base = Path("contracts")
ownership = Path("contracts/visualization/SIGNAL_UI_OWNERSHIP.yaml")
if not ownership.exists():
    print("ERROR: SIGNAL_UI_OWNERSHIP.yaml is missing")
    sys.exit(1)

ui_contract = json.loads(
    (base / "visualization/UI_PROVISIONING_CONTRACT.json").read_text()
)
admin_smoke = json.loads(
    (base / "visualization/ADMIN_GUI_TLS_LOGIN_SMOKE_VALIDATION.json").read_text()
)
admin_schema = json.loads((base / "install/ADMIN_GUI_READINESS.schema.json").read_text())
admin_profile = json.loads(
    Path("install/profiles/admin-access/PROFILE.schema.json").read_text()
)

if ui_contract.get("validation_result", {}).get("status") != "pass":
    print("ERROR: UI provisioning contract validation must pass.")
    sys.exit(1)

if admin_smoke.get("validation_result", {}).get("status") != "pass":
    print("ERROR: Admin GUI smoke validation must pass.")
    sys.exit(1)

required_paths = set(ui_contract.get("required_paths", []))
if "gitops/platform/observability/grafana/provisioning" not in required_paths:
    print("ERROR: Grafana provisioning path must be declared.")
    sys.exit(1)

if admin_profile.get("title") != "Admin Access Profile":
    print("ERROR: Admin access profile schema title mismatch.")
    sys.exit(1)

if admin_schema.get("title") != "Admin GUI Readiness":
    print("ERROR: Admin GUI readiness schema title mismatch.")
    sys.exit(1)

for ui in admin_smoke.get("uis", []):
    if (
        not ui.get("endpoint_reachable")
        or not ui.get("tls_valid")
        or ui.get("login_smoke") != "pass"
    ):
        print(f"ERROR: Admin UI smoke failed for {ui.get('name')}")
        sys.exit(1)

print("Batch 9A visualization/admin checks passed.")
PY
