# AI / MCP Layer Operator Guide (Batch 14)

This guide is the parent operator runbook for the AI / MCP runtime layer
delivered by Batch 14. The Batch 14 layer is a higher-order tier on top of
the platform delivered by Batches 1-13: it adds agents, an MCP gateway,
KAgent persistence, KHook triggers, and an approval-gated action layer.

For day-to-day operational concerns, drill into the focused runbooks:

| Concern                                | Runbook                                            |
| -------------------------------------- | -------------------------------------------------- |
| Approval-gated action flow             | `AI_APPROVAL_FLOW_RUNBOOK.md`                      |
| MCP gateway health and per-tool quota  | `MCP_GATEWAY_OPERATIONS_RUNBOOK.md`                |
| Case-file lifecycle and replay         | `CASEFILE_REVIEW_RUNBOOK.md`                       |
| KHook trigger dedupe / burst control   | `KHOOK_TROUBLESHOOTING_RUNBOOK.md`                 |

## Scope

The AI / MCP layer is composed of:

- **Agents** (`agents/catalog/`, `agents/policies/`, `agents/prompts/`):
  catalog, role definitions, prompt fragments, and policy bindings.
- **MCP services** (`services/mcp/`): a read-path bundle (incident-search,
  graph-analysis, trace-investigation, metrics-correlation,
  change-intelligence), a case-file service, and a runbook-execution
  write-path service with an action journal.
- **Triggers** (`triggers/khook/`): KHook triggers with dedupe / burst
  policies and a read-only dispatch boundary.
- **Pipelines** (`pipelines/risk/`, `pipelines/vector/`): risk scoring and
  vector retrieval pipeline definitions consumed by the read-path.
- **GitOps** (`gitops/platform/ai/base/`): namespaces, network policies,
  KAgent persistence (Postgres) and the deployments for all the above.

## Pre-checks

Before operating on the AI / MCP layer, confirm:

1. The platform delivered by Batches 1-13 is healthy. Run
   `bash scripts/ci/validate_all_batches_with_report.sh` and confirm all
   batches report `PASS`.
2. The five Batch 14 namespaces exist: `ai-runtime`, `ai-gateway`,
   `ai-triggers`, `ai-policy`, `mcp-system`, `mcp-services`.
3. KAgent Postgres is reachable from the `ai-runtime` namespace.
4. The MCP gateway returns `200 /healthz` on its in-cluster service URL.

## Standard activation procedure

1. Render the AI / MCP overlay for the target environment:
   `helm template platform-core gitops/charts/platform-core -f gitops/overlays/<env>/platform-core-values.yaml`.
2. Deploy the `ai-runtime` ArgoCD Application (`gitops/apps/ai-runtime-application.yaml`).
3. Run the smoke validator:
   `bash scripts/ci/validate_batch14_smoke.sh`.
4. Verify approval flow with the dry-run example from
   `AI_APPROVAL_FLOW_RUNBOOK.md`.

## Standard rollback procedure

1. Set the `ai-runtime` Application to `Pause` in ArgoCD.
2. Optionally delete the `ai-runtime` Application — Batches 1-13 continue
   to run with no AI workloads scheduled.
3. Capture audit evidence by exporting the most recent action journal
   under `services/mcp/runbook-execution/journal/` and the contents of the
   `audit-events-*` index in OpenSearch.
4. File an incident ticket per `INCIDENT_DRILL_RUNBOOK.md`.

## Verification

- All ten AI / MCP validators exit `0` (run via `validate_batch14_smoke.sh`).
- The `AI_RUNTIME_HEALTH` and `MCP_GATEWAY_HEALTH` dashboards under
  `gitops/platform/search/dashboards/saved-objects/` report green.
- The `approval_flow_rules.ndjson` and `mcp_health_rules.ndjson` alert
  bundles under `gitops/platform/search/dashboards/alerts/` are loaded and
  not firing.

## Cross-references

- Marker map: `docs/auxiliary/planning/AI_MCP_MARKER_COVERAGE.md`
- Plan: `docs/auxiliary/planning/kagent_khook/`
- Implementation tasks: `docs/auxiliary/planning/IMPLEMENTATION_TASKS.md`
  Batch 14 (`TB-14`)
