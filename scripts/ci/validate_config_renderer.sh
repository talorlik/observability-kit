#!/usr/bin/env bash
#
# Batch 19 validator: configuration rendering runtime (obskit render,
# obskit drift, obskit rollback).
#
# Repository-only and offline (TR-20 composed with TR-18: CI
# validation is fixture-driven; nothing here touches a live cluster or
# runs Git). Referenced as validated_by in
# contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml.
#
# Checks, in order:
#   1. structural checks on RENDERER_ARCHITECTURE_CONTRACT_V1.yaml
#      (metadata block bound to this validator and ADR-0003, the
#      obskit.configrender subpackage, extends_requirements_ci: false,
#      the CLI entrypoints, dry-run drill default) and ADR presence:
#      docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md records the
#      tools/obskit placement, lint-only requirements-ci.txt, and
#      GitOps-only propagation decisions - parsed line-based with the
#      Python stdlib so this step needs no venv, matching the
#      renderer's stdlib-only contract;
#   2. strategy catalog coverage: every (unified_key, system) binding
#      pair of contracts/management/samples/VALID_UNIFIED_CONFIG.json
#      has exactly one render_strategies catalog entry and vice versa,
#      loaded through the renderer's own facts module;
#   3. JSON twin fidelity: the YAML sample and its JSON twin are
#      semantically identical (venv PyYAML - a validator-side check
#      only; a grep asserts the renderer itself never imports yaml);
#   4. requirements-ci.txt cross-check: still lint-only (yamllint,
#      pymarkdownlnt) and tools/obskit/pyproject.toml still declares
#      no core dependencies - the renderer never extends either;
#   5. the offline renderer test suite under tests/configrender/, run
#      with PYTHONPATH=tools/obskit;
#   6. byte-identical re-render, generated-file header marker, render
#      manifest, and commit trailers through the real CLI against a
#      scratch copy of the fixture tree, then a clean drift run and a
#      seeded hand-edit surfacing render-idempotency-violation;
#   7. the rollback re-render drill in its dry-run default mode;
#   8. seeded rejection documents (unbound key, unknown system,
#      outside surface, traversal and out-of-surface render targets)
#      each fail `obskit render` with exit 2.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Validating config renderer (Batch 19)..."

python3 - <<'PY'
"""Structural checks on the renderer architecture contract and ADR."""
from pathlib import Path
import sys

CONTRACT = Path("contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml")
ADR = Path("docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md")

errors: list[str] = []

if not CONTRACT.is_file():
    print(f"ERROR: missing contract file: {CONTRACT}")
    sys.exit(1)

# Line-based parse (stdlib only): every fact below is a line the
# contract fixes verbatim, so drift is discoverable from either side.
required_lines = {
    # Metadata block: the contract must self-identify and bind to this
    # validator and its ADR.
    "contract: config-renderer-architecture": False,
    "version: v1": False,
    "decided_by: docs/adr/ADR_0003_CONFIG_RENDERER_ARCHITECTURE.md": False,
    "validated_by: scripts/ci/validate_config_renderer.sh": False,
    # Runtime boundaries: the renderer lives in obskit.configrender
    # and never extends the lint-only requirements-ci.txt.
    "subpackage: obskit.configrender": False,
    "extends_requirements_ci: false": False,
    # CLI entrypoints (render, its --check idempotency form, drift,
    # rollback).
    "command: obskit render": False,
    "command: obskit render --check": False,
    "command: obskit drift": False,
    "command: obskit rollback": False,
    # Rollback drill wrapper defaults to dry-run.
    "script: scripts/ops/run_config_rollback_drill.sh": False,
    "default_mode: dry-run": False,
}
for line in CONTRACT.read_text(encoding="utf-8").splitlines():
    stripped = line.strip()
    if stripped in required_lines:
        required_lines[stripped] = True
for key, seen in required_lines.items():
    if not seen:
        errors.append(f"contract missing line: {key}")

if not ADR.is_file():
    errors.append(f"missing ADR: {ADR}")
else:
    adr_text = ADR.read_text(encoding="utf-8")
    for needle, why in (
        ("tools/obskit/", "renderer placement decision"),
        ("requirements-ci.txt", "lint-only CI dependency decision"),
        ("GitOps-only", "GitOps-only propagation decision"),
    ):
        if needle not in adr_text:
            errors.append(f"ADR missing {why} ({needle!r})")

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)
print("Renderer architecture contract and ADR structural checks passed.")
PY

