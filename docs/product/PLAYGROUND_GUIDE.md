# Demo Playground Guide

This guide takes an evaluator or operator from a fresh or existing
local platform to populated dashboards and AI answers using only the
demo playground shipped under `demo/`. Every command is
copy-pasteable; no other document is required to complete the
walkthrough. The playground architecture is fixed by
[ADR-0011](../adr/ADR_0011_DEMO_PLAYGROUND_ARCHITECTURE.md).

## Table of Contents

- [What the Playground Is](#what-the-playground-is)
- [Prerequisites](#prerequisites)
- [Install the Platform](#install-the-platform)
- [Build and Load the Demo Image](#build-and-load-the-demo-image)
- [Deploy the Demo](#deploy-the-demo)
- [Run Traffic Scenarios](#run-traffic-scenarios)
- [Explore the Dashboards](#explore-the-dashboards)
- [Ask the AI](#ask-the-ai)
- [Tear Down](#tear-down)

## What the Playground Is

The demo package generates realistic telemetry so every product
surface - dashboards, tenancy, metering, and the AI layer - can be
exercised without instrumenting a real fleet. It ships five
product-owned workloads in one container image
(`ghcr.io/obskit/demo:0.1.0`): an HTTP API, an asynchronous worker, a
scheduled job, a SQLite-backed datastore service, and a declarative
load generator. All telemetry flows as OTLP/HTTP to the platform
collector gateway; no demo component writes to OpenSearch or Neo4j
directly.

The package is optional, additive, and removable. Deploying and
tearing it down never modifies core platform charts, contracts, or
the ArgoCD bootstrap, and the installer never deploys it.

Everything lands tenant-scoped: tenant `demo` (tier `standard`,
isolation class `shared-partition`), namespace `tenant-demo`,
environment `dev`, owner `team-demo`. Isolation, per-tenant
dashboards, and usage metering therefore run on demo data exactly as
they would on production data.

The ADR-0011 sizing budget caps the total demo footprint at 1 CPU and
1 GiB of memory requests across all pods, with each container
requesting at most 100m CPU and 128Mi memory. The playground fits the
OrbStack reference machine and the disposable kind harness.

## Prerequisites

- `docker` (or a compatible container engine) to build the demo
  image.
- A local Kubernetes cluster: either `kind` or the OrbStack built-in
  cluster.
- `kubectl` on `PATH`, with its current context pointing at that
  cluster.
- `helm` (used by the platform install; the demo itself is plain
  kustomize).
- A clone of this repository; run all commands from the repository
  root.

> [!WARNING]
> The playground refuses to deploy when `ENVIRONMENT=production` is
> set. It is a demo surface for local evaluation stacks only.

## Install the Platform

The demo needs a running Observability Kit platform to send
telemetry to. Pick one of the two paths below. If your cluster
already runs the platform (for example the persistent OrbStack dev
stack), skip to
[Build and Load the Demo Image](#build-and-load-the-demo-image).

### Fresh Cluster: Guided Install

From the repository root, install the `obskit` tool and run the
guided installer against your current kubeconfig context:

```bash
python3 -m venv .venv
.venv/bin/pip install "./tools/obskit[k8s]"
.venv/bin/obskit install \
  --live \
  --evaluation-only \
  --output-dir ./install-run
```

The installer executes a fixed seven-step flow: preflight,
compatibility grading, mode recommendation, contract capture, render,
Argo CD bootstrap manifests, and a post-install readiness check. With
`--evaluation-only` the recommended mode is `quickstart`. If
preflight fails, fix the printed remediation list and re-run; a
failed run resumes from the first incomplete step. The
[Installation Guide](INSTALLATION_GUIDE.md) covers every option.

### Fresh Cluster: Disposable Kind Harness

Alternatively, the live-cluster harness creates a disposable kind
cluster (`obskit-evidence`) and executes the full guided install on
it:

```bash
bash scripts/dev/live_cluster_harness.sh run --only install
```

The harness publishes committed Git state only, so commit your work
before running it. Tear the harness cluster down with the harness
itself when you are done; it is disposable by contract.

### Reusing the OrbStack Dev Stack

The persistent OrbStack dev stack already runs the platform. Confirm
the collector gateway is up and exposes the OTLP/HTTP port the demo
targets:

```bash
kubectl config use-context orbstack
kubectl -n observability get svc otel-gateway
kubectl -n observability get pods
```

The `otel-gateway` Service must list port `4318` (`otlp-http`). No
further platform work is needed.

## Build and Load the Demo Image

The image is product-owned and built from the repository:

```bash
docker build -t ghcr.io/obskit/demo:0.1.0 demo/services
```

All demo manifests pin exactly this tag with
`imagePullPolicy: IfNotPresent`, so the cluster uses your local build
and never pulls from a registry.

For a kind cluster (including the harness cluster), load the image
into the cluster nodes:

```bash
kind load docker-image ghcr.io/obskit/demo:0.1.0 --name obskit-evidence
```

Replace `obskit-evidence` with your kind cluster name (`kind get
clusters` lists them). On OrbStack the built-in cluster shares the
local Docker image store, so the plain `docker build` above is
sufficient - no load step.

## Deploy the Demo

One command deploys the whole playground:

```bash
bash demo/deploy.sh
```

The script applies the `demo/gitops/base` kustomize root against the
current kubeconfig context and refuses to run when
`ENVIRONMENT=production`. It creates:

- Namespace `tenant-demo`, labeled for tenant `demo` and environment
  `dev`.
- Four sample services as Deployments and a CronJob: `demo-http-api`,
  `demo-worker`, `demo-datastore`, and `demo-scheduled-job` (runs
  every 5 minutes).
- The load generator `demo-loadgen` with the four scenario documents
  mounted from the `demo-scenarios` ConfigMap.

Each service is onboarded through the Batch 7 one-block subscription
contract (`demo/onboarding/onboarding-values.yaml`,
`subscriptionMode: instrumentation`) and carries the
admission-required labels `service.name`, `deployment.environment`,
and `service.owner`. The tenant descriptor is
`demo/onboarding/tenant-demo.json`.

Verify the rollout:

```bash
kubectl get pods -n tenant-demo
kubectl get cronjob -n tenant-demo
kubectl logs -n tenant-demo deployment/demo-loadgen --tail=20
```

All pods reach `Running` (the scheduled job appears as completed pods
every 5 minutes), and the loadgen log shows the active scenario. For
GitOps-managed environments, apply the shipped ArgoCD Application
instead of the script:

```bash
DEMO_REPO_URL=<your-git-remote> \
  envsubst < demo/gitops/demo-application.yaml | kubectl apply -f -
```

## Run Traffic Scenarios

Traffic is scenario-driven and declarative. Exactly one scenario
document runs at a time, selected by the `DEMO_SCENARIO` environment
variable on the `demo-loadgen` Deployment:

```bash
kubectl -n tenant-demo set env deployment/demo-loadgen \
  DEMO_SCENARIO=<name>
```

`<name>` is one of the four shipped documents in
`demo/gitops/base/scenarios/`, validated against
`contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json` before any traffic is
sent:

| Scenario | What it shows |
| ---- | ---- |
| `steady-baseline` | Gentle continuous load (the default): healthy telemetry on every dashboard, tenancy, and metering surface |
| `burst` | Periodic 5x burst windows every 120 seconds: throughput panels and usage metering show realistic variation |
| `error-injection` | Roughly 30 percent of requests answered HTTP 500: error dashboards, risk scoring, and assisted RCA light up |
| `latency-injection` | Roughly 800 ms of injected server-side latency: latency percentiles, slow traces, and RCA surfaces light up |

Fault injection is honest: the generator only attaches
`x-demo-fault-ratio` and `x-demo-latency-ms` request headers, and the
demo HTTP API honors them server-side, so every injected fault is a
real distributed trace. Expect 10-15 minutes of scenario runtime
before dashboards and AI answers reflect the change. Full scenario
reference: [demo/SCENARIOS.md](../../demo/SCENARIOS.md).

## Explore the Dashboards

Four demo dashboards ship as saved-object NDJSON under the platform
provisioning path
`gitops/platform/search/dashboards/saved-objects/`, additive and
inert without demo data. Open OpenSearch Dashboards through the admin
access plane or the portal and find them by title; if your instance
does not auto-provision saved objects, import the `DEMO_*.ndjson`
files via Dashboards Management, then Saved objects, then Import.

| File | Dashboard title |
| ---- | ---- |
| `DEMO_SERVICE_OVERVIEW.ndjson` | Demo Service Overview |
| `DEMO_LOGS_EXPLORER.ndjson` | Demo Logs Explorer |
| `DEMO_LATENCY_TRACES.ndjson` | Demo Latency and Traces |
| `DEMO_ERRORS_ALERTS.ndjson` | Demo Errors and Alerts |

Every dashboard carries the standard filter set - `tenant_id`,
`service.name`, and `k8s.namespace.name`, plus a severity or status
dimension - and restores a default time range. Demo data is always
`tenant_id: demo` in namespace `tenant-demo`.

The fault scenarios light up these panels (mirroring each scenario
document's `expectations` block):

| Scenario | Panels |
| ---- | ---- |
| `error-injection` | Demo Errors and Alerts: `error-rate-by-service`; Demo Service Overview: `request-rate-and-errors`; Demo Logs Explorer: `error-log-stream` |
| `latency-injection` | Demo Latency and Traces: `p95-latency-by-route` and `slow-trace-waterfall`; Demo Service Overview: `latency-percentiles` |

## Ask the AI

The prompt pack
[demo/prompts/AI_PROMPT_PACK.md](../../demo/prompts/AI_PROMPT_PACK.md)
ships paste-ready prompts bound to the demo scenarios. To use it:

1. Select the scenario named by the prompt (previous section) and let
   it run 10-15 minutes.
2. Open the AI/kagent chat surface exposed by the AI runtime
   (`gitops/platform/ai/`).
3. Paste the prompt text verbatim. Prompts carry the `tenant_id demo`
   scope explicitly, so tenancy redaction and isolation behave
   exactly as in production.

The pack is read-path by default: every prompt exercises read-only
MCP catalog tools (`incident-search`, `graph-analysis`,
`trace-investigation`, `metrics-correlation`, `change-intelligence`,
and the casefile read operation) that run without approval.

> [!IMPORTANT]
> Exactly one prompt writes: the Casefile Follow-Up Note, which
> appends to an incident casefile through the approval flow in
> `contracts/policy/APPROVAL_FLOW_V1.yaml`, unchanged. Policy is
> evaluated before the write, missing preconditions deny it, and the
> playground relaxes none of the timeout or escalation rules.

## Tear Down

One command removes everything the deploy created:

```bash
bash demo/teardown.sh
```

Confirm the demo is gone and the platform is unchanged:

```bash
kubectl get namespace tenant-demo
kubectl -n observability get pods
```

The first command reports `NotFound` once deletion completes; the
second shows the platform pods untouched. The dashboards' saved
objects are additive platform provisioning and simply render empty
without demo data. Because the package never modifies core charts,
contracts, or the bootstrap, no further cleanup exists by design.
