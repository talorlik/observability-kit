#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Running Helm render checks for stub charts..."
helm template platform-core gitops/charts/platform-core >/dev/null

echo "Checking optional kustomize stubs when present..."
python3 - <<'PY'
from pathlib import Path
import subprocess
import shutil
import sys

kustomizations = sorted(Path("gitops").rglob("kustomization.yaml"))
if not kustomizations:
    print("No kustomization.yaml stubs found under gitops/.")
    sys.exit(0)

if shutil.which("kustomize") is None:
    print("kustomize binary not found; skipping kustomize stub renders.")
    sys.exit(0)

for path in kustomizations:
    target_dir = path.parent
    print(f"Rendering {target_dir}...")
    subprocess.run(
        ["kustomize", "build", str(target_dir)],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

print("All kustomization stubs rendered successfully.")
PY

echo "Stub render checks passed."
