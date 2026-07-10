#!/usr/bin/env bash
#
# Restore drill (Batch 8 Task 4; live path Batch 23, TR-12/TR-24).
#
# Modes:
#   dry-run (default)  simulate the drill steps; no cluster access.
#   live | real        execute a real OpenSearch snapshot/restore
#                      cycle against a harness cluster. Requires:
#                        OPENSEARCH_NAMESPACE   backend namespace
#                        HARNESS_KUBECONFIG     isolated kubeconfig
#                        HARNESS_CONTEXT        kind-obskit-evidence
#                      Optional:
#                        DRILL_PAYLOAD_OUT      JSON evidence payload
#                      The live path runs inside the OpenSearch pod
#                      (kubectl exec + curl with the pod's own admin
#                      credentials); it fails loudly when the harness
#                      context is missing rather than simulating.
#
# Refuses ENVIRONMENT=production in every mode.

set -euo pipefail

ENVIRONMENT="${ENVIRONMENT:-non-production}"
MODE="${1:-dry-run}"

if [[ "$ENVIRONMENT" == "production" ]]; then
  echo "ERROR: restore drill must not run in production."
  exit 1
fi

echo "Running restore drill in ${ENVIRONMENT} (${MODE})..."

if [[ "$MODE" == "dry-run" ]]; then
  echo "Simulating snapshot repository check..."
  echo "Simulating restore command execution..."
  echo "Simulating post-restore index health check..."
  echo "Restore drill dry-run passed."
  exit 0
fi

if [[ "$MODE" != "live" && "$MODE" != "real" ]]; then
  echo "ERROR: unknown mode '${MODE}' (dry-run|live)." >&2
  exit 2
fi

: "${OPENSEARCH_NAMESPACE:?live restore drill needs OPENSEARCH_NAMESPACE}"
: "${HARNESS_KUBECONFIG:?live restore drill needs HARNESS_KUBECONFIG}"
: "${HARNESS_CONTEXT:?live restore drill needs HARNESS_CONTEXT}"

if [[ "$HARNESS_CONTEXT" != kind-* ]]; then
  echo "ERROR: refusing context '$HARNESS_CONTEXT': live drills run" >&2
  echo "only against local kind harness contexts (kind-*)." >&2
  exit 2
fi

osx() {
  # One authenticated curl inside the OpenSearch pod. The pod's own
  # OPENSEARCH_INITIAL_ADMIN_PASSWORD provides credentials; nothing
  # secret crosses this script's arguments or environment.
  local method="$1" path="$2" body="${3:-}"
  local curl_cmd
  curl_cmd='curl -sk -u "admin:${OPENSEARCH_INITIAL_ADMIN_PASSWORD}"'
  curl_cmd+=" -X $method \"https://localhost:9200$path\""
  if [[ -n "$body" ]]; then
    curl_cmd+=" -H 'content-type: application/json'"
    curl_cmd+=" -d '$body'"
  fi
  kubectl --kubeconfig "$HARNESS_KUBECONFIG" \
    --context "$HARNESS_CONTEXT" \
    -n "$OPENSEARCH_NAMESPACE" exec deploy/opensearch -- \
    bash -c "$curl_cmd"
}

DRILL_INDEX="evidence-restore-drill"
REPO_NAME="evidence-fs-repo"
SNAPSHOT_NAME="restore-drill-snapshot"
STARTED_AT="$(date -u +%s)"

echo "Registering filesystem snapshot repository..."
osx PUT "/_snapshot/${REPO_NAME}" \
  '{"type":"fs","settings":{"location":"/usr/share/opensearch/snapshots/'"$REPO_NAME"'"}}' \
  | grep -q '"acknowledged":true'

echo "Seeding drill index with reference documents..."
osx PUT "/${DRILL_INDEX}/_doc/1?refresh=true" \
  '{"drill":"restore","doc":1}' >/dev/null
osx PUT "/${DRILL_INDEX}/_doc/2?refresh=true" \
  '{"drill":"restore","doc":2}' >/dev/null
osx PUT "/${DRILL_INDEX}/_doc/3?refresh=true" \
  '{"drill":"restore","doc":3}' >/dev/null

echo "Creating snapshot..."
osx PUT "/_snapshot/${REPO_NAME}/${SNAPSHOT_NAME}?wait_for_completion=true" \
  '{"indices":"'"$DRILL_INDEX"'"}' | grep -q '"state":"SUCCESS"'

echo "Deleting drill index (simulated data loss)..."
osx DELETE "/${DRILL_INDEX}" | grep -q '"acknowledged":true'

echo "Restoring from snapshot..."
osx POST "/_snapshot/${REPO_NAME}/${SNAPSHOT_NAME}/_restore?wait_for_completion=true" \
  '{"indices":"'"$DRILL_INDEX"'"}' >/dev/null

echo "Verifying restored document count..."
COUNT_JSON="$(osx GET "/${DRILL_INDEX}/_count?q=*")"
echo "$COUNT_JSON" | grep -q '"count":3' || {
  echo "ERROR: restored index count mismatch: $COUNT_JSON" >&2
  exit 1
}

echo "Cleaning up drill artifacts..."
osx DELETE "/${DRILL_INDEX}" >/dev/null
osx DELETE "/_snapshot/${REPO_NAME}/${SNAPSHOT_NAME}" >/dev/null

FINISHED_AT="$(date -u +%s)"
ELAPSED=$((FINISHED_AT - STARTED_AT))

if [[ -n "${DRILL_PAYLOAD_OUT:-}" ]]; then
  python3 - "$DRILL_PAYLOAD_OUT" <<PY
import json
import sys

payload = {
    "drill": "restore",
    "environment": "$ENVIRONMENT",
    "mode": "$MODE",
    "snapshot_repository": "$REPO_NAME (filesystem, in-cluster)",
    "snapshot": "$SNAPSHOT_NAME",
    "index": "$DRILL_INDEX",
    "documents_seeded": 3,
    "documents_restored": 3,
    "restore_cycle_seconds": $ELAPSED,
    "steps": [
        "register filesystem snapshot repository",
        "seed drill index (3 documents)",
        "snapshot (wait_for_completion)",
        "delete index (simulated data loss)",
        "restore from snapshot (wait_for_completion)",
        "verify document count == 3",
        "clean up drill index and snapshot",
    ],
}
with open(sys.argv[1], "w") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
fi

echo "Restore drill passed in ${ELAPSED}s (live snapshot/restore)."
