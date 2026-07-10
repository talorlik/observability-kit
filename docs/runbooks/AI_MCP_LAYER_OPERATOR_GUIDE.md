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

## Live Activation

Batch 24 (`TB-24`, ADR-0009) activates the runtime live. The runtime
is the product-owned `obskit-ai-runtime` image (built from
`services/ai/`, four entrypoints: kagent, khook, gateway, mcpserver)
deployed GitOps-only from `gitops/platform/ai/` with the MCP catalog
and governance contracts enforced unmodified.

On the disposable evidence harness (the only sanctioned live
environment before production activation):

```bash
bash scripts/dev/live_cluster_harness.sh create
bash scripts/dev/live_cluster_harness.sh run --only install
bash scripts/dev/live_cluster_harness.sh run --only ai-deploy
bash scripts/dev/live_cluster_harness.sh run --only ai-rehearsal
bash scripts/dev/live_cluster_harness.sh run --only ai-signoff
bash scripts/dev/live_cluster_harness.sh teardown
```

`ai-deploy` builds and side-loads the runtime image, materializes the
`kagent-postgres-credentials` secret (per
`contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml`; production
resolves it through the secrets backend adapter), applies the
`ai-runtime` Argo CD Application at
`gitops/platform/ai/overlays/dev`, and captures deployment evidence
under `artifacts/evidence/batch24/deploy/`. The model provider is
`local-stub` (ADR-0008); production profiles select
`anthropic-reference` with keys via `secretref:` only.

`ai-rehearsal` runs the live trigger-to-approval rehearsal (see
`AI_APPROVAL_FLOW_RUNBOOK.md`), and `ai-signoff` executes
`docs/operations/PRODUCTION_ACTIVATION_SIGNOFF_WORKFLOW.md` with
every quantitative threshold measured; an unmeasurable threshold is
a failed gate and forces `hold`.

Structural verification without a cluster:

```bash
bash scripts/ci/validate_ai_activation.sh
```

## Rollback to Scaffolding

Live activation is fully reversible to the validated pre-activation
state; nothing below touches contracts or evidence already captured.

1. Delete the `ai-runtime` Argo CD Application (with cascade) or set
   its `targetRevision` to the last pre-activation revision; Argo CD
   prunes the runtime workloads. Namespaces and contracts stay.
2. Delete the `kagent-postgres-credentials` secret (harness) or the
   secrets backend entry (production). The casefile store PVC is
   removed with the StatefulSet's claim per your storage policy;
   export `kagent_audit` first if the audit retention window
   (730 days, write-once) has not elapsed.
3. The repository state remains the Batch 14 validated scaffolding
   plus the Batch 24 contracts; all ten AI/MCP validators and
   `validate_ai_activation.sh`'s offline sections keep passing.
4. Re-activation is a fresh `ai-deploy` run; a harness cluster is
   never reused (ADR-0007).

## Cross-references

- Marker map: `docs/auxiliary/planning/AI_MCP_MARKER_COVERAGE.md`
- Plan: `docs/auxiliary/planning/kagent_khook/`
- Implementation tasks: `docs/auxiliary/planning/IMPLEMENTATION_TASKS.md`
  Batch 14 (`TB-14`)
- Activation decisions: `docs/adr/ADR_0008_MODEL_PROVIDER_ADAPTER.md`,
  `docs/adr/ADR_0009_AI_RUNTIME_ACTIVATION_STRATEGY.md`
- Live validation harness: `docs/runbooks/LIVE_VALIDATION_RUNBOOK.md`
