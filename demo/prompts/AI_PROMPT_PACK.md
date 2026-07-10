# Demo AI Playground Prompt Pack

Ready-to-use prompts for exercising the AI/MCP layer against the demo
playground. Every prompt is bound to actual MCP catalog tools from
`contracts/mcp/MCP_CATALOG_V1.yaml` and to the demo traffic scenario
that produces the data it needs, so tool calls return grounded answers
against captured demo telemetry instead of empty results.

## Table of Contents

- [How to Use This Pack](#how-to-use-this-pack)
- [Prompt Format](#prompt-format)
- [Service Health](#service-health)
- [Log Investigation](#log-investigation)
- [Trace Investigation](#trace-investigation)
- [Fault RCA (error-injection)](#fault-rca-error-injection)
- [Fault RCA (latency-injection)](#fault-rca-latency-injection)
- [Casefile Follow-Up](#casefile-follow-up)

## How to Use This Pack

1. Deploy the demo package (`demo/README.md`) and select the scenario
   named by the prompt via the `DEMO_SCENARIO` environment variable on
   the `demo-loadgen` Deployment (see `demo/SCENARIOS.md`).
2. Let the scenario run for 10-15 minutes so the signals listed in
   `demo/services/SIGNAL_INVENTORY.md` are captured by the platform.
3. Paste the prompt text into the AI/kagent surface (the agent chat
   exposed by the AI runtime, `gitops/platform/ai/`).
4. All demo telemetry is scoped to `tenant_id` `demo` in namespace
   `tenant-demo`; the prompts carry that scope explicitly so tenancy
   redaction and isolation behave exactly as in production.

Read-path tools (`incident-search`, `graph-analysis`,
`trace-investigation`, `metrics-correlation`, `change-intelligence`,
and the casefile read operation of `incident-casefile`) run without
approval per `contracts/policy/TOOL_RISK_CLASSIFICATION_V1.yaml`. The
pack is read-path by default: only the final Casefile Follow-Up
section performs a write, and that call is governed by the approval
flow in `contracts/policy/APPROVAL_FLOW_V1.yaml` unchanged - policy is
evaluated before the write, missing preconditions deny it, and
denials are fed back into the casefile.

> [!NOTE]
> No prompt in this pack invokes `runbook-execution` or any
> higher-risk write tool. Those remain gated by human approval,
> timeout, and escalation rules that the playground does not relax.

## Prompt Format

Each prompt is a `###` heading followed by three metadata lines and a
fenced block with the paste-ready text:

- `Tools:` - verbatim tool names from
  `contracts/mcp/MCP_CATALOG_V1.yaml` the prompt exercises.
- `Scenario:` - the one demo scenario
  (`demo/gitops/base/scenarios/<name>.json`) that produces the data.
- `Path:` - `read`, or `write (approval flow)` for the single
  write-path prompt.

The format is machine-checked by `tests/demo/test_demo_prompts.py`;
keep it exact when adding prompts.

## Service Health

### Baseline Service Health Summary

- Tools: `metrics-correlation`
- Scenario: `steady-baseline`
- Path: read

```text
Using telemetry for tenant_id demo in namespace tenant-demo, summarize
the current health of demo-http-api, demo-datastore, demo-worker, and
demo-scheduled-job. Correlate the demo.http.requests counter (split by
http.response.status_code) with the demo.http.server.duration
histogram for route /api/orders over the last 30 minutes, and confirm
the steady-baseline scenario is producing about 2 requests per second
with a near-zero error ratio. Flag any service whose signals deviate
from that baseline.
```

### Burst Window Throughput Check

- Tools: `metrics-correlation`
- Scenario: `burst`
- Path: read

```text
For tenant_id demo, correlate demo.loadgen.requests (attribute
demo.scenario = burst) with demo.http.requests on demo-http-api over
the last hour. The burst scenario raises throughput five-fold for 20
seconds every 120 seconds; confirm the periodic burst windows are
visible, check whether demo.http.server.duration for /api/orders
degrades inside the windows, and report whether demo.queue.depth on
demo-http-api grows faster than demo.worker.processed drains it during
the bursts.
```

### Scheduled Job and Worker Health

- Tools: `incident-search`, `metrics-correlation`
- Scenario: `steady-baseline`
- Path: read

```text
Search recent logs for tenant_id demo in namespace tenant-demo from
demo-scheduled-job and demo-worker. Using demo.job.runs (attribute
job.outcome) confirm the CronJob completes every 5 minutes with
outcome ok, and using demo.worker.processed (attribute worker.outcome)
confirm the worker is draining the queue. Surface any ERROR logs
carrying job.check or worker.phase attributes and state whether the
steady-baseline picture is healthy.
```

## Log Investigation

### Injected Fault Error Log Triage

- Tools: `incident-search`
- Scenario: `error-injection`
- Path: read

```text
Search logs for tenant_id demo, service demo-http-api, severity ERROR
over the last 15 minutes. The error-injection scenario answers roughly
30 percent of requests with HTTP 500, and each injected failure logs
"injected fault on GET /api/orders" with attributes http.route,
http.response.status_code, and demo.fault_ratio. Group the hits by
http.route, report the observed error ratio against the configured
demo.fault_ratio of 0.3, and list three sample trace-correlated log
entries I can pivot into traces.
```

### Cross-Service Log Sweep During Bursts

- Tools: `incident-search`
- Scenario: `burst`
- Path: read

```text
For tenant_id demo in namespace tenant-demo, sweep logs across
demo-http-api, demo-worker, and demo-datastore during the most recent
burst window. Look for ERROR entries with worker.phase (poll or ack
failures) and for any datastore sqlite3 failure logs, then compare the
INFO request log volume on demo-http-api ("GET /api/orders -> 200")
inside versus outside the 20-second burst windows. Tell me whether the
burst produced errors or only elevated volume.
```

## Trace Investigation

### Slow Trace Waterfall Walkthrough

- Tools: `trace-investigation`
- Scenario: `latency-injection`
- Path: read

```text
Find the slowest traces in the last 15 minutes for tenant_id demo
whose root span is demo.loadgen.request. Walk one waterfall end to
end: the SERVER span GET /api/orders on demo-http-api should carry
demo.injected_latency_ms = 800, with a fast child CLIENT span to
peer.service demo-datastore and its sqlite.SELECT orders span beneath.
Quantify how much of the end-to-end demo.loadgen.duration is spent
inside demo-http-api versus demo-datastore and name the exact span
where the injected latency sits.
```

### Order Flow Dependency Map

- Tools: `trace-investigation`, `graph-analysis`
- Scenario: `steady-baseline`
- Path: read

```text
Using traces for tenant_id demo, reconstruct the full order flow: the
demo.loadgen.request root span into GET /api/orders on demo-http-api,
the CLIENT call to peer.service demo-datastore with its sqlite.INSERT
and sqlite.SELECT orders spans (db.system = sqlite,
db.collection.name = orders), and the demo.worker.process CONSUMER
span that continues the producing request's trace with
demo.queue.item_id and demo.order_id. Confirm the derived service
graph shows demo-loadgen -> demo-http-api -> demo-datastore plus the
worker edge, and call out any dependency edge that is missing.
```

## Fault RCA (error-injection)

### Risk Scoring the Error Burst

- Tools: `metrics-correlation`, `incident-search`
- Scenario: `error-injection`
- Path: read

```text
Build the risk-scoring picture for the current error burst on
tenant_id demo. From demo.http.requests on demo-http-api, compute the
ratio of http.response.status_code 500 to total for route /api/orders
over the last 15 minutes (expected near the injected 0.3), correlate
it with the ERROR log volume carrying demo.fault_ratio, and check
demo.job.runs for degraded scheduled-job outcomes in the same window.
Summarize which signals should drive the risk score for this incident
and how severe you judge it to be.
```

### Assisted RCA for the 500 Spike

- Tools: `incident-search`, `trace-investigation`, `graph-analysis`
- Scenario: `error-injection`
- Path: read

```text
Perform an assisted RCA for the elevated 500 rate on demo-http-api
(tenant_id demo, namespace tenant-demo). Pull error traces whose
SERVER span GET /api/orders carries demo.fault_injected = true,
inspect the child spans to demo-datastore to confirm the datastore is
answering normally, and search the trace-correlated ERROR logs
("injected fault on GET /api/orders"). Use the dependency graph to
rule upstream and downstream services in or out, then state the root
cause hypothesis: the fault is injected inside demo-http-api by the
x-demo-fault-ratio header, not caused by its dependencies.
```

## Fault RCA (latency-injection)

### Risk Scoring the Latency Regression

- Tools: `metrics-correlation`
- Scenario: `latency-injection`
- Path: read

```text
Assess the risk-scoring inputs for the latency regression on tenant_id
demo. Compare the demo.http.server.duration histogram for route
/api/orders on demo-http-api before and after the latency-injection
scenario started - p95 should shift by roughly the injected 800 ms -
and correlate with demo.loadgen.duration for demo.scenario =
latency-injection to confirm clients observe the same shift. Verify
demo.http.requests shows no error-rate change, so this scores as a
pure latency incident, and recommend a severity.
```

### Assisted RCA for the Latency Shift

- Tools: `trace-investigation`, `metrics-correlation`, `change-intelligence`
- Scenario: `latency-injection`
- Path: read

```text
Run an assisted RCA on the p95 latency shift for GET /api/orders
(tenant_id demo). From slow traces, decide whether the time sits in
demo-http-api or demo-datastore: the SERVER span carries
demo.injected_latency_ms while demo.db.duration and the sqlite.SELECT
orders spans stay flat, which rules the datastore out as the
bottleneck. Correlate demo.http.server.duration against
demo.db.duration to confirm, then check recent change intelligence for
deployments or configuration changes to demo-http-api in namespace
tenant-demo that coincide with the shift, and state the root cause.
```

## Casefile Follow-Up

This section demonstrates the write path. The casefile read operation
(`incident-casefile.read.v1`) is read-path and needs no approval; the
casefile update operation (`incident-casefile.update.v1`, risk class
`write.low-risk`) is the only write this pack performs and it routes
through the approval flow per `contracts/policy/APPROVAL_FLOW_V1.yaml`
unchanged.

### Casefile Context Review

- Tools: `incident-casefile`
- Scenario: `error-injection`
- Path: read

```text
Open the incident casefile for the current error-injection exercise on
tenant_id demo and summarize what has been captured so far: the
risk-scoring inputs, the assisted-RCA hypothesis that demo-http-api
injects faults via the x-demo-fault-ratio header, and any linked
evidence such as ERROR logs with demo.fault_ratio or traces with
demo.fault_injected = true. List what evidence is still missing before
the casefile can be closed. Use only the read side of the casefile
tool for this review.
```

### Casefile Follow-Up Note

- Tools: `incident-casefile`
- Scenario: `error-injection`
- Path: write (approval flow)

```text
Append a follow-up note to the incident casefile for the
error-injection exercise on tenant_id demo: record that the observed
500 ratio on GET /api/orders matched the configured demo.fault_ratio
of 0.3, that traces with demo.fault_injected = true localized the
fault to demo-http-api, and that demo-datastore was ruled out. This is
the write-path casefile update (incident-casefile.update.v1, risk
class write.low-risk) and it is governed by the approval flow in
contracts/policy/APPROVAL_FLOW_V1.yaml unchanged: policy must allow
the write before execution, missing preconditions deny it, and any
denial is fed back into the casefile. Do not invoke any higher-risk
write tool as part of this follow-up.
```
