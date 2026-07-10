#!/usr/bin/env bash
#
# Rollback drill (Batch 8 Task 5; live path Batch 23, TR-12/TR-24).
#
# Modes:
#   dry-run (default)  simulate the drill steps; no cluster access.
#   live | real        execute a real GitOps revision rollback against
#                      a harness cluster: commit a config change to
#                      the GitOps repository, watch Argo CD converge,
#                      revert the commit, and verify the platform
#                      returns to the prior state. Requires:
#                        ROLLBACK_GITOPS_CLONE   GitOps working clone
#                        ROLLBACK_KUBECONFIG     isolated kubeconfig
#                        ROLLBACK_CONTEXT        kind-obskit-evidence
#                        ROLLBACK_APPLICATION    Argo CD app name
#                        ROLLBACK_PUBLISH_CMD    command republishing
#                                                the clone to the
#                                                git server
#                      Optional:
#                        DRILL_PAYLOAD_OUT       JSON evidence payload

set -euo pipefail

MODE="${1:-dry-run}"

echo "Running rollback drill (${MODE})..."

if [[ "$MODE" == "dry-run" ]]; then
  echo "Simulating GitOps revision rollback..."
  echo "Simulating exporter route rollback..."
  echo "Simulating post-rollback health verification..."
  echo "Rollback drill dry-run passed."
  exit 0
fi

if [[ "$MODE" != "live" && "$MODE" != "real" ]]; then
  echo "ERROR: unknown mode '${MODE}' (dry-run|live|real)." >&2
  exit 2
fi

: "${ROLLBACK_GITOPS_CLONE:?live rollback drill needs ROLLBACK_GITOPS_CLONE}"
: "${ROLLBACK_KUBECONFIG:?live rollback drill needs ROLLBACK_KUBECONFIG}"
: "${ROLLBACK_CONTEXT:?live rollback drill needs ROLLBACK_CONTEXT}"
: "${ROLLBACK_APPLICATION:?live rollback drill needs ROLLBACK_APPLICATION}"
: "${ROLLBACK_PUBLISH_CMD:?live rollback drill needs ROLLBACK_PUBLISH_CMD}"

if [[ "$ROLLBACK_CONTEXT" != kind-* ]]; then
  echo "ERROR: refusing context '$ROLLBACK_CONTEXT': live drills run" >&2
  echo "only against local kind harness contexts (kind-*)." >&2
  exit 2
fi

kc() {
  kubectl --kubeconfig "$ROLLBACK_KUBECONFIG" \
    --context "$ROLLBACK_CONTEXT" "$@"
}

app_field() {
  kc -n argocd get application "$ROLLBACK_APPLICATION" \
    -o jsonpath="$1"
}

wait_for_revision() {
  # $1 expected git revision, $2 expected ready gateway replicas
  local attempt revision replicas health
  revision=""
  health=""
  replicas=0
  for attempt in $(seq 1 60); do
    kc -n argocd annotate application "$ROLLBACK_APPLICATION" \
      argocd.argoproj.io/refresh=normal --overwrite >/dev/null 2>&1 \
      || true
    # Multi-source Application: revisions is an array (one entry per
    # source, same repo here); the singular field stays empty.
    revision="$(app_field '{.status.sync.revisions[0]}')"
    health="$(app_field '{.status.health.status}')"
    replicas="$(kc -n observability get deployment otel-gateway \
      -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo 0)"
    if [[ "$revision" == "$1" && "$health" == "Healthy" \
      && "$replicas" == "$2" ]]; then
      return 0
    fi
    sleep 10
  done
  echo "ERROR: application never converged to revision $1" >&2
  echo "(revision=$revision health=$health replicas=$replicas)" >&2
  return 1
}

OVERLAY="$ROLLBACK_GITOPS_CLONE/gitops/overlays/dev/platform-core-values.yaml"
if [[ ! -f "$OVERLAY" ]]; then
  echo "ERROR: no committed overlay at $OVERLAY." >&2
  exit 2
fi

STARTED_AT="$(date -u +%s)"
BASE_REVISION="$(git -C "$ROLLBACK_GITOPS_CLONE" rev-parse HEAD)"
BASE_REPLICAS="$(kc -n observability get deployment otel-gateway \
  -o jsonpath='{.spec.replicas}')"

echo "Committing forward config change (gateway replicas +1)..."
DRILL_REPLICAS=$((BASE_REPLICAS + 1))
# Structured edit: appending a second top-level collector key would
# leave a duplicate-key document that stricter parsers reject.
python3 - "$OVERLAY" "$DRILL_REPLICAS" <<'PY'
import sys

path, replicas = sys.argv[1], int(sys.argv[2])
with open(path) as handle:
    lines = handle.read().splitlines(keepends=True)
if any(line.startswith("collector:") for line in lines):
    raise SystemExit(
        "overlay already carries a collector block; refusing to "
        "guess a merge"
    )
lines.append(
    f"collector:\n  gateway:\n    replicas: {replicas}\n"
)
with open(path, "w") as handle:
    handle.writelines(lines)
PY
git -C "$ROLLBACK_GITOPS_CLONE" add gitops/overlays
git -C "$ROLLBACK_GITOPS_CLONE" \
  -c user.name="obskit-harness" \
  -c user.email="harness@observability-kit.local" \
  commit --quiet -m "drill: scale otel-gateway to ${DRILL_REPLICAS}"
FORWARD_REVISION="$(git -C "$ROLLBACK_GITOPS_CLONE" rev-parse HEAD)"
$ROLLBACK_PUBLISH_CMD

echo "Waiting for Argo CD to converge on the forward change..."
wait_for_revision "$FORWARD_REVISION" "$DRILL_REPLICAS"
FORWARD_AT="$(date -u +%s)"

echo "Rolling back: reverting the GitOps revision..."
git -C "$ROLLBACK_GITOPS_CLONE" \
  -c user.name="obskit-harness" \
  -c user.email="harness@observability-kit.local" \
  revert --no-edit HEAD >/dev/null
ROLLBACK_REVISION="$(git -C "$ROLLBACK_GITOPS_CLONE" rev-parse HEAD)"
$ROLLBACK_PUBLISH_CMD

echo "Waiting for Argo CD to converge on the rollback..."
wait_for_revision "$ROLLBACK_REVISION" "$BASE_REPLICAS"
FINISHED_AT="$(date -u +%s)"

if [[ -n "${DRILL_PAYLOAD_OUT:-}" ]]; then
  python3 - "$DRILL_PAYLOAD_OUT" <<PY
import json
import sys

payload = {
    "drill": "rollback",
    "mode": "$MODE",
    "application": "$ROLLBACK_APPLICATION",
    "base_revision": "$BASE_REVISION",
    "forward_revision": "$FORWARD_REVISION",
    "rollback_revision": "$ROLLBACK_REVISION",
    "base_gateway_replicas": $BASE_REPLICAS,
    "forward_gateway_replicas": $DRILL_REPLICAS,
    "forward_converge_seconds": $((FORWARD_AT - STARTED_AT)),
    "rollback_converge_seconds": $((FINISHED_AT - FORWARD_AT)),
    "steps": [
        "record base revision and gateway replica count",
        "commit forward overlay change (replicas +1)",
        "publish and wait for Synced/Healthy at forward revision",
        "git revert the forward commit (GitOps rollback)",
        "publish and wait for Synced/Healthy at rollback revision",
        "verify gateway replicas returned to base",
    ],
}
with open(sys.argv[1], "w") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
fi

echo "Rollback drill passed (GitOps revision rollback verified)."
