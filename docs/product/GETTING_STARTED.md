# Getting Started

This guide is for evaluators and first-time operators. It explains
what Observability Kit is, what a cluster needs before installing it,
and the shortest path from an empty Kubernetes cluster to a running
platform. When you are ready for the full installer reference,
continue with the [Installation Guide](INSTALLATION_GUIDE.md).

## Table of Contents

- [What Observability Kit Is](#what-observability-kit-is)
- [How the Platform Is Built](#how-the-platform-is-built)
- [Deployment Modes](#deployment-modes)
- [Prerequisites](#prerequisites)
- [Quickstart](#quickstart)
- [Previewing the Chart Without a Cluster](#previewing-the-chart-without-a-cluster)
- [Where to Go Next](#where-to-go-next)

## What Observability Kit Is

Observability Kit is a unified, cloud-agnostic, plug-and-play
observability platform. One guided install turns any conformant
Kubernetes cluster, cloud or on-prem, into a multi-tenant
observability platform with logs, metrics, traces, vector search, a
derived service graph, and AI-assisted incident analysis, all
operated from a single management plane.

The product holds a small set of non-negotiable invariants:

- One product, one install, one pane. Operators run a guided
  installer and manage everything, configuration, tenants, health,
  and the wrapped UIs, from a unified portal backed by a single
  schema-validated configuration document.
- Wrap, never fork. Every bundled system (OpenTelemetry Collector,
  OpenSearch, OpenSearch Dashboards, Grafana, Neo4j, Argo CD) stays
  upgradable through its own upstream mechanism. The platform
  configures wrapped systems; it never patches them.
- Multi-tenant with hard isolation. Cross-tenant access or leakage is
  a hard failure, not a policy preference. Isolation uses only native
  mechanisms of the wrapped systems and is deny-by-default.
- Cloud-agnostic core. OpenTelemetry is the sole collector, OpenSearch
  is the single telemetry and vector store, and Neo4j is a derived
  graph tier, never a raw telemetry store. No provider-specific
  service is mandatory; provider integrations are optional adapters.

## How the Platform Is Built

Delivery is Terraform + Helm + Argo CD. The installer renders a Helm
values overlay and Argo CD bootstrap manifests for your environment;
you commit them to your GitOps repository and Argo CD reconciles the
platform from there. Nothing writes persistent configuration directly
to the cluster API, so every change is reviewable, auditable, and
revertible with a Git revert.

Telemetry flows through one pipeline shape: OpenTelemetry collectors
(agents plus a gateway) receive logs, metrics, and traces and write
them to OpenSearch, which also serves vector search. The service graph
in Neo4j is derived from OpenSearch content and can always be rebuilt
from it. Dashboards, alert rules, and index lifecycle policies ship as
code alongside the charts.

## Deployment Modes

The installer recommends one of four deployment modes from a fixed
decision table, based on what it discovers in your cluster and the
intent you declare:

| Mode | When it is recommended |
| ---- | ---- |
| `quickstart` | You are evaluating the product (`--evaluation-only`). Fastest low-friction path. |
| `attach` | Compatible telemetry services already exist and you do not want new backend components. |
| `hybrid` | Compatible services exist, new components are allowed, and collectors must run in-cluster. |
| `standalone` | No attach path exists; deploy the full reference stack. |

The recommendation seeds the install contract; you confirm or override
it during contract capture. The decision rules live in
[MODE_DECISION_TABLE.json](../../contracts/compatibility/MODE_DECISION_TABLE.json).

## Prerequisites

You need:

- A conformant Kubernetes cluster and a kubeconfig with permission to
  read it. The installer grades the cluster `supported`,
  `conditional`, or `blocked` against the compatibility matrix before
  anything is rendered. Single-node clusters (kind, minikube, k3d)
  are fine for evaluation.
- Python 3.11 or newer for the `obskit` command-line tool. The tool's
  core is standard-library-only; reading a live cluster needs the
  `k8s` extra.
- A Git repository the platform's GitOps controller will watch. The
  installer emits manifests; committing them is your action.
- Helm, kubectl, and (once you bootstrap) Argo CD as the GitOps
  controller.
- Selected platform profiles for storage, object storage, identity,
  secrets, ingress, and GitOps controller. Defaults exist for all six
  dimensions; see
  [PROFILE_CATALOG.json](../../contracts/compatibility/PROFILE_CATALOG.json).

## Quickstart

The steps below evaluate the product on a cluster you control. The
same flow, without `--evaluation-only`, performs a real install; the
[Installation Guide](INSTALLATION_GUIDE.md) covers every option.

### Install the Obskit Tool

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install "./tools/obskit[k8s]"
```

The `[k8s]` extra pulls in the Kubernetes client used by live mode.
Without it, `obskit` still runs against recorded cluster snapshots.

### Run the Guided Installer

```bash
.venv/bin/obskit install \
  --live \
  --evaluation-only \
  --output-dir ./install-run
```

Run this from the repository root: the installer reads the contract
files from `./contracts` and uses the current directory as the
repository root by default. The installer executes a fixed seven-step
flow: preflight, compatibility grading, mode recommendation, contract
capture, render, Argo CD bootstrap manifests, and a post-install
readiness check. With `--evaluation-only` the mode recommendation is
`quickstart`. Prompts collect the install answers interactively;
every answer is recorded to `answers.json` so the run is reproducible
without prompts later.

If preflight fails or the cluster grades `blocked`, the run halts and
prints a remediation list. Fix the listed items and re-run: a failed
run resumes from the first incomplete step.

### Commit and Bootstrap

The installer writes rendered output under `--output-dir`, including
an environment values overlay and Argo CD bootstrap manifests. It
never applies anything to the cluster itself. Commit the rendered
files to your GitOps repository, then apply the bootstrap
kustomization exactly as the installer's final output instructs.
From that point Argo CD owns reconciliation.

### Verify Readiness

The installer's last step runs the post-install readiness check and
writes `install_summary.json` with the results and next steps. A
failed readiness check exits non-zero, so a zero exit code is your
signal that the platform is up.

## Previewing the Chart Without a Cluster

You can inspect exactly what the platform deploys before touching any
cluster. The quickstart overlay is the smallest footprint that still
exercises the full pipeline shape (single gateway replica, reduced
resources, graph tier disabled):

```bash
helm template platform-core gitops/charts/platform-core \
  -f gitops/overlays/quickstart/platform-core-values.yaml
```

Per-environment overlays live under `gitops/overlays/` (`base`,
`dev`, `staging`, `prod`, `quickstart`).

## Where to Go Next

- [Installation Guide](INSTALLATION_GUIDE.md) for the full installer
  reference: non-interactive runs, modes, and preflight remediation.
- [Configuration Guide](CONFIGURATION_GUIDE.md) for the unified
  configuration document and how changes propagate.
- [Operations Guide](OPERATIONS_GUIDE.md) for day-2 operations:
  upgrades, drills, drift response, and releases.
- [Documentation Index](INDEX.md) for the full documentation tree and
  reading paths per audience.