echo "Checking strategy catalog covers the sample bindings exactly..."
PYTHONPATH=tools/obskit python3 - <<'PY'
"""Every (unified_key, system) sample binding pair has exactly one
render_strategies catalog entry, and no catalog entry is an orphan.
Loaded through the renderer's own facts module so the check exercises
the same extraction path the render pipeline uses."""
import json
import sys
from pathlib import Path

from obskit.configrender.facts import load_strategy_catalog

catalog = load_strategy_catalog(
    Path("contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml")
)
sample = json.loads(
    Path("contracts/management/samples/VALID_UNIFIED_CONFIG.json")
    .read_text(encoding="utf-8")
)
sample_pairs = {
    (binding["unified_key"], binding["system"])
    for binding in sample["bindings"]
}
# load_strategy_catalog keys the catalog by (unified_key, system) and
# rejects duplicates itself, so set equality proves the one-to-one
# coverage in both directions.
catalog_pairs = set(catalog)

unbound = sorted(sample_pairs - catalog_pairs)
orphaned = sorted(catalog_pairs - sample_pairs)
if unbound:
    print(f"ERROR: sample binding pairs without a catalog entry: {unbound}")
if orphaned:
    print(f"ERROR: catalog entries no sample binding uses: {orphaned}")
if unbound or orphaned:
    sys.exit(1)
print(
    f"Strategy catalog and sample bindings agree on "
    f"{len(catalog_pairs)} (unified_key, system) pairs."
)
PY

echo "Checking the JSON twin matches the YAML sample..."
# Validator-side check only: the renderer stays stdlib-only, so the
# PyYAML comparison runs on the CI venv, never inside tools/obskit.
source scripts/ci/setup_python_env.sh
python - <<'PY'
"""VALID_UNIFIED_CONFIG.yaml and its JSON twin are semantically equal."""
import json
import sys
from pathlib import Path

import yaml

yaml_doc = yaml.safe_load(
    Path("contracts/management/samples/VALID_UNIFIED_CONFIG.yaml")
    .read_text(encoding="utf-8")
)
json_doc = json.loads(
    Path("contracts/management/samples/VALID_UNIFIED_CONFIG.json")
    .read_text(encoding="utf-8")
)
if yaml_doc != json_doc:
    print(
        "ERROR: contracts/management/samples/VALID_UNIFIED_CONFIG.json "
        "is not semantically identical to its YAML sample"
    )
    sys.exit(1)
print("YAML sample and JSON twin are semantically identical.")
PY

# The renderer itself must never import yaml (stdlib-only core).
if grep -rEn '^[[:space:]]*(import[[:space:]]+yaml|from[[:space:]]+yaml)\b' \
  tools/obskit/obskit/; then
  echo "ERROR: tools/obskit/obskit/ must stay stdlib-only (imports yaml)"
  exit 1
fi
echo "Renderer package imports no yaml (stdlib-only confirmed)."

python3 - <<'PY'
"""requirements-ci.txt must stay lint-only and the obskit package must
declare no core dependencies (TR-20 composed with TR-18)."""
from pathlib import Path
import sys

errors: list[str] = []

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
    errors.append(
        "requirements-ci.txt must stay lint-only; "
        f"unexpected entries: {unexpected}"
    )

# The core dependency list must stay empty; optional extras ([k8s])
# are allowed but never reach CI.
pyproject = Path("tools/obskit/pyproject.toml").read_text().splitlines()
if "dependencies = []" not in [line.strip() for line in pyproject]:
    errors.append(
        "tools/obskit/pyproject.toml must declare 'dependencies = []' "
        "(stdlib-only core)"
    )

if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)
print("requirements-ci.txt is lint-only and obskit declares no core deps.")
PY

echo "Running offline config renderer test suite..."
PYTHONPATH=tools/obskit python3 tests/configrender/test_render_core.py
PYTHONPATH=tools/obskit python3 tests/configrender/test_idempotency_and_drift.py
PYTHONPATH=tools/obskit python3 tests/configrender/test_rollback.py

echo "Running the real CLI end-to-end against a scratch fixture tree..."
scratch_dir="$(mktemp -d)"
trap 'rm -rf "${scratch_dir}"' EXIT

repo_dir="${scratch_dir}/repo"
cp -R tests/configrender/fixtures/repo "${repo_dir}"

document="tests/configrender/fixtures/document_valid.json"
marker_line="# GENERATED by the unified configuration renderer - DO NOT EDIT BY HAND."

run_render() {
  PYTHONPATH=tools/obskit python3 -m obskit render \
    --document "${document}" \
    --contracts-dir contracts \
    --repo-root "${repo_dir}" \
    --commit-message-out "${repo_dir}/COMMIT_MSG.txt" \
    "$@"
}

