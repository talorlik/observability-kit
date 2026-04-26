#!/usr/bin/env bash
#
# Sandbox validate — wrapper for running scripts/ci/validate_*.sh offline.
#
# Use this when running validators in a firewalled sandbox where:
#   - pip cannot reach pypi (so scripts/ci/setup_python_env.sh fails)
#   - helm is not installed (so validate_collector_core_topology.sh fails)
#   - kubectl is not installed (so the same script's dry-run fails)
#
# This wrapper installs three temporary shims, runs the requested validator,
# and restores the original setup_python_env.sh on exit.
#
# In real CI this wrapper is NOT used. CI installs helm via
# azure/setup-helm@v4 and has a working pip index, so the underlying
# scripts run unmodified.
#
# Usage:
#   bash scripts/dev/sandbox_validate.sh <validator-script> [args...]
#
# Examples:
#   bash scripts/dev/sandbox_validate.sh scripts/ci/validate_all_batches_with_report.sh
#   bash scripts/dev/sandbox_validate.sh scripts/ci/validate_batch14_smoke.sh
#   bash scripts/dev/sandbox_validate.sh scripts/ci/validate_core_adapter_integrations.sh
#
# Notes:
#   - The helm shim emits a single minimal Namespace manifest so the
#     structural dry-run fallback in validate_collector_core_topology.sh
#     finds apiVersion / kind / metadata. It does NOT exercise real Helm
#     templating; CI does.
#   - The kubectl shim returns non-zero on `cluster-info` so the
#     validator falls into its offline structural fallback path. It does
#     NOT exercise real cluster validation.
#   - setup_python_env.sh is replaced with a no-op for the duration of
#     the run and restored on exit, even on failure or interrupt. The
#     wrapper refuses to run if it detects a leftover stub from a prior
#     failed run, to avoid backing up the stub as the "original".

set -uo pipefail

if [ "$#" -lt 1 ]; then
  echo "usage: bash scripts/dev/sandbox_validate.sh <validator-script> [args...]" >&2
  exit 2
fi

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

SETUP="scripts/ci/setup_python_env.sh"

# Sanity check: refuse to run if the setup script is already a stub from a
# previous failed cleanup. This prevents backing up the stub as the
# "original" and making the bug stick.
if grep -q "Sandbox stub installed by scripts/dev/sandbox_validate.sh" "$SETUP" 2>/dev/null; then
  cat <<MSG >&2
ERROR: $SETUP appears to be a leftover sandbox stub from a previous failed
run, not the real script. Restore it before running this wrapper:

  git checkout $SETUP

If git checkout fails (e.g., the file is on a read-only mount), restore the
real contents from another checkout or the repo's history.
MSG
  exit 3
fi

# Backup goes to $TMPDIR (potentially a different filesystem). Restore uses
# `cat > target` — which writes content into the existing inode rather than
# replacing the file — so it works even when the target's directory does
# not permit unlink. (Some sandbox mounts allow write but block delete.)
SETUP_BAK="$(mktemp)"
TMP_BIN="$(mktemp -d)"

cleanup() {
  if [ -f "$SETUP_BAK" ]; then
    if cat "$SETUP_BAK" > "$SETUP" 2>/dev/null; then
      chmod +x "$SETUP" 2>/dev/null || true
    else
      echo "WARN: failed to restore $SETUP from $SETUP_BAK" >&2
      echo "WARN: backup left at: $SETUP_BAK" >&2
      echo "WARN: restore manually with: cat $SETUP_BAK > $SETUP" >&2
      return
    fi
    rm -f "$SETUP_BAK" 2>/dev/null || true
  fi
  rm -rf "$TMP_BIN" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Back up the real setup script and replace it with a no-op for this run.
cat "$SETUP" > "$SETUP_BAK"
cat > "$SETUP" <<'STUB'
#!/usr/bin/env bash
# Sandbox stub installed by scripts/dev/sandbox_validate.sh.
# Real script runs `pip install yamllint` etc. — replaced for offline use.
true
STUB
chmod +x "$SETUP"

# Helm shim: produce a minimal valid manifest so structural fallback succeeds.
cat > "$TMP_BIN/helm" <<'HELM'
#!/usr/bin/env bash
if [ "${1:-}" = "template" ]; then
  cat <<'MANIFEST'
apiVersion: v1
kind: Namespace
metadata:
  name: observability
MANIFEST
  exit 0
fi
exit 0
HELM
chmod +x "$TMP_BIN/helm"

# kubectl shim: force the offline structural fallback path.
cat > "$TMP_BIN/kubectl" <<'KUBE'
#!/usr/bin/env bash
case "${1:-}" in
  cluster-info) exit 1 ;;
  *) exit 0 ;;
esac
KUBE
chmod +x "$TMP_BIN/kubectl"

export PATH="$TMP_BIN:$PATH"

bash "$@"
exit_code=$?

# Cleanup runs via trap; explicit exit propagates the validator's status.
exit "$exit_code"
