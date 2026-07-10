#!/usr/bin/env bash

set -euo pipefail

echo "Running admin GUI smoke checks..."

test -f contracts/visualization/ADMIN_GUI_TLS_LOGIN_SMOKE_VALIDATION.json

# Batch 21: the management portal is part of the admin GUI surface.
# The contract must exist in-repo; the live endpoint probe runs only
# when the operator supplies PORTAL_BASE_URL (hosts are environment
# data owned by the deployed admin-access profile - never hardcoded
# here).
test -f contracts/management/PORTAL_CONTRACT_V1.yaml

if [ -n "${PORTAL_BASE_URL:-}" ]; then
  echo "Probing portal liveness at PORTAL_BASE_URL/healthz..."
  # TLS verification stays ON by default (this is a TLS smoke);
  # set PORTAL_TLS_INSECURE=1 only for self-signed bootstrap probes.
  curl_opts="-fsS"
  if [ "${PORTAL_TLS_INSECURE:-0}" = "1" ]; then
    curl_opts="-fsSk"
  fi
  body="$(curl $curl_opts "$PORTAL_BASE_URL/healthz")"
  case "$body" in
    *'"status"'*)
      echo "Portal /healthz responded with a status payload."
      ;;
    *)
      echo "ERROR: portal /healthz response carries no \"status\" field"
      exit 1
      ;;
  esac
else
  echo "SKIP: PORTAL_BASE_URL not set; portal endpoint probe skipped."
fi

echo "Admin GUI smoke checks passed."
