#!/usr/bin/env bash
#
# Batch 26 smoke wrapper: product documentation and GA readiness.
#
# Repository-only and offline: validates the docs/product/ tree, the
# INDEX.md audience map, the generated API reference freshness against
# the tenant control plane contract, the TR-26 docs-coverage matrix
# (every Batch 17-25 capability maps to a product doc section), the
# link and anchor integrity of the tree, and the signed GA readiness
# review WITHOUT a cluster, kind, or Docker. Nothing here deploys or
# probes a runtime; documentation is a release artifact with the same
# gating discipline as code (TR-26).

set -euo pipefail

echo "Running Batch 26 smoke validation (product docs, offline)..."

bash scripts/ci/validate_product_docs.sh

echo "Batch 26 smoke validation passed."
