#!/usr/bin/env bash
#
# Disposable cluster harness: the single mode-parameterized entry point
# for Batch 23 live-cluster validation and evidence capture (TR-24).
#
# Contract: contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml
# Decision: docs/adr/ADR_0007_DISPOSABLE_CLUSTER_HARNESS.md
# Runbook:  docs/runbooks/LIVE_VALIDATION_RUNBOOK.md
#
# NEVER CI-gated on pull requests. Live runs are manual or nightly and
# orchestrator-owned. Repository CI validates the captured evidence
# structurally (scripts/ci/validate_live_evidence.sh) and never creates
# clusters.
#
# Usage:
#
#   bash scripts/dev/live_cluster_harness.sh create
#   bash scripts/dev/live_cluster_harness.sh run [--only <check-id>]
#   bash scripts/dev/live_cluster_harness.sh teardown
#   bash scripts/dev/live_cluster_harness.sh status
#
# Modes:
#   create    Create the disposable kind cluster (evidence-disposable
#             profile), provision the conformance baseline
#             (ingress-nginx, external-secrets, Argo CD, standard-rwo
#             StorageClass) and the attached backend (OpenSearch,
#             Dashboards, Neo4j enterprise eval, in-cluster git server).
#   run       Execute the evidence flow against the harness cluster:
#             installer end-to-end, live drills, GUI smoke, and the
#             SDN-B15 cross-tenant denial scenarios. Evidence is
#             written under artifacts/evidence/batch23/.
#             --only <check-id> re-runs a single check:
#             install | restore-drill | rollback-drill |
#             config-rollback-drill | gui-smoke | denials
#   teardown  Delete the kind cluster, verify deletion against kind
#             and Docker, record the teardown evidence artifact, and
#             remove the scratch kubeconfig.
#   status    Show harness provenance and live cluster state.
#
# Safety (layered, all mandatory - see the harness contract):
#   - refuses ENVIRONMENT=production
#   - refuses a remote DOCKER_HOST
#   - writes and uses an ISOLATED kubeconfig; never reads or writes
#     ~/.kube/config or the ambient KUBECONFIG
#   - operates only on the kind-obskit-evidence context recorded in
#     the provenance file of the same run

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

SCRATCH_DIR="$REPO_ROOT/.live-harness"
KUBECONFIG_FILE="$SCRATCH_DIR/kubeconfig"
PROVENANCE_FILE="$SCRATCH_DIR/provenance.json"
SECRETS_ENV="$SCRATCH_DIR/secrets.env"
VENV_DIR="$SCRATCH_DIR/venv"
GITOPS_CLONE="$SCRATCH_DIR/gitops-clone"
INSTALL_OUTPUT="$SCRATCH_DIR/install-output"
LOG_DIR="$SCRATCH_DIR/logs"
EVIDENCE_DIR="$REPO_ROOT/artifacts/evidence/batch23"
ASSETS_DIR="$REPO_ROOT/scripts/dev/harness_assets"

# evidence-disposable profile pins; keep in lockstep with
# contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml
# (validate_live_evidence.sh cross-checks these strings).
CLUSTER_NAME="obskit-evidence"
CONTEXT="kind-obskit-evidence"
NODE_IMAGE="kindest/node:v1.29.14"
STACK_PROFILE="evidence-disposable"
INGRESS_NGINX_MANIFEST="https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.1/deploy/static/provider/kind/deploy.yaml"
EXTERNAL_SECRETS_MANIFEST="https://github.com/external-secrets/external-secrets/releases/download/v0.14.4/external-secrets.yaml"
ARGOCD_MANIFEST="https://raw.githubusercontent.com/argoproj/argo-cd/v3.1.0/manifests/install.yaml"

BACKEND_NS="evidence-backend"
GITOPS_NS="evidence-gitops"
PLATFORM_NS="observability"
GIT_REPO_URL="https://git-server.${GITOPS_NS}.svc.cluster.local:8443/gitops.git"
PORTAL_PORT=8688
OPENSEARCH_LOCAL_PORT=19200

