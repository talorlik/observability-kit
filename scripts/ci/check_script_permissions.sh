#!/usr/bin/env bash
#
# Preflight: ensure every shell script in scripts/ci/ has the executable
# bit set. Catches drift early (a missing +x will cause CI to invoke the
# script via `bash <path>` which works, but violates the project
# convention documented in scripts/ci/README.md).
#
# Cloud-agnostic; runs against repository state only.

set -euo pipefail

echo "Checking that scripts/ci/*.sh all have +x..."

missing_x=()
while IFS= read -r -d '' f; do
  if [ ! -x "$f" ]; then
    missing_x+=("$f")
  fi
done < <(find scripts/ci -maxdepth 1 -type f -name "*.sh" -print0)

if [ ${#missing_x[@]} -gt 0 ]; then
  echo "ERROR: the following scripts are missing the executable bit (+x):"
  for path in "${missing_x[@]}"; do
    echo "  $path"
  done
  echo
  echo "Fix with: chmod +x ${missing_x[*]}"
  exit 1
fi

# Also check scripts/validate/ since it's part of the dual-directory layout
# documented in scripts/ci/README.md.
if [ -d scripts/validate ]; then
  while IFS= read -r -d '' f; do
    if [ ! -x "$f" ]; then
      missing_x+=("$f")
    fi
  done < <(find scripts/validate -maxdepth 1 -type f -name "*.sh" -print0)

  if [ ${#missing_x[@]} -gt 0 ]; then
    echo "ERROR: the following scripts are missing the executable bit (+x):"
    for path in "${missing_x[@]}"; do
      echo "  $path"
    done
    echo
    echo "Fix with: chmod +x ${missing_x[*]}"
    exit 1
  fi
fi

count=$(find scripts/ci scripts/validate -maxdepth 1 -type f -name "*.sh" 2>/dev/null | wc -l)
echo "Script-permission preflight passed (${count} scripts checked)."
