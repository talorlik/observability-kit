#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Running YAML lint with yamllint..."
yamllint .