if ! run_render >/dev/null; then
  echo "ERROR: obskit render did not exit 0 on the fixture tree"
  exit 1
fi
# Byte-identical re-render: --check against the just-rendered tree
# must prove a no-diff, no-commit result (exit 0).
check_output="$(run_render --check)"
case "${check_output}" in
  *"no diff, no commit"*) ;;
  *)
    echo "ERROR: re-render --check did not report the no-diff line:"
    echo "${check_output}"
    exit 1
    ;;
esac
echo "Re-render --check proved no diff, no commit."

# Generated-file header marker is line one of rendered YAML targets.
for rendered in \
  "gitops/platform/observability/values/traces-pipeline.yaml" \
  "gitops/platform/observability/grafana/values/grafana-values.yaml"; do
  first_line="$(head -n 1 "${repo_dir}/${rendered}")"
  if [ "${first_line}" != "${marker_line}" ]; then
    echo "ERROR: rendered target missing header marker: ${rendered}"
    exit 1
  fi
done
echo "Rendered YAML targets carry the generated-file header marker."

# Render manifest exists and binds to the document digest.
python3 - "${repo_dir}" <<'PY'
"""The render manifest records the sha256-prefixed document digest."""
import json
import sys
from pathlib import Path

manifest_path = (
    Path(sys.argv[1]) / "gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json"
)
if not manifest_path.is_file():
    print(f"ERROR: missing render manifest: {manifest_path}")
    sys.exit(1)
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
digest = manifest.get("document_digest", "")
if not digest.startswith("sha256:"):
    print(f"ERROR: manifest document_digest is not sha256-prefixed: {digest!r}")
    sys.exit(1)
print("Render manifest present with sha256-prefixed document digest.")
PY

# Prepared commit message carries both required trailers from the
# propagation contract.
for trailer in \
  "Unified-Config-Schema-Version:" \
  "Unified-Config-Document-Digest: sha256:"; do
  if ! grep -q "^${trailer}" "${repo_dir}/COMMIT_MSG.txt"; then
    echo "ERROR: prepared commit message missing trailer: ${trailer}"
    exit 1
  fi
done
echo "Prepared commit message carries both required trailers."

run_drift() {
  PYTHONPATH=tools/obskit python3 -m obskit drift \
    --document "${document}" \
    --contracts-dir contracts \
    --repo-root "${repo_dir}"
}

echo "Checking drift is clean on the freshly rendered tree..."
if ! run_drift >/dev/null; then
  echo "ERROR: obskit drift did not exit 0 on a clean rendered tree"
  exit 1
fi

echo "Seeding a hand-edit and expecting render-idempotency-violation..."
printf '# hand-edit seeded by validate_config_renderer.sh\n' \
  >> "${repo_dir}/gitops/platform/observability/values/traces-pipeline.yaml"
drift_rc=0
drift_report="$(run_drift)" || drift_rc=$?
if [ "${drift_rc}" -ne 3 ]; then
  echo "ERROR: drift on a hand-edited tree exited ${drift_rc}, expected 3"
  exit 1
fi
case "${drift_report}" in
  *"render-idempotency-violation"*) ;;
  *)
    echo "ERROR: drift report missing render-idempotency-violation signal:"
    echo "${drift_report}"
    exit 1
    ;;
esac
echo "Hand-edit surfaced as render-idempotency-violation (exit 3)."

echo "Running the rollback re-render drill (dry-run default)..."
bash scripts/ops/run_config_rollback_drill.sh

echo "Checking seeded rejection documents fail with exit 2..."
for fixture in \
  "document_unbound_key.json" \
  "document_unknown_system.json" \
  "document_outside_surface.json" \
  "document_traversal_render_target.json" \
  "document_out_of_surface_render_target.json"; do
  reject_repo="${scratch_dir}/reject-$(basename "${fixture}" .json)"
  cp -R tests/configrender/fixtures/repo "${reject_repo}"
  reject_rc=0
  PYTHONPATH=tools/obskit python3 -m obskit render \
    --document "tests/configrender/fixtures/${fixture}" \
    --contracts-dir contracts \
    --repo-root "${reject_repo}" \
    --commit-message-out "${reject_repo}/COMMIT_MSG.txt" \
    >/dev/null 2>&1 || reject_rc=$?
  if [ "${reject_rc}" -ne 2 ]; then
    echo "ERROR: ${fixture} exited ${reject_rc}, expected 2"
    exit 1
  fi
  echo "rejected as expected: tests/configrender/fixtures/${fixture}"
done

echo "Config renderer validation passed."
