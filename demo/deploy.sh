#!/usr/bin/env bash
# Deploy the Observability Kit demo playground (Batch 27, TR-27).
# Applies demo/gitops/base against the current kubeconfig context.
# Optional, additive, removable: nothing in the core platform is
# modified. Refuses to run against production.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${ENVIRONMENT:-}" == "production" ]]; then
  echo "ERROR: demo playground refuses ENVIRONMENT=production." >&2
  exit 1
fi

if ! command -v kubectl >/dev/null 2>&1; then
  echo "ERROR: kubectl is required on PATH." >&2
  exit 1
fi

CONTEXT="$(kubectl config current-context 2>/dev/null || true)"
if [[ -z "$CONTEXT" ]]; then
  echo "ERROR: no current kubeconfig context; set KUBECONFIG." >&2
  exit 1
fi

echo "Deploying demo playground to context: $CONTEXT"
kubectl apply -k "$SCRIPT_DIR/gitops/base"
echo "Demo playground deployed. Namespace: tenant-demo."
echo "Teardown: bash demo/teardown.sh"
