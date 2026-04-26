# scripts/ci/

Bespoke validation scripts that run in CI (`.github/workflows/ci.yaml`) and
in local pre-merge sanity loops. Cloud-agnostic: every script under this
directory runs against repository state alone — no cluster connection, no
GUI, no service IP. These are the scripts that PRs gate on.

## Conventions

- One script per validation concern.
- Each script uses `set -euo pipefail` and an inline Python heredoc
  (`python3 - <<'PY' ... PY`) for schema/JSON validation.
- Exit `0` on pass; non-zero on fail.
- No external test framework.

## Two top-level script directories — by design

The repository keeps two parallel script directories. Both are intentional;
neither replaces the other.

| Directory          | Scope                                       | Runs in CI? | Examples                                                          |
| ------------------ | ------------------------------------------- | ----------- | ----------------------------------------------------------------- |
| `scripts/ci/`      | Repository-only validators (this directory) | yes         | `validate_*` contract checks, `validate_*_smoke.sh` wrappers      |
| `scripts/validate/` | Live-runtime probes (cluster / GUI required) | no          | `admin_gui_smoke.sh`, `post_install_readiness.sh`                |

`scripts/validate/` exists for probes that only make sense against a
deployed instance (e.g., probing the admin GUI's TLS + login behavior).
Putting them in `scripts/ci/` would imply they should run in PR CI, which
they cannot — there is no admin GUI in the GitHub Actions runner.

The Batch 9A smoke wrapper is the one place where the two directories
intentionally cross: it runs the `scripts/ci/` contract validator and then
hands off to the `scripts/validate/` live-GUI probe. See
`validate_batch9a_smoke.sh` for the inline rationale.

## Adding a new validator

1. Decide whether the work is repository-only (`scripts/ci/`) or runtime
   (`scripts/validate/`).
2. For `scripts/ci/`, follow the conventions above.
3. Add a corresponding entry to `.github/workflows/ci.yaml` if the script
   should run on every PR, **or** to a smoke wrapper
   (`validate_batch<N>_smoke.sh`) if it belongs to a specific batch.
4. If the script is a new batch smoke wrapper, also add an entry to
   `validate_all_batches_with_report.sh` (BATCH_IDS / BATCH_NAMES /
   VALIDATION_CRITERIA / SCRIPT_PATHS).

## Permissions

Every `*.sh` file in this directory must have the executable bit set. A
preflight check `check_script_permissions.sh` enforces this — if you add a
new script and forget `chmod +x`, the preflight check will fail and surface
the offending path.

## Manual / on-demand entry points

Some scripts here are intentionally not wired into CI:

- `validate_all_batches_with_report.sh` — developer / QA tool that runs
  every batch smoke wrapper and writes a markdown + JSON report under
  `docs/reports/validation/`. CI runs the per-batch validators directly,
  so the report tool is redundant in CI.
- `snyk_code_scan_project.sh` — manual Snyk wrapper. Snyk requires an API
  token CI does not have; operators run this locally when triaging code
  scan findings.
- `teardown_python_env.sh` — counterpart to `setup_python_env.sh`; removes
  the local `.venv` and pip cache. Used when refreshing a stale local
  environment.
