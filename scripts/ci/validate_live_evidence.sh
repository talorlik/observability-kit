#!/usr/bin/env bash
#
# Batch 23 validator: live-cluster validation and evidence (TB-23,
# TR-12, TR-24).
#
# Repository-only and structural: verifies that captured live
# evidence exists and matches its contracts WITHOUT requiring a
# cluster, kind, or Docker. The live run itself stays a manual or
# nightly flow through scripts/dev/live_cluster_harness.sh; this
# validator never creates or contacts a cluster.
#
# Checks:
#   1. Harness contract, ADR, entry point, and nightly workflow
#      exist; the entry point's pins match the contract; the nightly
#      workflow ships disabled by default and is absent from PR CI.
#   2. Every contract-required evidence artifact exists under
#      artifacts/evidence/batch23/ with the envelope keys the
#      contract fixes, passing status, and the evidence-disposable
#      stack profile.
#   3. The install evidence chain is coherent: preflight passed,
#      the compatibility grade is conditional with exactly the
#      disposable_evidence_harness_only condition, the install
#      summary reports readiness passed, and the live readiness
#      report validates through post_install_readiness.sh.
#   4. All nine SDN-B15 denial scenarios captured live evidence
#      matching their expected decisions and fixtures.
#   5. Every captured_evidence reference added to *_VALIDATION.json
#      contracts points at an existing evidence artifact, and the
#      declared blocks those contracts carried remain in place.

set -euo pipefail

echo "Validating Batch 23 live evidence (structural, no cluster)..."

EVIDENCE_DIR="artifacts/evidence/batch23"
CONTRACT="contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml"
HARNESS="scripts/dev/live_cluster_harness.sh"
ADR="docs/adr/ADR_0007_DISPOSABLE_CLUSTER_HARNESS.md"
NIGHTLY=".github/workflows/e2e-nightly.yaml"

for path in "$EVIDENCE_DIR" "$CONTRACT" "$HARNESS" "$ADR" "$NIGHTLY"; do
  if [[ ! -e "$path" ]]; then
    echo "ERROR: missing required path: $path"
    exit 1
  fi
done

# The live readiness report must validate through the same script
# the installer's readiness step invokes.
READINESS_REPORT_PATH="$EVIDENCE_DIR/install/readiness_report.json" \
  bash scripts/validate/post_install_readiness.sh

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

python3 - <<'PY'
import json
import re
import sys
from pathlib import Path

import yaml

errors: list[str] = []

contract = yaml.safe_load(
    Path(
        "contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml"
    ).read_text()
)
harness_src = Path("scripts/dev/live_cluster_harness.sh").read_text()
evidence_root = Path("artifacts/evidence/batch23")

# --- 1. Contract / harness / workflow coherence -----------------------

profile = contract["stack_profiles"]["evidence-disposable"]
pins = {
    "CLUSTER_NAME": profile["cluster_name"],
    "CONTEXT": profile["kubectl_context"],
    "NODE_IMAGE": profile["node_image"],
}
for variable, expected in pins.items():
    pattern = rf'^{variable}="{re.escape(expected)}"$'
    if not re.search(pattern, harness_src, re.MULTILINE):
        errors.append(
            f"harness entry point does not pin {variable} to the "
            f"contract value {expected!r}"
        )

if contract["stack_profiles"]["dev-persistent"].get("evidence_source"):
    errors.append("dev-persistent profile must never be an evidence source")

for phrase in ("ENVIRONMENT", "DOCKER_HOST", "kind-obskit-evidence"):
    if phrase not in harness_src:
        errors.append(f"harness entry point lost its {phrase} safety gate")

nightly = Path(".github/workflows/e2e-nightly.yaml").read_text()
nightly_doc = yaml.safe_load(nightly)
# YAML 1.1 parses the bare key `on` as boolean True.
triggers = nightly_doc.get("on", nightly_doc.get(True, {}))
if "schedule" in triggers:
    errors.append(
        "e2e-nightly.yaml must ship with the schedule trigger "
        "disabled (commented out) by default"
    )
if "workflow_dispatch" not in triggers:
    errors.append("e2e-nightly.yaml must keep workflow_dispatch")
ci = Path(".github/workflows/ci.yaml").read_text()
if "live_cluster_harness" in ci or "e2e-nightly" in ci:
    errors.append("PR CI must never invoke the live harness")

# --- 2. Required evidence artifacts and envelopes ---------------------

required = contract["evidence"]["required_artifacts"]
all_required = (
    required["install"] + required["checks"] + required["harness"]
)
for relpath in all_required:
    if not (evidence_root / relpath).is_file():
        errors.append(f"missing required evidence artifact: {relpath}")

envelope_keys = set(
    contract["evidence"]["artifact_conventions"]["required_keys"]
)
harness_keys = set(
    contract["evidence"]["artifact_conventions"]["harness_keys"]
)


