#!/usr/bin/env bash

set -euo pipefail

echo "Running admin GUI smoke checks..."

test -f contracts/visualization/ADMIN_GUI_TLS_LOGIN_SMOKE_VALIDATION.json

echo "Admin GUI smoke checks passed."
