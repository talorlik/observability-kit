#!/usr/bin/env bash
#
# Live-runtime integration probe: run the obskit discovery executor
# end to end (preflight --live, discover --live, evaluate) against an
# EXISTING kind cluster.
#
# NEVER CI-gated. CI validation of the executor is offline and
# fixture-driven (scripts/ci/validate_discovery_executor.sh, TR-18);
# this probe needs a live kind cluster plus the obskit[k8s] extra, so
# it runs only on demand from a developer machine or an evidence
# harness. Do not wire it into .github/workflows/ci.yaml.
#
# Usage:
#
#   bash scripts/validate/discovery_executor_kind_integration.sh \
#     --context kind-<name> \
#     [--kubeconfig <path>] \
#     [--output-dir <dir>]
#
#   --context      required; must start with "kind-" (the context name
#                  kind generates). Any other context is refused so the
#                  probe can never touch a shared or cloud cluster.
#   --kubeconfig   kubeconfig path; defaults to $KUBECONFIG. One of the
#                  two must be set explicitly - the probe never falls
#                  back to ~/.kube/config implicitly.
#   --output-dir   report destination; defaults to
#                  docs/reports/discovery_executor_kind/<context>/.
#
# Prerequisites:
#   - an existing kind cluster (this probe never creates or mutates
#     clusters or any cluster state; the executor is read-only)
#   - the obskit k8s extra:  python3 -m pip install "./tools/obskit[k8s]"
#
# Exit code: non-zero on refusal or runtime error; otherwise the
# preflight outcome (0 = pass/warn, 1 = a blocking check failed). All
# reports are written either way.

set -euo pipefail

usage() {
  sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

CONTEXT=""
KUBECONFIG_PATH="${KUBECONFIG:-}"
OUTPUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --context)
      CONTEXT="${2:?--context needs a value}"
      shift 2
      ;;
    --kubeconfig)
      KUBECONFIG_PATH="${2:?--kubeconfig needs a value}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:?--output-dir needs a value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

echo "obskit kind integration probe (live-runtime, NEVER CI-gated;"
echo "CI runs the offline fixture suite in scripts/ci/ instead)."

if [[ -z "$CONTEXT" ]]; then
  echo "ERROR: --context is required (a kind-* kubeconfig context)." >&2
  usage >&2
  exit 2
fi

# Safety gate: kind names every context kind-<cluster>. Refusing
# anything else guarantees this probe cannot run against a shared or
# cloud cluster even with a permissive kubeconfig.
if [[ "$CONTEXT" != kind-* ]]; then
  echo "ERROR: refusing context '$CONTEXT': only contexts starting" >&2
  echo "with 'kind-' are allowed. This probe targets local kind" >&2
  echo "clusters exclusively and never shared or cloud clusters." >&2
  exit 2
fi

if [[ -z "$KUBECONFIG_PATH" ]]; then
  echo "ERROR: no kubeconfig given. Set KUBECONFIG or pass" >&2
  echo "--kubeconfig <path> explicitly; there is no implicit" >&2
  echo "~/.kube/config fallback." >&2
  exit 2
fi

if [[ ! -f "$KUBECONFIG_PATH" ]]; then
  echo "ERROR: kubeconfig not found: $KUBECONFIG_PATH" >&2
  exit 2
fi

export PYTHONPATH="tools/obskit${PYTHONPATH:+:$PYTHONPATH}"

if ! python3 -c "import kubernetes" >/dev/null 2>&1; then
  echo "ERROR: the obskit[k8s] extra is not installed; the live" >&2
  echo "reader needs the Kubernetes API client. Install it with:" >&2
  echo "  python3 -m pip install \"./tools/obskit[k8s]\"" >&2
  exit 2
fi

OUTPUT_DIR="${OUTPUT_DIR:-docs/reports/discovery_executor_kind/${CONTEXT}}"
mkdir -p "$OUTPUT_DIR"

echo "Target context: $CONTEXT (kubeconfig: $KUBECONFIG_PATH)"
echo "Writing reports to: $OUTPUT_DIR"

# Preflight may legitimately exit 1 when the cluster fails a blocking
# check; the probe still runs discovery and evaluation so the full
# evidence set is produced, then propagates the preflight outcome.
PREFLIGHT_RC=0
python3 -m obskit.cli preflight --live \
  --kubeconfig "$KUBECONFIG_PATH" \
  --context "$CONTEXT" \
  --output "$OUTPUT_DIR/preflight_report.json" || PREFLIGHT_RC=$?

if [[ ! -f "$OUTPUT_DIR/preflight_report.json" ]]; then
  echo "ERROR: preflight produced no report (exit $PREFLIGHT_RC)." >&2
  exit 1
fi

python3 -m obskit.cli discover --live \
  --kubeconfig "$KUBECONFIG_PATH" \
  --context "$CONTEXT" \
  --output "$OUTPUT_DIR/discovery_probes.json"

python3 -m obskit.cli evaluate \
  --preflight "$OUTPUT_DIR/preflight_report.json" \
  --discovery "$OUTPUT_DIR/discovery_probes.json" \
  --output-dir "$OUTPUT_DIR"

echo "Reports written to $OUTPUT_DIR:"
ls -1 "$OUTPUT_DIR"

if [[ "$PREFLIGHT_RC" -ne 0 ]]; then
  echo "Preflight reported a blocking failure (exit $PREFLIGHT_RC);"
  echo "see $OUTPUT_DIR/preflight_report.json and the remediation list."
  exit "$PREFLIGHT_RC"
fi

echo "Kind integration probe complete: preflight passed."
