#!/usr/bin/env bash
#
# Config rollback drill (Batch 19 Task 4, TR-20).
#
# Proves the rollback contract offline: rollback is a re-render of a
# prior unified document revision through the identical render
# pipeline (`obskit rollback`), never a separate apply channel, and
# revert plus re-render reproduces the previously committed rendered
# bytes (digest-equality proof against the captured render manifest).
#
# Mode-parameterized per the scripts/ops conventions established by
# scripts/ops/run_rollback_drill.sh: dry-run (default) plans the
# rollback re-render without writing; real executes it and verifies
# the tree returns to the original rendered bytes. The drill only
# touches a scratch copy of the offline fixture tree - never a
# cluster, never Git history, never the repository's own gitops/.

set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-non-production}"
MODE="${1:-dry-run}"

if [[ "$MODE" != "dry-run" && "$MODE" != "real" ]]; then
  echo "ERROR: unknown mode '${MODE}' (expected dry-run or real)."
  exit 1
fi

# Real mode writes into its scratch tree only, but the ops convention
# stands: drills do not execute against production.
if [[ "$ENVIRONMENT" == "production" && "$MODE" == "real" ]]; then
  echo "ERROR: config rollback drill must not run in real mode in production."
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

# One CLI, one pipeline: the drill invokes obskit exactly as the
# offline tests do (PYTHONPATH, no install step, stdlib only).
obskit_cli() {
  PYTHONPATH="${REPO_ROOT}/tools/obskit" python3 -m obskit "$@"
}

PRIOR_DOCUMENT="${REPO_ROOT}/contracts/management/samples/VALID_UNIFIED_CONFIG.json"
CONTRACTS_DIR="${REPO_ROOT}/contracts"
DRILL_REPO="${SCRATCH}/repo"
REFERENCE_REPO="${SCRATCH}/reference"
PRIOR_MANIFEST="${SCRATCH}/prior_manifest.json"
MODIFIED_DOCUMENT="${SCRATCH}/modified_document.json"
ROLLBACK_REPORT="${DRILL_REPO}/rollback_report.json"

echo "Running config rollback drill in ${ENVIRONMENT} (${MODE})..."

echo "Preparing scratch copy of the offline fixture tree..."
cp -R "${REPO_ROOT}/tests/configrender/fixtures/repo" "${DRILL_REPO}"

echo "Rendering the prior unified document revision..."
obskit_cli render \
  --document "${PRIOR_DOCUMENT}" \
  --contracts-dir "${CONTRACTS_DIR}" \
  --repo-root "${DRILL_REPO}" \
  --commit-message-out "${DRILL_REPO}/COMMIT_MSG.txt" > /dev/null

echo "Capturing the prior render manifest and reference tree..."
cp "${DRILL_REPO}/gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json" \
  "${PRIOR_MANIFEST}"
cp -R "${DRILL_REPO}" "${REFERENCE_REPO}"

echo "Deriving and rendering a modified current document..."
python3 - "${PRIOR_DOCUMENT}" "${MODIFIED_DOCUMENT}" <<'PY'
import json
import sys

source, target = sys.argv[1], sys.argv[2]
with open(source, encoding="utf-8") as handle:
    document = json.load(handle)
# Simulate the intervening change that rollback undoes.
document["config"]["retention"]["logs_days"] = 7
with open(target, "w", encoding="utf-8") as handle:
    json.dump(document, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
obskit_cli render \
  --document "${MODIFIED_DOCUMENT}" \
  --contracts-dir "${CONTRACTS_DIR}" \
  --repo-root "${DRILL_REPO}" \
  --commit-message-out "${DRILL_REPO}/COMMIT_MSG.txt" > /dev/null

# Digest of every rendered byte under gitops/, for the dry-run proof
# that planning wrote nothing there (the rollback report itself lands
# at the scratch-repo root, outside this subtree).
tree_digest() {
  (cd "$1" && find gitops -type f -print0 | sort -z \
    | xargs -0 shasum -a 256 | shasum -a 256 | cut -d' ' -f1)
}

if [[ "$MODE" == "dry-run" ]]; then
  PRE_ROLLBACK_DIGEST="$(tree_digest "${DRILL_REPO}")"
  echo "Planning the rollback re-render (dry-run, nothing written)..."
  # No --mode flag on purpose: dry-run is the default mode of
  # `obskit rollback`, and the drill exercises that default.
  obskit_cli rollback \
    --document "${PRIOR_DOCUMENT}" \
    --contracts-dir "${CONTRACTS_DIR}" \
    --repo-root "${DRILL_REPO}" \
    --expected-manifest "${PRIOR_MANIFEST}" \
    --report-out "${ROLLBACK_REPORT}" > /dev/null
else
  echo "Executing the rollback re-render through the render pipeline..."
  obskit_cli rollback \
    --document "${PRIOR_DOCUMENT}" \
    --contracts-dir "${CONTRACTS_DIR}" \
    --repo-root "${DRILL_REPO}" \
    --mode real \
    --expected-manifest "${PRIOR_MANIFEST}" \
    --commit-message-out "${DRILL_REPO}/COMMIT_MSG.txt" \
    --report-out "${ROLLBACK_REPORT}" > /dev/null
fi

echo "Asserting the digest-equality proof..."
python3 - "${ROLLBACK_REPORT}" "${MODE}" <<'PY'
import json
import sys

report_path, mode = sys.argv[1], sys.argv[2]
with open(report_path, encoding="utf-8") as handle:
    report = json.load(handle)
assert report["deterministic_proof"] == "verified", report
assert report["mode"] == mode, report
expected_status = "planned" if mode == "dry-run" else "rolled-back"
assert report["status"] == expected_status, report
PY

if [[ "$MODE" == "dry-run" ]]; then
  echo "Verifying dry-run wrote nothing (tree digest unchanged)..."
  POST_ROLLBACK_DIGEST="$(tree_digest "${DRILL_REPO}")"
  if [[ "${PRE_ROLLBACK_DIGEST}" != "${POST_ROLLBACK_DIGEST}" ]]; then
    echo "ERROR: dry-run rollback modified the rendered tree."
    exit 1
  fi
  if diff -r -q "${REFERENCE_REPO}/gitops" "${DRILL_REPO}/gitops" \
    > /dev/null; then
    echo "ERROR: modified tree unexpectedly matches the reference."
    exit 1
  fi
  echo "Config rollback drill dry-run passed."
  exit 0
fi

echo "Verifying the tree returned to the original rendered bytes..."
diff -r "${REFERENCE_REPO}/gitops" "${DRILL_REPO}/gitops"
# Same-pipeline proof: the rollback commit message equals the commit
# message the original render of the prior document prepared.
diff "${REFERENCE_REPO}/COMMIT_MSG.txt" "${DRILL_REPO}/COMMIT_MSG.txt"
echo "Config rollback drill passed."