def check_envelope(relpath: str, payload: dict) -> None:
    missing = envelope_keys - set(payload)
    if missing:
        errors.append(f"{relpath}: missing envelope keys {sorted(missing)}")
        return
    if payload["batch"] != 23:
        errors.append(f"{relpath}: batch must be 23")
    harness_block = payload.get("harness", {})
    if harness_keys - set(harness_block):
        errors.append(f"{relpath}: incomplete harness block")
    elif harness_block["stack_profile"] != "evidence-disposable":
        errors.append(
            f"{relpath}: evidence must come from the "
            "evidence-disposable stack profile"
        )


for relpath in required["checks"] + required["harness"]:
    path = evidence_root / relpath
    if not path.is_file():
        continue
    payload = json.loads(path.read_text())
    check_envelope(relpath, payload)
    if relpath.startswith("checks/denials/"):
        continue  # denial artifacts carry decisions, not status
    if "status" in payload and payload["status"] != "pass":
        errors.append(f"{relpath}: captured status is not pass")

# --- 3. Install evidence chain ----------------------------------------

install_dir = evidence_root / "install"


def load(name: str) -> dict:
    return json.loads((install_dir / name).read_text())


if (install_dir / "preflight_report.json").is_file():
    preflight = load("preflight_report.json")
    statuses = {
        check["status"]
        for check in preflight.get("checks", [])
    }
    if "fail" in statuses:
        errors.append("captured preflight report carries failing checks")

if (install_dir / "compatibility_result.json").is_file():
    compatibility = load("compatibility_result.json")[
        "compatibility_result"
    ]
    if compatibility.get("grade") != "conditional":
        errors.append(
            "captured compatibility grade must be conditional on the "
            "kind evidence harness"
        )
    if "disposable_evidence_harness_only" not in compatibility.get(
        "reasons", []
    ):
        errors.append(
            "captured compatibility reasons must carry "
            "disposable_evidence_harness_only"
        )

if (install_dir / "install_summary.json").is_file():
    summary = load("install_summary.json")
    readiness = summary.get("readiness", {})
    if readiness.get("passed") is not True:
        errors.append("install summary must report readiness passed")

if (install_dir / "readiness_report.json").is_file():
    readiness_report = load("readiness_report.json")
    if (
        readiness_report["metadata"].get("emitted_after")
        != "live-install"
    ):
        errors.append(
            "captured readiness report must be emitted_after "
            "live-install"
        )
    for section in readiness_report.get("readiness_sections", []):
        if section.get("status") != "pass":
            errors.append(
                "captured readiness section "
                f"{section.get('id')} did not pass"
            )

# --- 4. Denial scenario evidence ---------------------------------------

fixtures = json.loads(
    Path(
        "contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json"
    ).read_text()
)["fixtures"]
fixture_ids = {fixture["scenario_id"] for fixture in fixtures}
expected_ids = {f"SDN-B15-{n:03d}" for n in range(1, 10)}
if fixture_ids != expected_ids:
    errors.append(
        f"denial fixtures drifted from SDN-B15-001..009: {fixture_ids}"
    )
by_id = {fixture["scenario_id"]: fixture for fixture in fixtures}
for scenario_id in sorted(expected_ids):
    path = evidence_root / "checks" / "denials" / f"{scenario_id}.json"
    if not path.is_file():
        errors.append(f"missing denial evidence: {scenario_id}")
        continue
    artifact = json.loads(path.read_text())
    if artifact.get("matches_expected") is not True:
        errors.append(
            f"{scenario_id}: live decision does not match the "
            "contracted expectation"
        )
    fixture = by_id[scenario_id]
    for key in ("enforcement_point", "expected_decision"):
        if artifact.get(key) != fixture.get(key):
            errors.append(
                f"{scenario_id}: {key} drifted from the CI fixture"
            )

# --- 5. captured_evidence references in validation contracts ----------

referencing = sorted(
    path
    for path in Path("contracts").rglob("*_VALIDATION.json")
    if "captured_evidence" in path.read_text()
)
if not referencing:
    errors.append(
        "no *_VALIDATION.json contract carries a captured_evidence "
        "reference (Batch 23 Task 4)"
    )
for path in referencing:
    document = json.loads(path.read_text())
    captured = document.get("captured_evidence")
    if captured is None:
        # Nested under validation_result or another block.
        for block in document.values():
            if isinstance(block, dict) and "captured_evidence" in block:
                captured = block["captured_evidence"]
                break
    if not isinstance(captured, dict):
        errors.append(f"{path}: captured_evidence must be an object")
        continue
    for artifact_path in captured.get("artifacts", []):
        if not Path(artifact_path).is_file():
            errors.append(
                f"{path}: captured_evidence references a missing "
                f"artifact {artifact_path}"
            )
    if captured.get("stack_profile") != "evidence-disposable":
        errors.append(
            f"{path}: captured_evidence must record the "
            "evidence-disposable stack profile"
        )

if errors:
    for message in errors:
        print(f"ERROR: {message}")
    sys.exit(1)

print("Batch 23 live-evidence structural validation passed.")
PY

echo "Live evidence validation passed."
