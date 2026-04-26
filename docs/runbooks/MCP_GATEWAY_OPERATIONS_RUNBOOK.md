# MCP Gateway Operations Runbook

This runbook covers operations for the MCP gateway and the MCP service
catalog (Batch 14). Cloud-agnostic — applies to any conformant Kubernetes
cluster.

## Scope

The MCP gateway fronts every MCP service exposed to agents. It enforces
explicit registration, heartbeat health, request timeouts, and a
deny-on-failover posture. Direct backend discovery is disabled.

Related contracts:

- `contracts/mcp/MCP_CATALOG_V1.yaml`
- `contracts/mcp/TOOL_RESPONSE_SCHEMA_V1.json`
- `contracts/mcp/GATEWAY_DISCOVERY_CONTRACT_V1.yaml`
- `contracts/mcp/TENANCY_REDACTION_RULES_V1.yaml`
- `contracts/policy/IDENTITY_ACCESS_MATRIX_V1.yaml`

Related dashboards/alerts:

- `gitops/platform/search/dashboards/saved-objects/MCP_GATEWAY_HEALTH.ndjson`
- `gitops/platform/search/dashboards/alerts/mcp_health_rules.ndjson`

## Service Catalog

Per `MCP_CATALOG_V1.yaml`, the catalog is the source of truth for which MCP
services exist:

- `incident-search-mcp`
- `graph-analysis-mcp`
- `trace-investigation-mcp`
- `metrics-correlation-mcp`
- `change-intelligence-mcp`
- `runbook-execution-mcp`
- `incident-casefile-mcp`

Identity bindings for all seven services are defined in
`IDENTITY_ACCESS_MATRIX_V1.yaml`.

## Symptom 1: gateway unhealthy / unavailable

1. Confirm via `mcp_gateway_unavailable` alert or the
   `mcp-gateway-request-rate` panel that the gateway is reporting
   unhealthy.
2. Inspect the gateway pod logs in the `ai-gateway` namespace.
3. Check heartbeat state: per `GATEWAY_DISCOVERY_CONTRACT_V1.yaml`, the
   gateway considers a registered service unhealthy after
   `unhealthy_threshold_missed_heartbeats` (default 3) consecutive missed
   heartbeats. Confirm whether it is the gateway itself or a registered
   downstream service that is degraded.
4. If only one downstream is unhealthy, the gateway will remove it from
   the catalog and emit an audit event. Other services continue to serve.
5. Verify the gateway's NetworkPolicy is intact:
   `gitops/platform/ai/base/gateway/networkpolicy.yaml`.

## Symptom 2: tool latency p95 high

The performance contract sets the upper bound at 750ms p95 per
`PERF_UPGRADE_SUITE_V1.json`.

1. Identify the offending tool from the `mcp-tool-latency` panel.
2. Inspect the underlying MCP service deployment in `mcp-system` namespace.
3. Check whether the service is hitting CPU or connection-pool limits.
4. If the upstream OpenSearch / Neo4j / event source is the actual
   bottleneck, follow the corresponding tier's runbook.
5. Per `GATEWAY_DISCOVERY_CONTRACT_V1.yaml.timeout_policy`, requests above
   `upper_bound_request_timeout_ms` (30000) are denied; verify that
   `default_request_timeout_ms` (5000) has not been raised inadvertently.

## Symptom 3: tool response schema validation failure

1. Confirm the `mcp_tool_schema_validation_failures` alert.
2. Inspect the response payload from the offending tool.
3. Compare the actual response shape to `TOOL_RESPONSE_SCHEMA_V1.json`.
4. If the MCP service is at fault, file an issue against the service owner
   declared in `MCP_CATALOG_V1.yaml`.
5. If the schema is wrong, propose a schema change in a PR; the
   `validate_mcp_contracts.sh` validator will guard against breaking
   changes.

## Symptom 4: tenancy isolation verification

1. Inspect `TENANCY_REDACTION_RULES_V1.yaml` for the active redaction
   profile per service.
2. Use the `mcp-tenancy-redaction-events` panel to spot anomalies (e.g.,
   tenant A receiving redaction events on tool calls scoped to tenant B).
3. Cross-reference with the audit log for the offending request id.
4. If isolation is breached, follow the security incident response in
   `docs/runbooks/SECURITY_ISOLATION_RESILIENCE_OPERATOR_GUIDE.md`.

## Failover and Recovery

Per `GATEWAY_DISCOVERY_CONTRACT_V1.yaml.failover_policy`:

- `fallback_mode: deny` — when the primary path fails, requests are denied
  rather than retried against an unprotected backend.
- `retry_attempts: 0` — no automatic retries.
- `notify_on_failover: true` — failover emits an audit event consumed by
  the alerting layer.

To recover after a degraded period, validate that:

1. All registered services are emitting heartbeats again.
2. Gateway logs show clean reconnect events.
3. End-to-end: invoke a known read tool (e.g.,
   `incident-search.v1`) and confirm it returns within
   `default_request_timeout_ms`.

## Validation Commands

```bash
bash scripts/ci/validate_mcp_contracts.sh
bash scripts/ci/validate_mcp_read_path_scaffolding.sh
bash scripts/ci/validate_kagent_khook_release.sh
bash scripts/ci/validate_batch14_smoke.sh
```