usage() {
  awk 'NR > 1 && !/^#/ { exit } NR > 1 { sub(/^# ?/, ""); print }' \
    "${BASH_SOURCE[0]}"
}

log() {
  echo "[harness $(date -u +%H:%M:%S)] $*"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

# ---------------------------------------------------------------------
# Safety gates
# ---------------------------------------------------------------------

safety_gates() {
  if [[ "${ENVIRONMENT:-}" == "production" ]]; then
    die "the disposable harness refuses to run with" \
      "ENVIRONMENT=production."
  fi
  if [[ -n "${DOCKER_HOST:-}" && "${DOCKER_HOST}" != unix://* ]]; then
    die "remote DOCKER_HOST '${DOCKER_HOST}' refused: the harness" \
      "operates only on the local Docker engine."
  fi
  local tool
  for tool in docker kind kubectl git python3 curl openssl; do
    command -v "$tool" >/dev/null || die "$tool not found on PATH."
  done
  docker info >/dev/null 2>&1 \
    || die "the local Docker engine is not reachable."
}

# Every cluster access goes through kc(): the isolated kubeconfig and
# the provenance-recorded context, never the ambient environment.
kc() {
  kubectl --kubeconfig "$KUBECONFIG_FILE" --context "$CONTEXT" "$@"
}

require_provenance() {
  [[ -f "$PROVENANCE_FILE" ]] \
    || die "no harness provenance at $PROVENANCE_FILE; run" \
      "'create' first."
  [[ -f "$KUBECONFIG_FILE" ]] \
    || die "no isolated kubeconfig at $KUBECONFIG_FILE; run" \
      "'create' first."
  local recorded
  recorded="$(python3 -c "
import json
print(json.load(open('$PROVENANCE_FILE'))['kubectl_context'])
")"
  [[ "$recorded" == "$CONTEXT" ]] \
    || die "provenance context '$recorded' is not '$CONTEXT';" \
      "refusing to operate on a context this harness did not create."
  kc get nodes >/dev/null \
    || die "harness cluster unreachable via the isolated kubeconfig."
}

# ---------------------------------------------------------------------
# create
# ---------------------------------------------------------------------

wait_rollout() {
  # $1 namespace, $2 kind/name, $3 timeout
  kc -n "$1" rollout status "$2" --timeout="${3:-300s}"
}

mode_create() {
  safety_gates
  if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
    die "cluster '$CLUSTER_NAME' already exists; a harness cluster" \
      "is never reused - run 'teardown' first."
  fi
  mkdir -p "$SCRATCH_DIR" "$LOG_DIR"

  log "creating kind cluster '$CLUSTER_NAME' ($NODE_IMAGE)"
  kind create cluster \
    --name "$CLUSTER_NAME" \
    --image "$NODE_IMAGE" \
    --config "$ASSETS_DIR/kind-cluster-config.yaml" \
    --kubeconfig "$KUBECONFIG_FILE" \
    --wait 180s

  local node_container
  node_container="$(docker ps \
    --filter "label=io.x-k8s.kind.cluster=$CLUSTER_NAME" \
    --format '{{.ID}}' | head -1)"

  python3 - "$PROVENANCE_FILE" "$KUBECONFIG_FILE" "$CONTEXT" \
    "$STACK_PROFILE" "$NODE_IMAGE" "$CLUSTER_NAME" \
    "$node_container" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone

(_, output, kubeconfig, context, stack_profile, node_image,
 cluster_name, node_container) = sys.argv
server_version = subprocess.run(
    ["kubectl", "--kubeconfig", kubeconfig,
     "--context", context, "version", "-o", "json"],
    capture_output=True, text=True, check=True).stdout
provenance = {
    "artifact_kind": "harness_provenance",
    "batch": 23,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "harness": {
        "stack_profile": stack_profile,
        "kubectl_context": context,
        "node_image": node_image,
    },
    "cluster_name": cluster_name,
    "kubectl_context": context,
    "node_image": node_image,
    "kind_node_container": node_container,
    "server_version": json.loads(server_version).get(
        "serverVersion", {}),
}
with open(output, "w") as handle:
    json.dump(provenance, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

  log "provisioning conformance baseline: storage class"
  kc apply -f "$ASSETS_DIR/storageclass-standard-rwo.yaml"

  log "provisioning conformance baseline: ingress-nginx"
  kc apply -f "$INGRESS_NGINX_MANIFEST"

  log "provisioning conformance baseline: external-secrets"
  # The upstream release manifest hardcodes its namespaced resources
  # into "default" (helm-templated release); apply it as released.
  # Discovery matches the secret integration by CRD suffix and
  # workload name, not namespace.
  kc apply --server-side -f "$EXTERNAL_SECRETS_MANIFEST"

  log "provisioning conformance baseline: Argo CD"
  kc create namespace argocd --dry-run=client -o yaml | kc apply -f -
  kc -n argocd apply --server-side -f "$ARGOCD_MANIFEST"

  log "waiting for baseline rollouts"
  wait_rollout ingress-nginx deployment/ingress-nginx-controller 600s
  wait_rollout default deployment/external-secrets 420s
  wait_rollout argocd deployment/argocd-repo-server 600s
  wait_rollout argocd statefulset/argocd-application-controller 600s

  log "generating per-run backend credentials"
  local opensearch_admin_password neo4j_password
  opensearch_admin_password="Ev1dence-$(openssl rand -hex 12)"
  neo4j_password="Ev1dence-$(openssl rand -hex 12)"
  {
    echo "OPENSEARCH_ADMIN_PASSWORD=$opensearch_admin_password"
    echo "NEO4J_PASSWORD=$neo4j_password"
  } > "$SECRETS_ENV"
  chmod 600 "$SECRETS_ENV"

  log "deploying attached backend (OpenSearch, Dashboards, Neo4j)"
  kc create namespace "$BACKEND_NS" --dry-run=client -o yaml \
    | kc apply -f -
  kc -n "$BACKEND_NS" create secret generic opensearch-admin \
    --from-literal=password="$opensearch_admin_password" \
    --dry-run=client -o yaml | kc apply -f -
  kc -n "$BACKEND_NS" create secret generic neo4j-auth \
    --from-literal=auth="neo4j/$neo4j_password" \
    --dry-run=client -o yaml | kc apply -f -
  kc apply -f "$ASSETS_DIR/backend-opensearch.yaml"
  kc apply -f "$ASSETS_DIR/backend-neo4j.yaml"

  log "deploying in-cluster git server (HTTPS, per-run cert)"
  kc create namespace "$GITOPS_NS" --dry-run=client -o yaml \
    | kc apply -f -
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$SCRATCH_DIR/git-server-key.pem" \
    -out "$SCRATCH_DIR/git-server-cert.pem" -days 2 \
    -subj "/CN=git-server.${GITOPS_NS}.svc.cluster.local" \
    >/dev/null 2>&1
  kc -n "$GITOPS_NS" create secret tls git-server-tls \
    --cert="$SCRATCH_DIR/git-server-cert.pem" \
    --key="$SCRATCH_DIR/git-server-key.pem" \
    --dry-run=client -o yaml | kc apply -f -
  kc -n "$GITOPS_NS" create configmap git-server-script \
    --from-file=git_smart_http.py="$ASSETS_DIR/git_smart_http.py" \
    --dry-run=client -o yaml | kc apply -f -
  kc apply -f "$ASSETS_DIR/gitserver.yaml"
  # Declarative Argo CD repository credential: TLS verification off
  # for the per-run self-signed certificate. Scoped to exactly the
  # harness repository URL.
  kc -n argocd apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: evidence-gitops-repo
  namespace: argocd
  labels:
    argocd.argoproj.io/secret-type: repository
stringData:
  type: git
  url: $GIT_REPO_URL
  insecure: "true"
EOF

  log "waiting for backend rollouts (image pulls may take minutes)"
  wait_rollout "$BACKEND_NS" deployment/opensearch 900s
  wait_rollout "$BACKEND_NS" deployment/opensearch-dashboards 900s
  wait_rollout "$BACKEND_NS" deployment/neo4j 900s
  wait_rollout "$GITOPS_NS" deployment/git-server 300s

  log "create complete. Next: bash $0 run"
}

# ---------------------------------------------------------------------
# run
# ---------------------------------------------------------------------

ensure_venv() {
  if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
    log "creating harness venv (obskit[k8s] + portal[api])"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet \
      "$REPO_ROOT/tools/obskit[k8s]" \
      "$REPO_ROOT/services/portal[api]" \
      "$REPO_ROOT/services/tenancy"
  fi
}

secrets() {
  [[ -f "$SECRETS_ENV" ]] || die "no $SECRETS_ENV; run 'create' first."
  # shellcheck source=/dev/null
  source "$SECRETS_ENV"
}

wrap_evidence() {
  # $1 artifact kind, $2 output path, $3 payload file (JSON),
  # $4 status (pass|fail), $5 check command string
  "$VENV_DIR/bin/python3" "$ASSETS_DIR/wrap_evidence.py" \
    --artifact-kind "$1" \
    --output "$2" \
    --payload "$3" \
    --status "$4" \
    --check-command "$5" \
    --stack-profile "$STACK_PROFILE" \
    --context "$CONTEXT" \
    --node-image "$NODE_IMAGE"
}

check_install() {
  log "check: install (guided installer end to end)"
  ensure_venv
  rm -rf "$INSTALL_OUTPUT" "$GITOPS_CLONE"
  mkdir -p "$INSTALL_OUTPUT" "$EVIDENCE_DIR/install"

  # 1. Non-interactive guided install against the live harness
  #    cluster. Answers and non-discoverable profiles are harness
  #    assets; the flow is preflight, grading, mode recommendation,
  #    contract capture, render, Argo CD bootstrap manifests, and
  #    post-install readiness (contracts/install/
  #    INSTALL_FLOW_CONTRACT_V1.yaml).
  "$VENV_DIR/bin/python3" -m obskit.cli install --live \
    --kubeconfig "$KUBECONFIG_FILE" \
    --context "$CONTEXT" \
    --cluster-name "$CLUSTER_NAME" \
    --answers "$ASSETS_DIR/install_answers.json" \
    --profiles "$ASSETS_DIR/install_profiles.json" \
    --output-dir "$INSTALL_OUTPUT" \
    --repo-root "$REPO_ROOT" \
    2>&1 | tee "$LOG_DIR/install.log"

  # 2. The two operator actions the install contract prescribes:
  #    commit rendered/ into the GitOps repository, apply the
  #    rendered bootstrap kustomization. The GitOps repository is a
  #    disposable clone of this repo served by the in-cluster git
  #    daemon; the platform arrives only through Argo CD.
  log "committing rendered output into the disposable GitOps clone"
  git clone --quiet --depth 1 "file://$REPO_ROOT" "$GITOPS_CLONE"
  # The rendered Application targets revision "main"; the clone
  # inherits whatever branch the source checkout is on, so pin it.
  git -C "$GITOPS_CLONE" checkout --quiet -B main
  cp "$INSTALL_OUTPUT/rendered/overlays/dev/platform-core-values.yaml" \
    "$GITOPS_CLONE/gitops/overlays/dev/platform-core-values.yaml"
  git -C "$GITOPS_CLONE" add gitops/overlays
  git -C "$GITOPS_CLONE" \
    -c user.name="obskit-harness" \
    -c user.email="harness@observability-kit.local" \
    commit --quiet -m "install: rendered overlay from obskit install"
  publish_gitops_clone

  log "applying the rendered Argo CD bootstrap kustomization"
  kc apply -k "$INSTALL_OUTPUT/rendered/bootstrap/argocd/"

  log "waiting for Argo CD to sync platform-core"
  local attempt sync health
  for attempt in $(seq 1 60); do
    sync="$(kc -n argocd get application platform-core \
      -o jsonpath='{.status.sync.status}' 2>/dev/null || true)"
    health="$(kc -n argocd get application platform-core \
      -o jsonpath='{.status.health.status}' 2>/dev/null || true)"
    if [[ "$sync" == "Synced" && "$health" == "Healthy" ]]; then
      break
    fi
    sleep 10
  done
  [[ "$sync" == "Synced" && "$health" == "Healthy" ]] \
    || die "platform-core Application never reached" \
      "Synced/Healthy (sync=$sync health=$health)."

  log "waiting for platform workloads"
  wait_rollout "$PLATFORM_NS" daemonset/otel-agent 600s
  wait_rollout "$PLATFORM_NS" deployment/otel-gateway 600s

  # 3. Live readiness report through the contracted readiness
  #    script, then evidence capture.
  log "building and validating the live readiness report"
  kc -n argocd get application platform-core -o json \
    > "$INSTALL_OUTPUT/argocd_application_state.json"
  "$VENV_DIR/bin/python3" "$ASSETS_DIR/build_readiness_report.py" \
    --kubeconfig "$KUBECONFIG_FILE" \
    --context "$CONTEXT" \
    --platform-namespace "$PLATFORM_NS" \
    --backend-namespace "$BACKEND_NS" \
    --application-state "$INSTALL_OUTPUT/argocd_application_state.json" \
    --output "$INSTALL_OUTPUT/readiness_report.json"
  READINESS_REPORT_PATH="$INSTALL_OUTPUT/readiness_report.json" \
    bash scripts/validate/post_install_readiness.sh

  local artifact
  for artifact in preflight_report discovery_probes \
    capability_matrix compatibility_result mode_recommendation \
    remediation_list install_summary readiness_report \
    argocd_application_state; do
    cp "$INSTALL_OUTPUT/$artifact.json" \
      "$EVIDENCE_DIR/install/$artifact.json"
  done
  "$VENV_DIR/bin/python3" "$ASSETS_DIR/wrap_evidence.py" \
    --artifact-kind live_install_evidence_manifest \
    --output "$EVIDENCE_DIR/install/evidence_manifest.json" \
    --payload-listing "$EVIDENCE_DIR/install" \
    --status pass \
    --check-command "obskit install --live (guided flow)" \
    --stack-profile "$STACK_PROFILE" \
    --context "$CONTEXT" \
    --node-image "$NODE_IMAGE"
  log "install evidence captured under $EVIDENCE_DIR/install/"
}

publish_gitops_clone() {
  # Serve the clone from the in-cluster git daemon: build a bare
  # repo, ship it into the git-server pod, verify with ls-remote.
  local bare="$SCRATCH_DIR/gitops.git" pod
  rm -rf "$bare"
  git clone --quiet --bare "$GITOPS_CLONE" "$bare"
  git -C "$bare" update-server-info
  touch "$bare/git-daemon-export-ok"
  kc -n "$GITOPS_NS" rollout status deployment/git-server \
    --timeout=180s >/dev/null
  pod="$(kc -n "$GITOPS_NS" get pods -l app=git-server \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}')"
  kc -n "$GITOPS_NS" exec "$pod" -- rm -rf /repos/gitops.git
  kc -n "$GITOPS_NS" cp "$bare" "$pod:/repos/gitops.git"
  local attempt served=false
  for attempt in $(seq 1 12); do
    # 127.0.0.1 explicitly: busybox wget resolves localhost to ::1
    # first and the server binds IPv4 only.
    if kc -n "$GITOPS_NS" exec "$pod" -- \
      wget -q --no-check-certificate -O /dev/null \
      https://127.0.0.1:8443/gitops.git/info/refs; then
      served=true
      break
    fi
    sleep 5
  done
  [[ "$served" == "true" ]] \
    || die "git server never served the published repository."
}

check_restore_drill() {
  log "check: restore drill (live OpenSearch snapshot/restore)"
  ensure_venv
  secrets
  mkdir -p "$EVIDENCE_DIR/checks"
  local payload="$LOG_DIR/restore_drill_payload.json" status=pass
  OPENSEARCH_NAMESPACE="$BACKEND_NS" \
    OPENSEARCH_ADMIN_PASSWORD="$OPENSEARCH_ADMIN_PASSWORD" \
    HARNESS_KUBECONFIG="$KUBECONFIG_FILE" \
    HARNESS_CONTEXT="$CONTEXT" \
    DRILL_PAYLOAD_OUT="$payload" \
    bash scripts/ops/run_restore_drill.sh live || status=fail
  wrap_evidence live_restore_drill \
    "$EVIDENCE_DIR/checks/restore_drill.json" "$payload" "$status" \
    "scripts/ops/run_restore_drill.sh live"
  [[ "$status" == "pass" ]]
}

check_rollback_drill() {
  log "check: rollback drill (live GitOps revision rollback)"
  ensure_venv
  mkdir -p "$EVIDENCE_DIR/checks"
  [[ -d "$GITOPS_CLONE/.git" ]] \
    || die "no GitOps clone; run the install check first."
  local payload="$LOG_DIR/rollback_drill_payload.json" status=pass
  ROLLBACK_GITOPS_CLONE="$GITOPS_CLONE" \
    ROLLBACK_KUBECONFIG="$KUBECONFIG_FILE" \
    ROLLBACK_CONTEXT="$CONTEXT" \
    ROLLBACK_APPLICATION="platform-core" \
    ROLLBACK_PUBLISH_CMD="$0 __publish-gitops" \
    DRILL_PAYLOAD_OUT="$payload" \
    bash scripts/ops/run_rollback_drill.sh live || status=fail
  wrap_evidence live_rollback_drill \
    "$EVIDENCE_DIR/checks/rollback_drill.json" "$payload" "$status" \
    "scripts/ops/run_rollback_drill.sh live"
  [[ "$status" == "pass" ]]
}

check_config_rollback_drill() {
  log "check: config rollback drill (renderer round-trip, real mode)"
  ensure_venv
  mkdir -p "$EVIDENCE_DIR/checks"
  local payload="$LOG_DIR/config_rollback_payload.json" status=pass
  local out="$LOG_DIR/config_rollback_drill.log"
  if PYTHONPATH="tools/obskit" \
    bash scripts/ops/run_config_rollback_drill.sh real > "$out" 2>&1
  then
    status=pass
  else
    status=fail
  fi
  python3 - "$out" "$payload" <<'PY'
import json
import sys

with open(sys.argv[1]) as handle:
    lines = handle.read().splitlines()
with open(sys.argv[2], "w") as handle:
    json.dump({"drill_output": lines}, handle, indent=2)
    handle.write("\n")
PY
  wrap_evidence live_config_rollback_drill \
    "$EVIDENCE_DIR/checks/config_rollback_drill.json" \
    "$payload" "$status" \
    "scripts/ops/run_config_rollback_drill.sh real"
  [[ "$status" == "pass" ]]
}

check_gui_smoke() {
  log "check: GUI smoke (live portal endpoint over TLS)"
  ensure_venv
  mkdir -p "$EVIDENCE_DIR/checks"
  local payload="$LOG_DIR/gui_smoke_payload.json" status=pass
  local cert="$SCRATCH_DIR/portal-cert.pem"
  local key="$SCRATCH_DIR/portal-key.pem"
  if [[ ! -f "$cert" ]]; then
    openssl req -x509 -newkey rsa:2048 -nodes \
      -keyout "$key" -out "$cert" -days 2 \
      -subj "/CN=127.0.0.1" >/dev/null 2>&1
  fi
  "$VENV_DIR/bin/python3" "$ASSETS_DIR/run_portal.py" \
    --port "$PORTAL_PORT" --certfile "$cert" --keyfile "$key" \
    > "$LOG_DIR/portal.log" 2>&1 &
  local portal_pid=$!
  # EXIT trap so the portal never leaks even when set -e aborts the
  # run mid-check; RETURN alone does not fire on an errexit abort.
  trap 'kill "$portal_pid" 2>/dev/null || true' RETURN EXIT
  local attempt ready=false
  for attempt in $(seq 1 30); do
    if curl -fsSk "https://127.0.0.1:$PORTAL_PORT/healthz" \
      >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  [[ "$ready" == "true" ]] \
    || die "portal never answered /healthz; see $LOG_DIR/portal.log"
  local healthz_file="$LOG_DIR/healthz_response.json"
  curl -fsSk "https://127.0.0.1:$PORTAL_PORT/healthz" \
    > "$healthz_file" || true
  local smoke_out="$LOG_DIR/gui_smoke.log"
  if PORTAL_BASE_URL="https://127.0.0.1:$PORTAL_PORT" \
    PORTAL_TLS_INSECURE=1 \
    bash scripts/validate/admin_gui_smoke.sh > "$smoke_out" 2>&1
  then
    status=pass
  else
    status=fail
  fi
  kill "$portal_pid" 2>/dev/null || true
  python3 - "$smoke_out" "$healthz_file" "$payload" <<'PY'
import json
import sys

with open(sys.argv[1]) as handle:
    lines = handle.read().splitlines()
with open(sys.argv[2]) as handle:
    healthz = json.load(handle)
with open(sys.argv[3], "w") as handle:
    json.dump({
        "smoke_output": lines,
        "healthz_response": healthz,
        "tls": "self-signed harness certificate, verification "
               "disabled via PORTAL_TLS_INSECURE=1",
    }, handle, indent=2)
    handle.write("\n")
PY
  wrap_evidence live_gui_smoke \
    "$EVIDENCE_DIR/checks/gui_smoke.json" "$payload" "$status" \
    "scripts/validate/admin_gui_smoke.sh (PORTAL_BASE_URL set)"
  [[ "$status" == "pass" ]]
}

check_denials() {
  log "check: cross-tenant denial scenarios SDN-B15-001..009"
  ensure_venv
  secrets
  mkdir -p "$EVIDENCE_DIR/checks/denials"
  local pf_pid
  kc -n "$BACKEND_NS" port-forward svc/opensearch \
    "$OPENSEARCH_LOCAL_PORT:9200" > "$LOG_DIR/port-forward.log" 2>&1 &
  pf_pid=$!
  # EXIT trap so the port-forward never leaks on an errexit abort.
  trap 'kill "$pf_pid" 2>/dev/null || true' RETURN EXIT
  local attempt reachable=false
  for attempt in $(seq 1 30); do
    if curl -fsk -u "admin:$OPENSEARCH_ADMIN_PASSWORD" \
      "https://127.0.0.1:$OPENSEARCH_LOCAL_PORT/_cluster/health" \
      >/dev/null 2>&1; then
      reachable=true
      break
    fi
    sleep 2
  done
  [[ "$reachable" == "true" ]] \
    || die "OpenSearch unreachable through the port-forward."
  "$VENV_DIR/bin/python3" "$ASSETS_DIR/run_denial_scenarios.py" \
    --opensearch-url "https://127.0.0.1:$OPENSEARCH_LOCAL_PORT" \
    --admin-password "$OPENSEARCH_ADMIN_PASSWORD" \
    --neo4j-password "$NEO4J_PASSWORD" \
    --kubeconfig "$KUBECONFIG_FILE" \
    --context "$CONTEXT" \
    --backend-namespace "$BACKEND_NS" \
    --matrix contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml \
    --fixtures \
    contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json \
    --output-dir "$EVIDENCE_DIR/checks/denials" \
    --stack-profile "$STACK_PROFILE" \
    --node-image "$NODE_IMAGE" \
    ${DENIAL_SCENARIO:+--scenario "$DENIAL_SCENARIO"}
  kill "$pf_pid" 2>/dev/null || true
  log "denial evidence captured under $EVIDENCE_DIR/checks/denials/"
}

mode_run() {
  safety_gates
  require_provenance
  mkdir -p "$LOG_DIR" "$EVIDENCE_DIR/harness"
  cp "$PROVENANCE_FILE" "$EVIDENCE_DIR/harness/provenance.json"

  local only=""
  if [[ "${1:-}" == "--only" ]]; then
    only="${2:?--only needs a check id}"
  fi

  case "$only" in
    "")
      check_install
      check_restore_drill
      check_rollback_drill
      check_config_rollback_drill
      check_gui_smoke
      check_denials
      log "run complete: all checks captured evidence."
      ;;
    install) check_install ;;
    restore-drill) check_restore_drill ;;
    rollback-drill) check_rollback_drill ;;
    config-rollback-drill) check_config_rollback_drill ;;
    gui-smoke) check_gui_smoke ;;
    denials) check_denials ;;
    *)
      die "unknown check id '$only'; valid: install," \
        "restore-drill, rollback-drill, config-rollback-drill," \
        "gui-smoke, denials."
      ;;
  esac
}

