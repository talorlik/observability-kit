# Guided Installation Guide

Operator guide for the Batch 18 guided installer: `obskit install`
takes a conformant Kubernetes cluster from empty to a verified
installation in one contracted flow, interactively or fully
unattended.

> [!NOTE]
> This is the operator runbook for the installer. The full
> customer-facing product documentation tree (`docs/product/`,
> including the product-level installation guide) arrives in
> Batch 26.

## Scope

- Interactive installation with the `obskit install` wizard.
- Non-interactive installation with `obskit install --answers`.
- Resume after a failed or interrupted run.
- Post-install readiness verification and the install summary.

The flow is fixed by
`contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml` (decided by
`docs/adr/ADR_0002_GUIDED_INSTALL_FLOW.md`): preflight, grading, mode
recommendation, install contract capture, render, Argo CD bootstrap,
post-install readiness. The installer composes the Batch 17 discovery
executor and emits GitOps artifacts only - it performs no cluster API
writes and never modifies wrapped open-source systems.

## Pre-Checks

- Python 3.11+ available. The installer core is stdlib-only; live
  cluster access additionally needs the `[k8s]` extra
  (`pip install './tools/obskit[k8s]'`) and read-only RBAC per
  `tools/obskit/rbac/obskit-readonly-rbac.yaml`.
- An Observability Kit checkout (`--repo-root`) for the contract
  files and the readiness script.
- A GitOps repository the operator can commit to, carrying the kit's
  `gitops/` tree (chart and base overlay); the install answers point
  at it via `gitops_repo_url` and `gitops_path`.
- Cluster input: either `--live` (with optional `--kubeconfig` and
  `--context`) or `--snapshot <file>` with a recorded cluster
  snapshot for offline rehearsal.

## Procedure

### Interactive Install

```bash
cd tools/obskit
PYTHONPATH=. python3 -m obskit install \
  --live \
  --output-dir /tmp/obskit-install \
  --repo-root ../..
```

The wizard walks the contracted steps. Preflight, grading, and mode
recommendation run first; a failed preflight check or a `blocked`
compatibility grade halts the run with the remediation list
(`remediation_list.json`). The wizard then prompts for every install
contract field, offering the recommended deployment mode as the
default, validates the answers against
`contracts/install/INSTALL_CONTRACT_SCHEMA.json`, and records them to
`answers.json` - every interactive run is replayable non-interactively
from that file. Invalid answers fail the run with a non-zero exit
before anything renders.

### Non-Interactive Install

```bash
PYTHONPATH=tools/obskit python3 -m obskit install \
  --live \
  --answers answers.json \
  --output-dir /tmp/obskit-install \
  --repo-root .
```

The answers file drives exactly the flow the wizard drives - full
parity by contract. The same schema validation applies: invalid
answers exit non-zero before any render or bootstrap step executes.

### Rendered Output and Bootstrap

The render and bootstrap steps write, under
`<output-dir>/rendered/`:

- `overlays/<environment>/platform-core-values.yaml` - the
  environment overlay derived from the install contract.
- `bootstrap/argocd/kustomization.yaml` and
  `bootstrap/argocd/platform-core-application.yaml` - the Argo CD
  bootstrap manifests (a multi-source Application resolving the
  overlay through Helm's `$values` mechanism).

Every rendered file carries a generated-file header marker and
re-rendering the same contract is byte-identical. The installer
applies nothing itself (GitOps-only propagation): commit the CONTENTS
of `rendered/` into `<gitops_path>/` of the GitOps repository, then
bootstrap the controller:

```bash
kubectl apply -k <gitops_path>/bootstrap/argocd/
```

### Resume After Failure

State lives in `<output-dir>/install_state.json`: per-step status and
input digests. Re-running the same command resumes from the first
incomplete step; completed steps whose inputs are unchanged are
skipped. Re-running a fully completed install changes nothing and
exits zero. In live mode the cluster-reading steps (preflight,
grading, mode recommendation, readiness) always re-execute, because
live cluster state has no stable digest. To restart from scratch, use
a fresh `--output-dir`.

## Verification

The final step invokes
`scripts/validate/post_install_readiness.sh` and emits
`install_summary.json` plus a human-readable summary listing each
readiness section and the next steps. A failed readiness check makes
the installer exit non-zero; the summary is still written for
diagnosis.

> [!IMPORTANT]
> Until the Batch 23 live-cluster harness lands, the readiness check
> validates the declared readiness report contract (sections show
> `pending`), not live cluster state. `readiness.passed: true` means
> the readiness contract holds; live evidence capture arrives with
> Batch 23. Cluster-level confirmation is the Argo CD health check
> below.

Confirm:

- installer exit code `0`;
- `install_summary.json` shows `readiness.passed: true` and every
  expected readiness section;
- the rendered overlay and bootstrap manifests exist and carry the
  generated-file header;
- after committing and bootstrapping, the Argo CD `platform-core`
  Application reports `Synced/Healthy`.

Offline validation of the installer itself:
`bash scripts/ci/validate_guided_installer.sh` (also aggregated by
`bash scripts/ci/validate_batch18_smoke.sh`).

## Rollback

The installer writes only to `--output-dir` and changes no cluster or
repository state itself, so pre-bootstrap rollback is deleting that
directory. After the operator has committed rendered output, rollback
is a Git revert of that commit in the GitOps repository, reconciled
by Argo CD (see `docs/runbooks/ROLLBACK_RUNBOOK.md`); an applied
bootstrap is removed with
`kubectl delete -k <gitops_path>/bootstrap/argocd/`.
