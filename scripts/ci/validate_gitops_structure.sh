#!/usr/bin/env bash

set -euo pipefail

required_paths=(
  "gitops/apps/platform-core-application.yaml"
  "gitops/charts/platform-core/Chart.yaml"
  "gitops/charts/platform-core/templates/namespace.yaml"
  "gitops/overlays/base/platform-core-values.yaml"
  "gitops/dashboards/README.md"
  "gitops/alerts/README.md"
  "gitops/README.md"
)

echo "Validating GitOps baseline structure..."
for path in "${required_paths[@]}"; do
  if [ ! -e "$path" ]; then
    echo "Missing required path: $path"
    exit 1
  fi
done

echo "GitOps baseline structure checks passed."
