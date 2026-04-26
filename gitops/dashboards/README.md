# Dashboards Baseline

This directory establishes the dashboards-as-code contract for the platform.
The directory contract was set in Batch 1; dashboard content is delivered
incrementally by later batches.

Authoritative dashboards live alongside the search-stack manifests so they
ship with the same ArgoCD Application as the OpenSearch / OpenSearch
Dashboards deployment.

## Where the dashboards live

All saved-object dashboards are under
`gitops/platform/search/dashboards/saved-objects/`. The current set:

| Dashboard                       | Batch | Source                                              |
| ------------------------------- | ----- | --------------------------------------------------- |
| `COLLECTOR_HEALTH.ndjson`       | 4     | OpenTelemetry collector pipeline health             |
| `LOGS_OPERATIONS.ndjson`        | 5     | Logs ingest, retention, and query SLOs              |
| `METRICS_TRACES_OVERVIEW.ndjson`| 6     | Metrics + traces correlation views                  |
| `SERVICE_OVERVIEW.ndjson`       | 6     | Per-service golden signals                          |
| `PLATFORM_OVERVIEW.ndjson`      | 9     | Operator-experience platform overview               |
| `GOVERNANCE_OVERVIEW.ndjson`    | 9A    | Visualization + admin access plane                  |
| `VECTOR_FOUNDATIONS.ndjson`     | 10    | Vector index health and recall metrics              |
| `GRAPH_FOUNDATION.ndjson`       | 11    | Neo4j derived-graph topology + sync lag             |
| `RCA_AUDIT_OVERVIEW.ndjson`     | 12    | Risk score quantiles + assisted-RCA outcomes        |
| `AI_RUNTIME_HEALTH.ndjson`      | 14    | AI agents, casefile lifecycle, KAgent persistence   |
| `MCP_GATEWAY_HEALTH.ndjson`     | 14    | MCP gateway, per-tool latency, error budgets        |

Per-environment overlays are not yet split out — all environments load the
same saved objects. When per-environment threshold tuning is required, copy
the relevant ndjson into an environment-scoped subdirectory and reference it
from the corresponding `gitops/overlays/<env>/` overlay.

## How to add a dashboard

1. Export the dashboard from OpenSearch Dashboards as an `.ndjson` saved
   object.
2. Place the file under `gitops/platform/search/dashboards/saved-objects/`.
3. Update this README's table.
4. Rerun `bash scripts/ci/validate_visualization_admin_access.sh`.

## Validation

`scripts/ci/validate_visualization_admin_access.sh` enforces presence of the
core dashboard set and shape conformance for the saved-object envelope.
