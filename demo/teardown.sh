#!/usr/bin/env bash
# Tear down the Observability Kit demo playground (Batch 27, TR-27).
# Removes exactly what demo/deploy.sh created; the platform itself
# is untouched.
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

echo "Tearing down demo playground in context: $CONTEXT"
kubectl delete -k "$SCRIPT_DIR/gitops/base" --ignore-not-found=true
echo "Demo playground removed. The platform is unchanged."
