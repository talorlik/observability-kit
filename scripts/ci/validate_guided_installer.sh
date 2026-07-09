#!/usr/bin/env bash
#
# Batch 18 validator: guided installation experience (obskit install).
#
# Repository-only and offline (TR-19 composed with TR-18: CI
# validation is fixture-driven; nothing here touches a live cluster).
# Referenced as validated_by in
# contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml.
#
# Checks, in order:
#   1. structural checks on INSTALL_FLOW_CONTRACT_V1.yaml (metadata
#      block bound to this validator and ADR-0002, the seven step ids
#      in exactly the contracted order) - parsed line-based with the
#      Python stdlib so the validator needs no venv, matching the
#      installer's stdlib-only contract;
#   2. ADR presence: docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md records
#      the tools/obskit placement and never-modify-wrapped-systems
#      decisions;
#   3. requirements-ci.txt cross-check: still lint-only (yamllint,
#      pymarkdownlnt) - the installer never extends it;
#   4. the offline installer test suite under tests/installer/, run
#      with PYTHONPATH=tools/obskit (wizard parity, schema rejection,
#      idempotent resume, byte-identical render, readiness
#      finalization);
#   5. seeded invalid-answers rejection through the real CLI: every
#      tests/installer/fixtures/answers_invalid_*.json must fail
#      `obskit install` with a non-zero exit and leave nothing
#      rendered.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Validating guided installer (Batch 18)..."

python3 - <<'PY'
"""Structural checks on the install flow contract and ADR."""
from pathlib import Path
import sys

CONTRACT = Path("contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml")
ADR = Path("docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md")

EXPECTED_STEPS = [
    "preflight",
    "grading",
    "mode-recommendation",
    "contract-capture",
    "render",
    "argocd-bootstrap",
    "post-install-readiness",
]

errors: list[str] = []

if not CONTRACT.is_file():
    print(f"ERROR: missing contract file: {CONTRACT}")
    sys.exit(1)
lines = CONTRACT.read_text(encoding="utf-8").splitlines()

# Metadata block: the contract must self-identify and bind to this
# validator and its ADR so drift is discoverable from either side.
required_metadata = {
    "contract: guided-install-flow": False,
    "version: v1": False,
    "decided_by: docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md": False,
    "validated_by: scripts/ci/validate_guided_installer.sh": False,
}
for line in lines:
    stripped = line.strip()
    if stripped in required_metadata:
        required_metadata[stripped] = True
for key, seen in required_metadata.items():
    if not seen:
        errors.append(f"contract metadata missing line: {key}")

# Step ids in exactly the contracted order, with ascending order
# values. Line-based parse: step id lines are '  - id: <step>' under
# the top-level 'steps:' key.
in_steps = False
found_steps: list[str] = []
found_orders: list[int] = []
for line in lines:
    if line.startswith("steps:"):
        in_steps = True
        continue
    if in_steps and line and not line.startswith((" ", "#")):
        in_steps = False
    if in_steps:
        stripped = line.strip()
        if stripped.startswith("- id: "):
            found_steps.append(stripped.removeprefix("- id: "))
        elif stripped.startswith("order: "):
            found_orders.append(int(stripped.removeprefix("order: ")))

if found_steps != EXPECTED_STEPS:
    errors.append(
        "contract steps are not the contracted sequence: "
        f"found {found_steps}"
    )
if found_orders != list(range(1, len(EXPECTED_STEPS) + 1)):
    errors.append(
        f"contract step order values are not exactly 1..7: "
        f"{found_orders}"
    )

if not ADR.is_file():
    errors.append(f"missing ADR: {ADR}")
else:
    adr_text = ADR.read_text(encoding="utf-8")
    for needle, why in (
        ("tools/obskit", "installer placement decision"),
        ("obskit install", "CLI entry point decision"),
        ("never forks or patches wrapped", "wrap-never-fork decision"),
        ("INSTALL_FLOW_CONTRACT_V1.yaml", "flow contract binding"),
    ):
        if needle not in adr_text:
            errors.append(f"ADR missing {why} ({needle!r})")

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)
print("Install flow contract and ADR structural checks passed.")
PY

python3 - <<'PY'
"""requirements-ci.txt must stay lint-only (TR-18/TR-19)."""
from pathlib import Path
import sys

allowed = {"yamllint", "pymarkdownlnt"}
names = set()
for line in Path("requirements-ci.txt").read_text().splitlines():
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        continue
    for sep in ("==", ">=", "<=", "~=", ">", "<"):
        if sep in stripped:
            stripped = stripped.split(sep, 1)[0]
            break
    names.add(stripped.strip())
