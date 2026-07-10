#!/usr/bin/env bash
#
# Validate a post-install readiness report against
# contracts/install/POST_INSTALL_READINESS.schema.json.
#
# Default report: the declared scaffold
# contracts/discovery/READINESS_REPORT_SCAFFOLD.json (dry-run-install).
# Batch 23: set READINESS_REPORT_PATH to validate a live readiness
# report captured from the evidence harness (live-install).

set -euo pipefail

READINESS_REPORT_PATH="${READINESS_REPORT_PATH:-contracts/discovery/READINESS_REPORT_SCAFFOLD.json}"
export READINESS_REPORT_PATH

echo "Validating post-install readiness report" \
  "(${READINESS_REPORT_PATH})..."

python3 - <<'PY'
import json
import os
from pathlib import Path
import sys

schema = json.loads(Path("contracts/install/POST_INSTALL_READINESS.schema.json").read_text())
report = json.loads(Path(os.environ["READINESS_REPORT_PATH"]).read_text())

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

allowed_emitted = set(
    schema["properties"]["metadata"]["properties"]["emitted_after"]["enum"]
)
if report["metadata"].get("emitted_after") not in allowed_emitted:
    print(
        "ERROR: readiness report emitted_after must be one of "
        f"{sorted(allowed_emitted)}"
    )
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
