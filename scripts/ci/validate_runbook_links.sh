#!/usr/bin/env bash

set -euo pipefail

required_docs=(
  "docs/runbooks/INSTALL_RUNBOOK.md"
  "docs/runbooks/VALIDATION_RUNBOOK.md"
  "docs/runbooks/ROLLBACK_RUNBOOK.md"
  "docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md"
  "docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md"
)

echo "Checking baseline runbook files..."
for path in "${required_docs[@]}"; do
  if [ ! -f "$path" ]; then
    echo "Missing runbook: $path"
    exit 1
  fi
done

echo "Checking runbook links in README..."
python3 - <<'PY'
from pathlib import Path
import sys

required = [
    "docs/runbooks/INSTALL_RUNBOOK.md",
    "docs/runbooks/VALIDATION_RUNBOOK.md",
    "docs/runbooks/ROLLBACK_RUNBOOK.md",
    "docs/runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md",
    "docs/runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md",
]

content = Path("README.md").read_text()
for path in required:
    if path not in content:
        print(f"README is missing runbook link: {path}")
        sys.exit(1)
PY

echo "Runbook baseline checks passed."