# ---------------------------------------------------------------------
# teardown
# ---------------------------------------------------------------------

mode_teardown() {
  safety_gates
  mkdir -p "$EVIDENCE_DIR/harness"

  local existed="false"
  if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
    existed="true"
    log "deleting kind cluster '$CLUSTER_NAME'"
    kind delete cluster --name "$CLUSTER_NAME" \
      --kubeconfig "$KUBECONFIG_FILE"
  else
    log "cluster '$CLUSTER_NAME' does not exist; verifying anyway"
  fi

  local kind_gone="true" docker_gone="true"
  kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME" \
    && kind_gone="false"
  [[ -n "$(docker ps -aq \
    --filter "label=io.x-k8s.kind.cluster=$CLUSTER_NAME")" ]] \
    && docker_gone="false"

  python3 - "$EVIDENCE_DIR/harness/teardown_verification.json" \
    "$STACK_PROFILE" "$CONTEXT" "$NODE_IMAGE" \
    "$existed" "$kind_gone" "$docker_gone" <<'PY'
import json
import sys
from datetime import datetime, timezone

(_, output, stack_profile, context, node_image,
 existed, kind_gone, docker_gone) = sys.argv
verification = {
    "artifact_kind": "harness_teardown_verification",
    "batch": 23,
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "harness": {
        "stack_profile": stack_profile,
        "kubectl_context": context,
        "node_image": node_image,
    },
    "cluster_existed_before_teardown": existed == "true",
    "kind_reports_cluster_absent": kind_gone == "true",
    "docker_reports_no_labeled_containers": docker_gone == "true",
}
with open(output, "w") as handle:
    json.dump(verification, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

  if [[ "$kind_gone" == "true" && "$docker_gone" == "true" ]]; then
    rm -f "$KUBECONFIG_FILE" "$PROVENANCE_FILE" "$SECRETS_ENV"
    log "teardown verified: cluster absent in kind and Docker."
  else
    die "teardown verification failed" \
      "(kind_gone=$kind_gone docker_gone=$docker_gone)."
  fi
}

# ---------------------------------------------------------------------
# status
# ---------------------------------------------------------------------

mode_status() {
  echo "harness scratch dir: $SCRATCH_DIR"
  if [[ -f "$PROVENANCE_FILE" ]]; then
    echo "provenance:"
    sed 's/^/  /' "$PROVENANCE_FILE"
  else
    echo "provenance: none (no create recorded)"
  fi
  echo "kind clusters:"
  kind get clusters 2>/dev/null | sed 's/^/  /' || true
  echo "docker containers labeled for '$CLUSTER_NAME':"
  docker ps --filter "label=io.x-k8s.kind.cluster=$CLUSTER_NAME" \
    --format '  {{.ID}} {{.Names}} {{.Status}}' || true
}

# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------

MODE="${1:-}"
shift || true

case "$MODE" in
  create) mode_create "$@" ;;
  run) mode_run "$@" ;;
  teardown) mode_teardown "$@" ;;
  status) mode_status "$@" ;;
  __publish-gitops)
    # Internal hook for the rollback drill: republish the GitOps
    # clone to the in-cluster git server after the drill commits.
    require_provenance
    publish_gitops_clone
    ;;
  -h|--help|help) usage ;;
  *)
    usage >&2
    die "unknown mode '${MODE:-<none>}'; valid: create, run," \
      "teardown, status."
    ;;
esac
