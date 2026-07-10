# Observability Kit Demo Playground

Optional, additive, removable demo package. It deploys sample
workloads that emit logs, metrics, and traces through OpenTelemetry
to the platform collector, plus a scenario-driven load generator, so
every product surface - dashboards, tenancy, metering, and the AI
layer - can be exercised on realistic data. Nothing in the core
charts, contracts, or the ArgoCD bootstrap changes when this package
is deployed or torn down.

Architecture decisions are recorded in
[ADR-0011](../docs/adr/ADR_0011_DEMO_PLAYGROUND_ARCHITECTURE.md).
The operator walkthrough is
[PLAYGROUND_GUIDE.md](../docs/product/PLAYGROUND_GUIDE.md).

## Package Layout

```text
demo/
  README.md                    This file
  SCENARIOS.md                 Scenario reference and selection
  deploy.sh                    One-command deploy (kustomize apply)
  teardown.sh                  One-command teardown
  onboarding/
    onboarding-values.yaml     Batch 7 one-block onboarding values
    tenant-demo.json           Demo tenant descriptor
  services/
    Dockerfile                 Single obskit-demo image, five
                               entrypoints
    pyproject.toml             Stdlib-only Python package
    demosvc/                   Service and load generator code
    SIGNAL_INVENTORY.md        Emitted signals per service
  gitops/
    base/                      Kustomize root deploy.sh applies
      scenarios/               Traffic scenario definitions
                               (schema: contracts/demo/
                               DEMO_SCENARIO_SCHEMA_V1.json)
    demo-application.yaml      Optional ArgoCD Application (operator
                               applied, never bootstrapped)
  prompts/
    AI_PROMPT_PACK.md          MCP-bound AI playground prompts
```

Demo dashboards live under the platform provisioning path
(`gitops/platform/search/dashboards/saved-objects/DEMO_*.ndjson`),
not in this directory, because the dashboards tier provisions from
there.

## Deploy

```bash
bash demo/deploy.sh
```

Applies `demo/gitops/base` with kustomize against the current
kubeconfig context. The demo lands in namespace `tenant-demo` under
tenant `demo` (owner `team-demo`, environment `dev`), onboarded
through the Batch 7 one-block subscription contract. The script
refuses to run when `ENVIRONMENT=production`.

For GitOps-managed environments, apply the shipped ArgoCD
Application instead (set the repo URL first):

```bash
DEMO_REPO_URL=<your-git-remote> \
  envsubst < demo/gitops/demo-application.yaml | kubectl apply -f -
```

## Teardown

```bash
bash demo/teardown.sh
```

Deletes everything `deploy.sh` created (the `tenant-demo` namespace
and its contents). The platform itself is untouched.

## Traffic Scenarios

The load generator runs the scenario named by the `DEMO_SCENARIO`
value in `demo/gitops/base` (default `steady-baseline`). See
[SCENARIOS.md](SCENARIOS.md) for every scenario, how to select one,
and what each fault scenario lights up.

## Sizing

Total demo footprint stays within 1 CPU and 1 GiB of requests, per
ADR-0011, fitting the OrbStack development stack and the disposable
kind harness.
