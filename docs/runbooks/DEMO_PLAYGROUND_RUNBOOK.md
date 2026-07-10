# Demo Playground Runbook

Operator drill procedures for the Batch 27 demo playground: deploy,
scenario execution, verification, and teardown of the demo workloads
under `demo/`, exercising dashboards, tenancy, metering, and the AI
layer on demo data (TR-27, ADR-0011).

## Scope

- Deploying and removing the demo package on a local platform stack.
- Running the four traffic scenarios, including the two fault
  scenarios, and observing the surfaces they light up.
- Verifying telemetry flow end to end: pods, collector, dashboards,
  and an AI answer.

Out of scope: installing the platform itself (see
`docs/runbooks/GUIDED_INSTALLATION_GUIDE.md`) and authoring new
scenarios (see `demo/SCENARIOS.md`). The evaluator-facing walkthrough
is `docs/product/PLAYGROUND_GUIDE.md`; this runbook is the internal
drill procedure.

## Preconditions

- Allowed stacks:
  - The OrbStack persistent dev stack (`dev-persistent`) for
    iteration and day-to-day demo work.
  - The disposable kind harness cluster (`obskit-evidence`, created
    by `scripts/dev/live_cluster_harness.sh`) when a drill must
    produce committed evidence.
  - The persistent dev stack is never an evidence source; only the
    disposable harness produces evidence (Batch 23 contract).
- `ENVIRONMENT` is not `production`; `demo/deploy.sh` hard-refuses
  it.
- The platform is running: `kubectl -n observability get svc
  otel-gateway` lists port `4318` (`otlp-http`).
- The demo image is built and reachable by the cluster:

  ```bash
  docker build -t ghcr.io/obskit/demo:0.1.0 demo/services
  # kind clusters only (OrbStack shares the local image store):
  kind load docker-image ghcr.io/obskit/demo:0.1.0 \
    --name obskit-evidence
  ```

## Deploy Drill

1. From the repository root:

   ```bash
   bash demo/deploy.sh
   ```

2. Confirm what was created: namespace `tenant-demo`; Deployments
   `demo-http-api`, `demo-worker`, `demo-datastore`, `demo-loadgen`;
   CronJob `demo-scheduled-job`; ConfigMap `demo-scenarios`.

   ```bash
   kubectl get all -n tenant-demo
   ```

3. Confirm the core platform was not modified: `git status` is clean
   and no resource outside `tenant-demo` changed.

## Scenario Drill

1. Select a scenario on the running load generator:

   ```bash
   kubectl -n tenant-demo set env deployment/demo-loadgen \
     DEMO_SCENARIO=<name>
   ```

   `<name>` is `steady-baseline`, `burst`, `error-injection`, or
   `latency-injection`.

2. Let the scenario run 10-15 minutes before judging any surface.

3. For the fault scenarios, observe the surfaces named by the
   scenario document's `expectations` block:

   - `error-injection`: roughly 30 percent HTTP 500 responses.
     Watch `error-rate-by-service` (Demo Errors and Alerts),
     `request-rate-and-errors` (Demo Service Overview), and
     `error-log-stream` (Demo Logs Explorer); risk scoring and
     assisted RCA must pick up the error burst.
   - `latency-injection`: roughly 800 ms injected latency. Watch
     `p95-latency-by-route` and `slow-trace-waterfall` (Demo Latency
     and Traces) and `latency-percentiles` (Demo Service Overview);
     assisted RCA must surface the latency shift.

4. Return to baseline after a fault drill:

   ```bash
   kubectl -n tenant-demo set env deployment/demo-loadgen \
     DEMO_SCENARIO=steady-baseline
   ```

## Verification

- Pods: everything in `tenant-demo` is `Running`, and the CronJob
  completes every 5 minutes.

  ```bash
  kubectl get pods -n tenant-demo
  ```

- Telemetry arriving: the loadgen log shows the active scenario, and
  the collector gateway shows no export errors.

  ```bash
  kubectl logs -n tenant-demo deployment/demo-loadgen --tail=20
  kubectl logs -n observability deployment/otel-gateway --tail=50
  ```

- Dashboards: the four `DEMO_*` dashboards render demo data filtered
  to `tenant_id: demo` in namespace `tenant-demo`.
- AI answer: paste one read-path prompt from
  `demo/prompts/AI_PROMPT_PACK.md` into the kagent chat surface and
  confirm a scoped, non-empty answer.

## Teardown Drill

1. Remove the demo:

   ```bash
   bash demo/teardown.sh
   ```

2. Confirm removal and platform integrity:

   ```bash
   kubectl get namespace tenant-demo
   kubectl -n observability get pods
   ```

   The namespace reports `NotFound`; platform pods are untouched.

## Troubleshooting

| Symptom | Cause | Fix |
| ---- | ---- | ---- |
| Pods in `ErrImagePull` or `ImagePullBackOff` | Image not loaded into the cluster | Rebuild and reload: `docker build -t ghcr.io/obskit/demo:0.1.0 demo/services`, then `kind load docker-image` for kind clusters |
| Loadgen runs but no telemetry appears | Collector unreachable | Verify `otel-gateway.observability.svc.cluster.local:4318` resolves and the Service exposes `otlp-http`; check gateway logs |
| Loadgen pod exits non-zero at startup | Scenario document invalid | Read the printed error list; validate against `contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json` (`tests/demo/test_demo_scenarios.py` runs the same validation) |
| Workload rejected at admission | Kyverno denial: missing `service.name`, `deployment.environment`, or `service.owner` labels | Restore the labels in `demo/gitops/base/`; they are admission-required by the Batch 8 policies |

## References

- `docs/product/PLAYGROUND_GUIDE.md` - evaluator-facing walkthrough.
- `docs/adr/ADR_0011_DEMO_PLAYGROUND_ARCHITECTURE.md` - gated
  architecture decisions and the sizing budget.
- `demo/SCENARIOS.md` - full scenario reference and authoring guide.
- `demo/README.md` - package layout, deploy, and teardown.
- `scripts/ci/validate_demo_playground.sh` - the Batch 27 structural
  validator.
