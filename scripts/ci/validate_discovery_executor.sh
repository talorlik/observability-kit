#!/usr/bin/env bash
#
# Batch 17 validator: discovery and preflight execution engine (obskit).
#
# Repository-only and offline (TR-18: CI validation is fixture-driven;
# live-cluster integration lives in
# scripts/validate/discovery_executor_kind_integration.sh and is never
# CI-gated). Referenced as validated_by in
# contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml.
#
# Checks, in order:
#   1. structural checks on EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml
#      (metadata block, allowed_verbs exactly get/list/watch,
#      extends_requirements_ci false) - parsed line-based with the
#      Python stdlib so the validator needs no venv, matching the
#      executor's stdlib-only contract;
#   2. requirements-ci.txt cross-check: still lint-only (yamllint,
#      pymarkdownlnt) - the executor never extends it;
#   3. the offline fixture-driven executor test suite under
#      tests/executor/, run with PYTHONPATH=tools/obskit.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Validating discovery executor (Batch 17)..."

CONTRACT_PATH="contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml"

echo "Checking executor architecture contract structure..."

CONTRACT_PATH="$CONTRACT_PATH" python3 - <<'PY'
import os
import re
import sys
from pathlib import Path

path = Path(os.environ["CONTRACT_PATH"])
if not path.is_file():
    print(f"ERROR: missing contract file {path}")
    sys.exit(1)

lines = [
    line
    for line in path.read_text().splitlines()
    if line.strip() and not line.strip().startswith("#")
]
stripped = [line.strip() for line in lines]

errors: list[str] = []

# Metadata block: the contract must self-identify and bind to this
# validator so contract drift is discoverable from either side.
required_lines = {
    "contract: discovery-executor-architecture": "metadata.contract",
    "version: v1": "metadata.version",
    "owner: platform-observability": "metadata.owner",
    "validated_by: scripts/ci/validate_discovery_executor.sh":
        "metadata.validated_by",
    "decided_by: docs/adr/ADR_0001_DISCOVERY_EXECUTOR_ARCHITECTURE.md":
        "metadata.decided_by",
}
for expected, label in required_lines.items():
    if expected not in stripped:
        errors.append(f"{label}: expected line {expected!r} not found")

# allowed_verbs: exactly get, list, watch, in that order.
verbs: list[str] = []
collecting = False
for line in lines:
    if line.strip() == "allowed_verbs:":
        collecting = True
        continue
    if collecting:
        match = re.match(r"\s+-\s+(\S+)\s*$", line)
        if match:
            verbs.append(match.group(1))
        else:
            break
if verbs != ["get", "list", "watch"]:
    errors.append(
        f"cluster_access.allowed_verbs: expected [get, list, watch], "
        f"found {verbs}"
    )

# The executor owns its dependencies; requirements-ci.txt stays
# lint-only by contract.
if "extends_requirements_ci: false" not in stripped:
    errors.append(
        "runtime.extends_requirements_ci: expected 'false' not found"
    )

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)

print("Executor architecture contract structure OK.")
PY

echo "Cross-checking requirements-ci.txt stays lint-only..."

python3 - <<'PY'
import re
import sys
from pathlib import Path

allowed = {"yamllint", "pymarkdownlnt"}
found: list[str] = []
for line in Path("requirements-ci.txt").read_text().splitlines():
    entry = line.split("#", 1)[0].strip()
    if not entry:
        continue
    # Strip version specifiers and extras: name[extra]==1.2 -> name.
    name = re.split(r"[\[<>=!~; ]", entry, maxsplit=1)[0].lower()
    found.append(name)

unexpected = sorted(set(found) - allowed)
missing = sorted(allowed - set(found))
if unexpected:
    print(
        "ERROR: requirements-ci.txt must stay lint-only "
        f"(yamllint, pymarkdownlnt); unexpected entries: {unexpected}. "
        "The obskit executor owns its dependencies in "
        "tools/obskit/pyproject.toml (extends_requirements_ci: false)."
    )
    sys.exit(1)
if missing:
    print(f"ERROR: requirements-ci.txt lost lint deps: {missing}")
    sys.exit(1)

print("requirements-ci.txt is lint-only OK.")
PY

echo "Running offline fixture-driven executor tests..."

export PYTHONPATH=tools/obskit

python3 tests/executor/test_preflight_executor.py
python3 tests/executor/test_report_schema_conformance.py
python3 tests/executor/test_discovery_probes.py
python3 tests/executor/test_evaluate_artifacts.py
python3 tests/executor/test_determinism_and_boundaries.py

echo "Discovery executor validation passed."
