# Demo Services Signal Inventory

This file is the handoff contract between the demo services (Batch
27, Task 2) and the downstream demo surfaces: the dashboards task
consumes the metric names, attributes, and log conventions listed
here, and the AI prompt pack task binds its prompts to these exact
field names. Changing any name here is a breaking change for both.

All signals are emitted by the stdlib OTLP/HTTP JSON emitter
(`demo/services/demosvc/otel.py`) to the platform gateway collector
at the `OTEL_EXPORTER_OTLP_ENDPOINT` env value (default
`http://otel-gateway.observability.svc.cluster.local:4318`), paths
`/v1/logs`, `/v1/metrics`, `/v1/traces`. No demo component writes to
OpenSearch or Neo4j directly (TR-02, TR-07).

## Resource Attributes (Every Export, Every Service)

- `service.name` - one of `demo-http-api`, `demo-worker`,
  `demo-scheduled-job`, `demo-datastore`, `demo-loadgen`.
- `service.version` - `0.1.0` (env `DEMO_SERVICE_VERSION`).
- `deployment.environment` - `dev` (env `DEMO_ENVIRONMENT`).
- `service.owner` - `team-demo` (env `DEMO_OWNER`).
- `tenant_id` - `demo` (env `DEMO_TENANT_ID`). This is the tenant
  routing attribute: `contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.
  yaml` fixes `tenant_id` as the field stamped at ingest by the
  collector routing layer, embedded in the per-tenant index patterns
  (`tenant-<tenant_id>-<signal>-*`), and used verbatim in the
  document-level security filter
  (`{"term": {"tenant_id": "<tenant_id>"}}`) for the demo tenant's
  `shared-partition` isolation class. Emitting it as a resource
  attribute lets the routing layer honor it without inference.

Dashboards filter on `service.name`, `deployment.environment`, and
`tenant_id`; the AI prompts scope every query with
`tenant_id: demo`.

## Trace Conventions (All Services)

- W3C `traceparent` (`00-<32-hex trace id>-<16-hex span id>-01`) is
  extracted from incoming requests and propagated on every outgoing
  HTTP call, so load generator, HTTP API, datastore, worker, and
  scheduled job share traces end to end.
- Span status: OTLP code `2` (error) with a message on faults and
  transport failures, code `1` otherwise.
- Histogram bucket boundaries are latency-in-ms oriented: 1, 2, 5,
  10, 25, 50, 100, 250, 500, 1000, 2500, 5000.

## demo-http-api

Signal types: logs, metrics, traces. Port 8080. Routes:
`/api/orders` (POST, GET), `/api/queue` (GET poll, POST ack),
`/api/status`, `/healthz` (probe only, not instrumented).

Spans:

- `<METHOD> <route>` - kind SERVER, one per request. Attributes:
  `http.request.method`, `http.route`, `url.path`,
  `http.response.status_code`; on injected faults additionally
  `demo.fault_injected` (bool) and error status; on injected latency
  `demo.injected_latency_ms`.
- `<METHOD> /orders` - kind CLIENT, child of the SERVER span, one
  per datastore call. Attributes: `http.request.method`, `url.full`,
  `peer.service` = `demo-datastore`, `http.response.status_code`.

Metrics:

- `demo.http.requests` (counter) - attributes `http.route`,
  `http.request.method`, `http.response.status_code`. Dashboards:
  request rate and error-rate panels; AI prompts: error-ratio
  queries for risk scoring.
- `demo.http.server.duration` (histogram, ms) - attribute
  `http.route`. Dashboards: latency percentiles; AI prompts: latency
  regression questions.
- `demo.queue.depth` (histogram, gauge-style observation) - no
  attributes. Dashboards: queue backlog panel; AI prompts: backlog
  vs worker-throughput correlation.

Logs:

- INFO per request: `<METHOD> <route> -> <status>` with
  `http.route`, `http.response.status_code`, trace-correlated.
- ERROR on injected faults: `injected fault on <METHOD> <route>`
  with `http.route`, `http.response.status_code`,
  `demo.fault_ratio`, trace-correlated. The error-injection scenario
  relies on these for the RCA surfaces.

Fault injection headers honored (sent by the load generator):
`x-demo-fault-ratio` (float 0..1, probability of a 500 plus error
span and ERROR log) and `x-demo-latency-ms` (int, added delay before
responding, capped at 30000).

## demo-worker

