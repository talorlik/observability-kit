# Alerts Baseline

This directory establishes the alerts-as-code contract for the platform.
The directory contract was set in Batch 1; alert content is delivered
incrementally by later batches.

Authoritative alert rules ship next to the search-stack manifests so they
are deployed by the same ArgoCD Application as the OpenSearch / Dashboards
deployment.

## Where the alert rules live

All saved-object alert bundles are under
`gitops/platform/search/dashboards/alerts/`. The current set:

| Bundle                              | Batch | Signals covered                                            | Runbook                                                                  |
| ----------------------------------- | ----- | ---------------------------------------------------------- | ------------------------------------------------------------------------ |
| `slo_burn_rate_rules.ndjson`        | 9     | Multi-window SLO burn (fast / slow), symptom latency       | `docs/runbooks/OPERATOR_EXPERIENCE_SLO_OPERATIONS_GUIDE.md`              |
| `platform_health_rules.ndjson`      | 9     | Collector pipeline health, queue saturation                | `docs/runbooks/COLLECTOR_CORE_TOPOLOGY_OPERATOR_GUIDE.md`                |
| `vector_graph_health_rules.ndjson`  | 10/11 | Vector index recall, Neo4j sync lag                        | `docs/runbooks/VECTOR_FOUNDATIONS_OPERATOR_GUIDE.md`                     |
| `approval_flow_rules.ndjson`        | 14    | Approval timeouts, pending-approval queue depth            | `docs/runbooks/AI_APPROVAL_FLOW_RUNBOOK.md`                              |
| `mcp_health_rules.ndjson`           | 14    | MCP gateway error rate, per-tool latency, quota exhaustion | `docs/runbooks/MCP_GATEWAY_OPERATIONS_RUNBOOK.md`                        |

Every alert rule should carry a `tags: ["runbook:<path>"]` reference to the
operator guide that documents triage steps. The validators do not parse the
tag, but the convention is enforced at review.

Per-environment overlays are not yet split out — every environment receives
the same thresholds. When per-environment tuning is required, copy the
relevant ndjson into an environment-scoped subdirectory and reference it
from the corresponding `gitops/overlays/<env>/` overlay.

## How to add an alert rule

1. Define the rule in OpenSearch Dashboards / Alerting and export it as a
   saved-object `.ndjson`.
2. Place it under `gitops/platform/search/dashboards/alerts/`.
3. Add a `runbook:` tag pointing to the matching operator guide.
4. Update this README's table.
5. Rerun `bash scripts/ci/validate_visualization_admin_access.sh`.