unexpected = sorted(names - allowed)
if unexpected:
    print(
        "ERROR: requirements-ci.txt must stay lint-only; "
        f"unexpected entries: {unexpected}"
    )
    sys.exit(1)
print("requirements-ci.txt is still lint-only.")
PY

echo "Running offline installer test suite..."
PYTHONPATH=tools/obskit python3 tests/installer/test_install_wizard.py
PYTHONPATH=tools/obskit python3 tests/installer/test_render_step.py
PYTHONPATH=tools/obskit python3 tests/installer/test_finalize_step.py

echo "Checking seeded invalid-answers fixtures are rejected..."
snapshot_dir="$(mktemp -d)"
trap 'rm -rf "${snapshot_dir}"' EXIT
python3 - "${snapshot_dir}" <<'PY'
"""Build the non-blocked snapshot the installer tests use."""
import json
import sys
from pathlib import Path

base = json.loads(
    Path("tests/executor/fixtures/snapshot_preflight_pass.json")
    .read_text(encoding="utf-8")
)
reference = json.loads(
    Path("tests/executor/fixtures/snapshot_discovery_reference.json")
    .read_text(encoding="utf-8")
)
for key in (
    "crds",
    "storage_classes",
    "ingress_classes",
    "namespaces",
    "workloads",
    "services",
):
    base[key] = reference[key]
base["cluster"]["distribution"] = "kubeadm"
out = Path(sys.argv[1]) / "snapshot.json"
out.write_text(
    json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

found_any=false
for fixture in tests/installer/fixtures/answers_invalid_*.json; do
  # Guard against an unexpanded glob: without matches the loop body
  # would otherwise run once with the literal pattern and pass for
  # the wrong reason (obskit fails on the unreadable path).
  [ -f "${fixture}" ] || continue
  found_any=true
  out_dir="${snapshot_dir}/out-$(basename "${fixture}" .json)"
  if PYTHONPATH=tools/obskit python3 -m obskit install \
    --snapshot "${snapshot_dir}/snapshot.json" \
    --profiles tests/executor/fixtures/profiles_reference.json \
    --answers "${fixture}" \
    --output-dir "${out_dir}" \
    --repo-root . >/dev/null 2>&1; then
    echo "ERROR: seeded invalid answers accepted: ${fixture}"
    exit 1
  fi
  if [ -d "${out_dir}/rendered" ]; then
    echo "ERROR: invalid answers produced rendered output: ${fixture}"
    exit 1
  fi
  echo "rejected as expected: ${fixture}"
done
if [ "${found_any}" != "true" ]; then
  echo "ERROR: no seeded invalid-answers fixtures found"
  exit 1
fi

echo "Running the real CLI end-to-end with valid answers..."
e2e_dir="${snapshot_dir}/e2e"
run_install() {
  PYTHONPATH=tools/obskit python3 -m obskit install \
    --snapshot "${snapshot_dir}/snapshot.json" \
    --profiles tests/executor/fixtures/profiles_reference.json \
    --answers tests/installer/fixtures/answers_valid.json \
    --output-dir "${e2e_dir}" \
    --repo-root . >/dev/null
}
if ! run_install; then
  echo "ERROR: valid-answers install did not exit 0"
  exit 1
fi
for expected in \
  "install_summary.json" \
  "rendered/bootstrap/argocd/kustomization.yaml" \
  "rendered/bootstrap/argocd/platform-core-application.yaml"; do
  if [ ! -f "${e2e_dir}/${expected}" ]; then
    echo "ERROR: valid-answers install missing output: ${expected}"
    exit 1
  fi
done
# Overlay path depends on the fixture's environment answer.
if ! find "${e2e_dir}/rendered/overlays" -name \
  "platform-core-values.yaml" | grep -q .; then
  echo "ERROR: valid-answers install rendered no overlay"
  exit 1
fi
before="$(find "${e2e_dir}" -type f -exec shasum {} + | sort)"
if ! run_install; then
  echo "ERROR: idempotent re-run did not exit 0"
  exit 1
fi
after="$(find "${e2e_dir}" -type f -exec shasum {} + | sort)"
if [ "${before}" != "${after}" ]; then
  echo "ERROR: re-running a completed install changed files"
  exit 1
fi
echo "Real-CLI end-to-end and idempotent re-run passed."

echo "Guided installer validation passed."
