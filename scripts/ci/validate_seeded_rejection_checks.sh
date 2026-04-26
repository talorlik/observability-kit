#!/usr/bin/env bash

set -euo pipefail

# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

workdir="$(mktemp -d)"
trap 'rm -rf "$workdir"' EXIT

invalid_yaml="$workdir/invalid.yaml"
cat >"$invalid_yaml" <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: seeded-invalid-yaml
data:
  broken: [unclosed
EOF

echo "Checking seeded invalid YAML rejection..."
if yamllint "$invalid_yaml" >/dev/null 2>&1; then
  echo "Expected seeded invalid YAML to fail lint, but it passed."
  exit 1
fi

seeded_secret="$workdir/seeded-secret.txt"
cat >"$seeded_secret" <<'EOF'
-----BEGIN PRIVATE KEY-----
MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQC7fAKEq4jR3owV
mW0vXfGQ2YQz6I5y2gX5G+ob2hQwS4j8z62r4cQhxt8z8fC7aI9YF7fJQ4xV4T6x
yl4QF8m8WzWm+4rK2lqN4l7fD3r3uA0rEoGv7u2n7rA8mV6Yl5Q0m5eM2jP1yW3X
uQIDAQABAoIBAQCPy8Qx4v2xQ9fXwzX7Q2kE9vN7R9k6M4JcB8mQkL2oA8rYz2vC
-----END PRIVATE KEY-----
EOF

echo "Checking seeded secret rejection behavior with gitleaks..."
if docker run --rm -v "$workdir:/repo" zricethezav/gitleaks:latest \
  detect --source=/repo --no-git --verbose >/dev/null 2>&1; then
  echo "Expected seeded secret scan to fail, but it passed."
  exit 1
fi

echo "Seeded rejection checks passed."