Signal types: logs, metrics, traces. Polls
`http://demo-http-api:8080/api/queue` (env `DEMO_HTTP_API_URL`)
every `DEMO_WORKER_POLL_SECONDS` (default 5) seconds.

Spans:

- `GET /api/queue` / `POST /api/queue` - kind CLIENT, poll and ack
  calls. Attributes: `http.request.method`, `url.full`,
  `peer.service` = `demo-http-api`, `http.response.status_code`.
- `demo.worker.process` - kind CONSUMER, one per queue item,
  continuing the trace stored with the item (the producing request's
  traceparent). Attributes: `demo.queue.item_id`, `demo.order_id`.

Metrics:

- `demo.worker.processed` (counter) - attribute `worker.outcome`
  (`ok` or `poll-error`). Dashboards: throughput panel; AI prompts:
  backlog correlation.
- `demo.worker.duration` (histogram, ms) - no attributes.
  Dashboards: processing-time panel.

Logs: INFO per processed item (`demo.queue.item_id`,
trace-correlated); ERROR on poll or ack failure (`worker.phase` =
`poll` or `ack`).

## demo-scheduled-job

Signal types: logs, metrics, traces. CronJob, every 5 minutes; each
run is a new root trace and the process exits 0 regardless of check
outcome (a degraded run is telemetry, not a pod failure).

Spans:

- `demo.job.run` - kind INTERNAL, root of the run. Attributes:
  `job.name` = `demo-scheduled-job`, `job.outcome` (`ok` or
  `degraded`); error status when degraded.
- `GET /api/status`, `GET /api/orders` - kind CLIENT, children of
  the root. Attributes: `http.request.method`, `url.full`,
  `peer.service` = `demo-http-api`, `http.response.status_code`.

Metrics:

- `demo.job.runs` (counter) - attribute `job.outcome`. Dashboards:
  run-cadence and success panel; AI prompts: "did the scheduled job
  degrade during the incident window" questions.

Logs: one summary INFO per run (`job.outcome`,
`job.checks_passed`, trace-correlated); ERROR per failed check
(`job.check`).

## demo-datastore

Signal types: logs, metrics, traces. Port 8081, SQLite at
`DEMO_DB_PATH` (default `/tmp/demo.db`), `orders` table. Routes:
`/orders` (POST, GET), `/status`, `/healthz` (probe only).

Spans:

- `<METHOD> <route>` - kind SERVER, continuing the caller's
  traceparent. Attributes: `http.request.method`, `http.route`,
  `http.response.status_code`.
- `sqlite.<operation> orders` - kind CLIENT, one per SQL statement,
  child of the SERVER span. Attributes: `db.system` = `sqlite`,
  `db.operation.name` (`CREATE`, `INSERT`, `SELECT`),
  `db.query.text` (the literal parameterized SQL),
  `db.collection.name` = `orders`, `db.namespace` (the db path).
  These give the graph tier and RCA surfaces a genuine database
  dependency edge.

Metrics:

- `demo.db.operations` (counter) - attribute `db.operation.name`.
  Dashboards: datastore operation-rate panel.
- `demo.db.duration` (histogram, ms) - attribute
  `db.operation.name`. Dashboards: db latency panel; AI prompts:
  "is the datastore the bottleneck" questions.
- `demo.http.requests` / `demo.http.server.duration` - same
  conventions as demo-http-api, for the datastore's own HTTP
  surface.

Logs: INFO per request and ERROR on `sqlite3` failures, both
trace-correlated with `http.route`.

## demo-loadgen

Implemented in `demosvc/loadgen.py`. It codes against the emitter
API in this package and the fault headers above; its scenario
documents are validated by
`contracts/demo/DEMO_SCENARIO_SCHEMA_V1.json`. Resource attributes
follow this file.

Traces: one root `demo.loadgen.request` CLIENT span per request,
with `http.request.method`, `url.full`,
`http.response.status_code`, and the scenario name as
`demo.scenario` (plus `demo.scenario.kind`); the `traceparent`
header propagates the context
into demo-http-api, so every demo trace starts here.

Metrics:

- `demo.loadgen.requests` (counter) - attributes `demo.scenario`,
  `http.response.status_code`.
- `demo.loadgen.duration` (histogram, ms) - end-to-end client
  latency per request, attribute `demo.scenario`.

Logs: periodic INFO heartbeat with the active scenario and request
counters; ERROR on scenario-load failure before exit.
