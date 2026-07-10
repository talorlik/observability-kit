# Demo Traffic Scenarios

The demo load generator (`demo-loadgen`, the `loadgen` entrypoint of
the `ghcr.io/obskit/demo` image) executes exactly one declarative
scenario document per run. The four shipped documents live in
`demo/gitops/base/scenarios/` and are mounted into the pod at
`/etc/demo/scenarios` from the `demo-scenarios` ConfigMap. Every
document is validated against
`contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json` before any traffic is
sent; an invalid document makes the generator exit non-zero with the
full error list instead of running a half-configured load.

Fault injection never fakes telemetry: the generator only attaches the
`x-demo-fault-ratio` and `x-demo-latency-ms` request headers derived
from the scenario `fault` block, and the demo HTTP API honors them
server-side. All requests carry a fresh W3C `traceparent`, so every
injected fault is observable end to end as a real distributed trace.

## Selecting a Scenario

Scenario selection is the `DEMO_SCENARIO` environment variable on the
`demo-loadgen` Deployment. The value is the document filename without
the `.json` suffix: `steady-baseline` (default), `burst`,
`error-injection`, or `latency-injection`.

Imperatively, for a quick switch on a running playground:

```bash
kubectl -n tenant-demo set env deployment/demo-loadgen \
  DEMO_SCENARIO=burst
```

Declaratively, for GitOps-managed environments, patch the Deployment
in a kustomize overlay instead of editing live state:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: demo-loadgen
  namespace: tenant-demo
spec:
  template:
    spec:
      containers:
        - name: demo-loadgen
          env:
            - name: DEMO_SCENARIO
              value: error-injection
```

The target base URL comes from the environment variable named by
`target.base_url_env` (default `DEMO_TARGET_BASE_URL`, falling back to
`http://demo-http-api:8080` when unset). The `target.route` values
below assume the demo HTTP API; edit the scenario document to point at
a different route.

## steady-baseline

Gentle continuous load that keeps every dashboard, tenancy, and
metering surface populated with healthy telemetry.

- Schema fields used: `schema_version`, `name`, `kind`, `description`,
  `target` (`base_url_env`, `route`, `method`), and `load`
  (`requests_per_second: 2`, `concurrency: 2`,
  `duration_seconds: 0` - run forever).
- No `burst`, `fault`, or `expectations` blocks: the schema forbids
  them for this kind.
- Select it with `DEMO_SCENARIO=steady-baseline` (the Deployment
  default).

## burst

Baseline load with a periodic burst window so throughput panels and
usage metering show realistic variation instead of a flat line.

- Schema fields used: everything from `steady-baseline` plus the
  required `burst` block (`interval_seconds: 120`,
  `burst_seconds: 20`, `burst_multiplier: 5`).
- Every 120 seconds the generator runs the first 20 seconds at five
  times the baseline `requests_per_second`, then returns to baseline.
- Select it with `DEMO_SCENARIO=burst`.

## error-injection

Steady load in which roughly 30 percent of requests are answered with
HTTP 500 by the demo HTTP API, driven by the `x-demo-fault-ratio`
header derived from `fault.error_ratio: 0.3`.

- Schema fields used: the baseline fields plus the required `fault`
  block (`error_ratio: 0.3`) and the required `expectations` block
  naming the surfaces below.
- Select it with `DEMO_SCENARIO=error-injection`.

It is expected to light up the following surfaces, mirroring the
scenario document's `expectations` arrays:

| Type | Surface |
| --- | --- |
| Dashboard panel | `DEMO_ERRORS_ALERTS/error-rate-by-service` |
| Dashboard panel | `DEMO_SERVICE_OVERVIEW/request-rate-and-errors` |
| Dashboard panel | `DEMO_LOGS_EXPLORER/error-log-stream` |
| AI surface | `risk-scoring` |
| AI surface | `assisted-rca` |
| AI surface | `mcp:incident-search` |

## latency-injection

Steady load in which the demo HTTP API adds roughly 800 milliseconds
of server-side latency to each request, driven by the
`x-demo-latency-ms` header derived from `fault.latency_ms: 800`.

- Schema fields used: the baseline fields plus the required `fault`
  block (`latency_ms: 800`) and the required `expectations` block
  naming the surfaces below.
- Select it with `DEMO_SCENARIO=latency-injection`.

It is expected to light up the following surfaces, mirroring the
scenario document's `expectations` arrays:

| Type | Surface |
| --- | --- |
| Dashboard panel | `DEMO_LATENCY_TRACES/p95-latency-by-route` |
| Dashboard panel | `DEMO_LATENCY_TRACES/slow-trace-waterfall` |
| Dashboard panel | `DEMO_SERVICE_OVERVIEW/latency-percentiles` |
| AI surface | `risk-scoring` |
| AI surface | `assisted-rca` |
| AI surface | `mcp:trace-investigation` |
| AI surface | `mcp:metrics-correlation` |

## Writing a New Scenario

Copy one of the shipped documents, keep `schema_version: "v1"`, and
validate before shipping: the schema is
`contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json`, with valid and
seeded-invalid samples under `contracts/demo/samples/`. The offline
test `tests/demo/test_demo_scenarios.py` runs the same validation the
generator applies at startup.
