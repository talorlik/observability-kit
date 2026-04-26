#!/usr/bin/env bash

set -euo pipefail

echo "Validating post-install readiness report..."

python3 - <<'PY'
import json
from pathlib import Path
import sys

schema = json.loads(Path("contracts/install/POST_INSTALL_READINESS.schema.json").read_text())
report = json.loads(Path("contracts/discovery/READINESS_REPORT_SCAFFOLD.json").read_text())

required_top = set(schema.get("required", []))
missing_top = sorted(required_top - set(report.keys()))
if missing_top:
    print(f"ERROR: readiness report missing required top-level keys: {missing_top}")
    sys.exit(1)

meta_rules = schema["properties"]["metadata"]["required"]
missing_meta = sorted(set(meta_rules) - set(report.get("metadata", {}).keys()))
if missing_meta:
    print(f"ERROR: readiness report metadata missing keys: {missing_meta}")
    sys.exit(1)

if report["metadata"].get("emitted_after") != "dry-run-install":
    print("ERROR: readiness report emitted_after must be dry-run-install")
    sys.exit(1)

sections = report.get("readiness_sections", [])
if len(sections) < 3:
    print("ERROR: readiness report requires at least three readiness sections")
    sys.exit(1)

allowed = {"pending", "pass", "fail"}
for section in sections:
    for key in ("id", "description", "status"):
        if key not in section:
            print(f"ERROR: readiness section missing key: {key}")
            sys.exit(1)
    if section["status"] not in allowed:
        print(f"ERROR: invalid readiness status: {section['status']}")
        sys.exit(1)

print("Post-install readiness validation passed.")
PY
