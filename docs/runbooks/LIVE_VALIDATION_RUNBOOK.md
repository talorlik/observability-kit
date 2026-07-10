# Live Validation Runbook

Operate the Batch 23 disposable cluster harness: create the evidence
cluster, capture live evidence, re-run a single check, and verify
teardown. Contract:
`contracts/evidence/DISPOSABLE_CLUSTER_HARNESS_CONTRACT_V1.yaml`
(TR-24); decision record:
`docs/adr/ADR_0007_DISPOSABLE_CLUSTER_HARNESS.md`.

## Scope

- The `evidence-disposable` stack profile: a kind cluster named
  `obskit-evidence` on the local Docker engine (OrbStack), created
  per run and destroyed after evidence capture. The only profile
  live evidence may come from.
- The `dev-persistent` stack profile: the OrbStack built-in
  Kubernetes cluster with the dev overlay, for day-to-day iteration.
  Never an evidence source; the harness refuses its context.
- Live runs are manual or nightly and orchestrator-owned. Nothing
  here gates pull requests; repository CI validates captured
  evidence structurally via `scripts/ci/validate_live_evidence.sh`.

## Pre-Checks

1. Local Docker engine reachable (`docker info`); the harness
   refuses a remote `DOCKER_HOST`.
2. `kind`, `kubectl`, `git`, `python3`, and `openssl` on PATH.
3. `ENVIRONMENT` is not `production`; the harness refuses it.
4. Roughly 12 GiB of memory headroom on the Docker engine (the
   harness contract's sizing bound) and network access for pinned
   upstream image pulls.
5. No leftover harness cluster:
   `bash scripts/dev/live_cluster_harness.sh status` shows no
   `obskit-evidence` cluster. A harness cluster is never reused; if
   one exists, tear it down first.

## Procedure

### Harness Lifecycle

```bash
bash scripts/dev/live_cluster_harness.sh create
bash scripts/dev/live_cluster_harness.sh run
bash scripts/dev/live_cluster_harness.sh teardown
```

`create` provisions the kind cluster (pinned
`kindest/node:v1.29.14`), the conformance baseline (ingress-nginx,
external-secrets, Argo CD, the `standard-rwo` StorageClass), the
attached backend (OpenSearch and Dashboards 2.19.1 with the security
plugin, Neo4j Enterprise under evaluation acceptance), and the
in-cluster git server. It writes the isolated kubeconfig and the
provenance file under `.live-harness/`; the harness operates only on
the `kind-obskit-evidence` context recorded there.

### Evidence Capture Flow

`run` executes the full evidence flow and writes committed artifacts
under `artifacts/evidence/batch23/`:

1. `install` - the guided installer end to end (`obskit install
   --live`, non-interactive answers from
   `scripts/dev/harness_assets/install_answers.json`), then the two
   contracted operator actions (commit `rendered/` into the
   disposable GitOps clone, apply the rendered Argo CD bootstrap),
   Argo CD sync to Synced/Healthy, and the live readiness report
   validated through `scripts/validate/post_install_readiness.sh`.
   Evidence: `install/` (installer artifacts verbatim plus
   `evidence_manifest.json`).
2. `restore-drill` - `scripts/ops/run_restore_drill.sh live`: a real
   OpenSearch snapshot, index delete, restore, and count
   verification. Evidence: `checks/restore_drill.json`.
3. `rollback-drill` - `scripts/ops/run_rollback_drill.sh live`: a
   forward GitOps commit, Argo CD convergence, `git revert`, and
   convergence back to the base state. Evidence:
   `checks/rollback_drill.json`.
4. `config-rollback-drill` -
   `scripts/ops/run_config_rollback_drill.sh real` (renderer
   round-trip on a scratch copy). Evidence:
   `checks/config_rollback_drill.json`.
5. `gui-smoke` - the portal served live over TLS
   (`scripts/dev/harness_assets/run_portal.py`), probed by
   `scripts/validate/admin_gui_smoke.sh` with `PORTAL_BASE_URL`
   set. Evidence: `checks/gui_smoke.json`.
6. `denials` - the nine cross-tenant denial scenarios `SDN-B15-001`
   through `SDN-B15-009` from
   `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`, executed
   live by `scripts/dev/harness_assets/run_denial_scenarios.py`.
   Evidence: `checks/denials/SDN-B15-00N.json`.

Commit the captured evidence; the validation contracts reference it
through their `captured_evidence` blocks.

### Re-Running a Single Check

```bash
bash scripts/dev/live_cluster_harness.sh run --only rollback-drill
```

Valid check ids: `install`, `restore-drill`, `rollback-drill`,
`config-rollback-drill`, `gui-smoke`, `denials`. Drill and denial
checks need the `install` check to have run first on the same
cluster (they use the installed platform and the GitOps clone). To
re-run one denial scenario, set `DENIAL_SCENARIO=SDN-B15-007` before
`run --only denials`.

### Resetting the Dev-Persistent Stack

The OrbStack built-in cluster is never an evidence source. To reset
it after dev iteration: delete the platform namespaces
(`observability`, `argocd`) from the OrbStack cluster or reset
Kubernetes from the OrbStack settings pane, then re-apply the dev
overlay through the normal GitOps flow
(`gitops/overlays/dev/platform-core-values.yaml`).

## Verification

1. Evidence exists and is structurally valid:

   ```bash
   bash scripts/ci/validate_live_evidence.sh
   ```

2. Teardown verified: `teardown` exits zero only when the cluster is
   absent from both `kind get clusters` and the Docker engine, and
   it records
   `artifacts/evidence/batch23/harness/teardown_verification.json`
   with both verifications true. Confirm with:

   ```bash
   bash scripts/dev/live_cluster_harness.sh status
   ```

   Expected: no provenance, no `obskit-evidence` cluster, no labeled
   containers.

3. The scratch directory `.live-harness/` holds no kubeconfig after
   teardown (the provenance and kubeconfig are removed on verified
   teardown).

## Rollback

The harness itself is disposable: `teardown` is the rollback for
every harness state, and a fresh `create` starts clean. Captured
evidence is plain committed files; reverting the commit that added
them restores the prior evidence state. The dev-persistent stack is
untouched by harness runs by construction (isolated kubeconfig,
context refusal).
