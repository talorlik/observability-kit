#!/usr/bin/env bash

set -euo pipefail

echo "Running Batch 9A smoke validation bundle..."

bash scripts/ci/validate_visualization_admin_access.sh
bash scripts/validate/admin_gui_smoke.sh

echo "Batch 9A smoke validation bundle passed."
