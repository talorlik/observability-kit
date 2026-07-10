# Installation Guide

This guide is the full reference for installing Observability Kit
with the guided installer, `obskit install`. It covers the contracted
install flow, interactive and non-interactive runs, deployment modes,
compatibility grading, and preflight remediation. For a first
orientation, read [Getting Started](GETTING_STARTED.md); for the
operator runbook form of this material, see the
[guided installation runbook](../runbooks/GUIDED_INSTALLATION_GUIDE.md).

## Table of Contents

- [How the Installer Works](#how-the-installer-works)
- [The Seven Steps](#the-seven-steps)
- [Before You Run the Installer](#before-you-run-the-installer)
- [Interactive Installation](#interactive-installation)
- [Non-Interactive Installation](#non-interactive-installation)
- [Command Reference](#command-reference)
- [Install Contract Answers](#install-contract-answers)
- [Compatibility Grading and Remediation](#compatibility-grading-and-remediation)
- [Deployment Mode Selection](#deployment-mode-selection)
- [Completing the Installation](#completing-the-installation)
- [Re-Running and Resuming](#re-running-and-resuming)
- [Related Material](#related-material)

## How the Installer Works

The installer executes a seven-step flow whose order is fixed by
contract in
[INSTALL_FLOW_CONTRACT_V1.yaml](../../contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml)
and decided by
[ADR-0002](../adr/ADR_0002_GUIDED_INSTALL_FLOW.md). The installer
loads that contract at runtime and asserts its own step sequence
against it, so the flow you run is the flow that is documented here.

Three properties shape everything below:

- GitOps-only. The render and bootstrap steps write files; the
  installer performs no direct mutable cluster API writes for
  persistent configuration. You commit the rendered output and the
  GitOps controller applies it.
- Deterministic. Identical answers and cluster inputs produce
  byte-identical reports and rendered manifests. Every rendered file
  carries a generated-file header so hand edits are detectable.
- Idempotent and resumable. Re-running a completed install changes
  nothing and exits zero. A failed run resumes from the first
  incomplete step, keyed by the `install_state.json` journal. Steps
  that read the live cluster always re-execute in live mode, because
  live cluster state has no stable digest.

## The Seven Steps

Steps run strictly in ascending order. Each emits artifacts under
`--output-dir` and halts the flow on its declared condition.

| Order | Step | Emits | Halts when |
| ---- | ---- | ---- | ---- |
| 1 | `preflight` | `preflight_report.json` | Any preflight check class reports `fail`; remediation guidance accompanies the halt. |
| 2 | `grading` | `capability_matrix.json`, `compatibility_result.json`, `remediation_list.json` | The compatibility grade is `blocked`; the remediation list is the fix path. |
| 3 | `mode-recommendation` | `mode_recommendation.json` | No rule in the mode decision table matches the inputs. |
| 4 | `contract-capture` | `answers.json`, `install_contract.json` | The captured answers do not validate against the install contract schema. |
| 5 | `render` | `rendered/overlays/<environment>/platform-core-values.yaml` | Rendered output fails its structural self-check. |
| 6 | `argocd-bootstrap` | `rendered/bootstrap/argocd/kustomization.yaml`, `rendered/bootstrap/argocd/platform-core-application.yaml` | Bootstrap manifests fail their structural self-check. |
| 7 | `post-install-readiness` | `install_summary.json` | The post-install readiness check exits non-zero. |

Answers always validate against
[INSTALL_CONTRACT_SCHEMA.json](../../contracts/install/INSTALL_CONTRACT_SCHEMA.json)
before any render or bootstrap step executes; invalid answers fail
the run with a non-zero exit code.

## Before You Run the Installer

Install the tool from the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install "./tools/obskit[k8s]"
```

Python 3.11 or newer is required. The `[k8s]` extra is needed only
for `--live` runs; snapshot runs work with the standard library
alone.

Run the installer from the repository root. By default it reads
contract files from `./contracts` and uses the current directory as
the repository root for the readiness step; both defaults are
overridable with `--contracts-dir` and `--repo-root`.

## Interactive Installation

```bash
.venv/bin/obskit install \
  --live \
  --output-dir ./install-run
```

Prompts collect every answer the install contract schema requires.
The captured answers are recorded to `answers.json` in the output
directory, so any interactive run is reproducible non-interactively
afterwards.

Use `--kubeconfig` and `--context` to select the cluster explicitly;
otherwise the standard kubeconfig resolution order applies.
`--cluster-name` overrides the name recorded in reports (the default
in live mode is the kubeconfig context name).

## Non-Interactive Installation

```bash
.venv/bin/obskit install \
  --live \
  --answers ./answers.json \
  --output-dir ./install-run
```

An answers file drives exactly the same step sequence with no
prompts. Parity with interactive mode is a contract invariant, not a
convenience: the flow, validation, and outputs are identical either
way. The natural workflow is to run interactively once, review the
recorded `answers.json`, and reuse it for repeatable installs.

Installs can also run against a recorded cluster snapshot instead of
a live cluster:

```bash
.venv/bin/obskit install \
  --snapshot ./cluster-snapshot.json \
  --answers ./answers.json \
  --output-dir ./install-run
```

Snapshot mode exercises the full flow offline, which is how the
repository's own CI validates the installer.

## Command Reference

`obskit install` accepts the following flags. `--snapshot` and
`--live` are mutually exclusive and one is required.

| Flag | Meaning |
| ---- | ---- |
| `--snapshot <path>` | Read a recorded cluster snapshot (fixture mode). |
| `--live` | Read a live cluster via the Kubernetes API (requires the `[k8s]` extra). |
| `--kubeconfig <path>` | Kubeconfig path for live mode (default: standard resolution order). |
| `--context <name>` | Kubeconfig context for live mode. |
| `--cluster-name <name>` | Cluster name recorded in reports (live mode default: the context name). |
| `--output <path>` | Report destination file, or `-` for stdout (default). |
| `--answers <path>` | Answers JSON file validated against the install contract schema; omit to capture answers interactively. |
| `--output-dir <path>` | Required. Directory receiving reports, the captured install contract, rendered manifests, and the `install_state.json` journal. |
| `--contracts-dir <path>` | Repository contracts directory (default: `./contracts`). |
| `--profiles <path>` | Optional JSON file supplying profiles discovery cannot observe (object storage, identity); discovered profiles default from the capability matrix. |
| `--repo-root <path>` | Repository root used by the post-install readiness step (default: `.`). |
| `--evaluation-only` | Mode input: this run evaluates the product rather than installing it. |
| `--allow-new-backend-components true\|false` | Mode input: new backend components may be deployed (default: `true`). |
| `--require-in-cluster-collectors true\|false` | Mode input: collectors must run in-cluster (default: `true`). |
| `--has-compatible-existing-services auto\|true\|false` | Mode input: compatible existing services are present; `auto` derives it from the discovery probes (default: `auto`). |

The four mode-input flags mirror `obskit evaluate` flag for flag, so
both commands resolve the mode recommendation identically.

## Install Contract Answers

Contract capture collects these answers, interactively or from
`--answers`, and validates them against the install contract schema:

- `cluster_name` and `environment` identify the target.
- `deployment_mode` confirms or overrides the recommended mode.
- `gitops_repo_url` and `gitops_path` locate the GitOps repository
  the rendered output will be committed to.
- `base_domain` anchors ingress hostnames.
- `storage_profile`, `object_storage_profile`, `identity_profile`,
  `secret_profile`, and `ingress_profile` select platform profiles
  from the
  [profile catalog](../../contracts/compatibility/PROFILE_CATALOG.json).
- `attached_services` and `external_trust_references` describe
  existing services for attach and hybrid modes.

## Compatibility Grading and Remediation

Preflight runs every contracted check class (cluster connectivity,
required permissions, API readiness, and CRD readiness) and emits a
report conforming to
[PREFLIGHT_REPORT_SCHEMA.json](../../contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json).
A failing check class halts the flow with remediation guidance.

Grading then derives the capability matrix and a compatibility grade
on a three-level scale, per
[GRADING_RULES.json](../../contracts/compatibility/GRADING_RULES.json):

- `supported` proceeds without conditions.
- `conditional` proceeds with declared conditions (for example, a
  distribution that is supported only in a specific configuration).
- `blocked` halts the install. Blocking causes are an unsupported
  Kubernetes version or distribution, a missing required profile, or
  an unmet profile prerequisite.

Every blocking or conditional finding maps to concrete actions in the
[remediation catalog](../../contracts/compatibility/REMEDIATION_CATALOG.json),
and the emitted `remediation_list.json` is your ordered fix path:
resolve the listed items, then re-run the installer. Cluster-reading
steps re-execute, so the new grade reflects the fixed cluster. The
[preflight and discovery operator guide](../runbooks/PREFLIGHT_AND_DISCOVERY_OPERATOR_GUIDE.md)
covers diagnosing individual checks in depth.

## Deployment Mode Selection

The mode recommendation resolves from the decision table in
[MODE_DECISION_TABLE.json](../../contracts/compatibility/MODE_DECISION_TABLE.json),
driven by the four mode-input flags and, for
`--has-compatible-existing-services auto`, by what discovery actually
found. The supported modes are `quickstart`, `attach`, `standalone`,
and `hybrid`; [Getting Started](GETTING_STARTED.md) summarizes when
each is recommended, and the
[compatibility and mode operator guide](../runbooks/COMPATIBILITY_AND_MODE_OPERATOR_GUIDE.md)
explains the reasoning behind each rule.

## Completing the Installation

The installer never applies manifests. Its final steps emit the
environment overlay and the Argo CD bootstrap manifests, and print
the operator apply instruction. To complete the install:

1. Commit the rendered output to the GitOps repository and path you
   declared in the install contract.
2. Apply the bootstrap kustomization exactly as the installer's
   output instructs. This bootstraps Argo CD pointing at your
   committed overlay; from here on, the GitOps controller owns
   reconciliation.
3. Confirm the readiness result in `install_summary.json`. The
   readiness step invokes the repository's post-install readiness
   probe and a failure yields a non-zero installer exit code.

## Re-Running and Resuming

The `install_state.json` journal in the output directory records step
completion and input digests:

- Re-running a completed install changes nothing and exits zero.
- Re-running a failed install resumes from the first incomplete step.
- In live mode, the cluster-reading steps (preflight, grading, mode
  recommendation, readiness) always re-execute; rendered outputs are
  only rewritten when their inputs changed, and re-rendering the same
  contract produces byte-identical output.

## Related Material

- [Guided installation runbook](../runbooks/GUIDED_INSTALLATION_GUIDE.md)
  for the step-by-step operator procedure with verification points.
- [Install runbook](../runbooks/INSTALL_RUNBOOK.md) for the baseline
  install and rollback procedure.
- [Configuration Guide](CONFIGURATION_GUIDE.md) for changing the
  platform after installation.
- [ADR-0002](../adr/ADR_0002_GUIDED_INSTALL_FLOW.md) for why the flow
  is shaped this way.
