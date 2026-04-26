#!/usr/bin/env bash

set -euo pipefail

echo "Checking for hard-coded environment overlay values..."

for path in gitops/overlays/*/platform-core-values.yaml; do
  [ -e "$path" ] || continue

  env_name="$(basename "$(dirname "$path")")"
  if [ "$env_name" = "base" ]; then
    continue
  fi

  if grep -nE "^[[:space:]]*environment:[[:space:]]*[A-Za-z0-9_-]+" "$path" \
    >/dev/null; then
    echo "Hard-coded environment value detected in $path"
    echo "Use generated overlays or templated values instead."
    exit 1
  fi
done

echo "No hard-coded environment values detected in overlays."
