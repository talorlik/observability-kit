# ADR-0011: Demo Playground Architecture

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 27 owner)
**Markers:** TB-27, TR-06, TR-15, TR-27

## Context

Batches 17-26 delivered a GA-reviewed platform, but an evaluating
operator has nothing to observe: no workloads, no traffic, no
incidents. Batch 27 ships a demo package under `demo/` that
generates realistic telemetry and exercises dashboards, tenancy,
metering, and the AI layer on the local stacks (OrbStack dev stack
and the disposable kind harness).

Two technology choices are ADR-gated by the plan: how the sample
workloads are sourced, and how load is generated. Both are bound by
the platform's hard constraints: OpenTelemetry is the sole
collector, no demo component writes to OpenSearch or Neo4j
directly, wrap-never-fork applies to any upstream application, the
package must be optional, additive, and removable, and sizing must
fit the development stack.

## Decision

1. **Workload sourcing: house-built, single image.** The demo
   services are product-owned code in one `obskit-demo` container
   image (`python:3.12-slim` base, standard-library-only Python,
   the `services/ai` image pattern). One image provides five
   entrypoints selected by container args: `http-api`, `worker`,
   `scheduled-job`, `datastore`, and `loadgen`. No upstream demo
   application is wrapped, so wrap-never-fork is satisfied
   trivially and no wrapped-system registry or license inventory
   entries are needed.
2. **Telemetry emission: stdlib OTLP/HTTP JSON emitter.** The demo
   services emit logs, metrics, and traces as OTLP/HTTP JSON
   (protocol-stable encoding) to the platform gateway collector at
   `otel-gateway.observability.svc.cluster.local:4318`. The
   gateway container already listens on 4318; the chart's
   `otel-gateway` Service gains an additive `otlp-http` port. The
   OpenTelemetry Python SDK is rejected because it would make the
   demo package the only non-stdlib Python in the repository,
   breaking the offline test posture (`tests/` runs without PyPI)
   and adding a PyPI dependency to the image build.
3. **Load generation: house-pattern declarative scenario runner.**
   The `loadgen` entrypoint of the same image executes declarative
   scenario documents (steady baseline, burst, error-injection,
   latency-injection) validated by
   `contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json` with seeded
   invalid samples. k6 and fortio are rejected: each would add a
   wrapped-system registry entry, a license inventory entry, and
   image weight that buys nothing at demo scale.
4. **Datastore tier: SQLite via the Python stdlib.** The
   datastore-backed service uses `sqlite3` in-pod, producing
   genuine `db.*` client spans without a database pod. A dedicated
   PostgreSQL instance is rejected: it would introduce a second
   unregistered public-image pin and consume development-stack
   budget for no additional telemetry value.
5. **Tenant scoping.** The package deploys under tenant `demo`
   (tier `standard`, isolation class `shared-partition`), namespace
   `tenant-demo`, environment `dev`, owner `team-demo`. Each
   service onboards through the Batch 7 one-block subscription
   contract (`subscriptionMode: instrumentation`) and carries the
   admission-required labels `service.name`,
   `deployment.environment`, and `service.owner`, so isolation,
   per-tenant dashboards, and usage metering are exercised on demo
   data.
6. **Deployment: operator-explicit, one command, core untouched.**
   `bash demo/deploy.sh` applies the `demo/gitops/base` kustomize
   root; `bash demo/teardown.sh` removes it, leaving the platform
   unchanged. Both refuse `ENVIRONMENT=production`. For
   GitOps-managed environments an ArgoCD Application manifest is
   shipped at `demo/gitops/demo-application.yaml` (repo URL
   parameterized, applied only by the operator, never referenced
   from `gitops/apps/` or the bootstrap). The installer never
   deploys the demo.
7. **Sizing budget.** Total demo footprint is capped at 1 CPU and
   1 GiB memory of requests across all pods (each service requests
   at most 100m CPU and 128Mi memory), fitting the OrbStack
   reference machine and the disposable kind harness.
8. **Dashboards and prompts.** Demo dashboards ship as saved-object
   NDJSON under the platform provisioning path
   (`gitops/platform/search/dashboards/saved-objects/DEMO_*`),
   additive and inert without demo data. The AI prompt pack binds
   only read-path MCP catalog tools by default; any write-path
   prompt routes through the approval flow unchanged.

## Alternatives Considered

- **Wrapping the upstream OpenTelemetry Demo** (astronomy shop):
  rejected. Roughly twenty polyglot services exceed the
  development-stack sizing budget, the Helm chart assumes bundled
  backends the platform already provides, and trimming it to fit
  would drift into fork territory.
- **Per-kind public sample images** (for example nginx plus a
  public cron image): rejected. Each image is an unpinned
  wrapped-system surface, none emit coherent cross-service traces,
  and the mix cannot demonstrate the one-block onboarding contract
  cleanly.
- **OpenTelemetry Python SDK for instrumentation**: rejected for
  the emitter reasons in Decision 2; revisitable post-GA if the
  demo ever needs SDK-specific features (for example exemplars).
- **k6 or fortio as the load generator**: rejected for the
  registry, license, and sizing reasons in Decision 3.
- **PostgreSQL as the demo datastore**: rejected for the pin and
  budget reasons in Decision 4.
- **Registering the demo in `gitops/apps/`**: rejected. That path
  is reconciled by the bootstrap app-of-apps, which would make the
  demo a default platform component and violate the
  optional-additive-removable requirement.

## Consequences

- The demo package is fully offline-testable: scenario documents,
  manifests, onboarding blocks, dashboards, and the prompt pack are
  validated structurally by `scripts/ci/validate_demo_playground.sh`
  without a cluster, and the emitter is unit-tested against the
  OTLP JSON shape in `tests/demo/`.
- The platform-core chart gains one additive Service port
  (`otlp-http`, 4318) on `otel-gateway`. Any future HTTP-emitting
  workload benefits; the collector topology contract is unchanged.
- Hand-rolled OTLP emission means the demo owns its span-context
  and histogram encoding; the emitter stays small and is pinned by
  tests to the OTLP JSON encoding rules (hex trace and span ids).
- Deploy and teardown never modify core charts, contracts, or the
  ArgoCD bootstrap; removal is `kubectl delete` of the demo
  namespace-scoped resources only.
- Demo telemetry flows under tenant `demo`, so metering and
  isolation surfaces show real per-tenant data without touching
  any customer-shaped tenant fixture.
