# KHook Troubleshooting Runbook

This runbook covers operational troubleshooting for the KHook trigger tier
of the AI/MCP layer (Batch 14). Cloud-agnostic — applies to any conformant
Kubernetes cluster.

## Scope

KHook normalizes events from cluster-internal sources and (via provider
adapters) external event sources into a single hook-event schema, then
dispatches them to the agent layer under read-only dispatch policy.

Related contracts:

- `contracts/policy/READ_ONLY_DISPATCH_POLICY_V1.yaml`
- `contracts/policy/DEDUPE_BURST_CONTROL_V1.yaml`
- `triggers/`
- `adapters/providers/EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml`

Related dashboards/alerts:

- `gitops/platform/search/dashboards/saved-objects/AI_RUNTIME_HEALTH.ndjson`
  (KHook event rate panel)
- `gitops/platform/search/dashboards/alerts/approval_flow_rules.ndjson`
  (action-gate precondition failures)

## Symptom 1: trigger not firing

1. Confirm the hook is registered: list current hooks via the agent
   gateway and check that the hook ID is present and `enabled: true`.
2. Verify provider adapter delivery — for an external source, check the
   provider's outbox / event log to confirm the event was emitted within
   the last evaluation window.
3. Inspect the KHook deployment logs in `ai-triggers` namespace for
   normalization errors. Look for fields missing from
   `EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml.normalization.required_fields`.
4. Check dedupe state — re-firing within `DEDUPE_BURST_CONTROL_V1.yaml`
   suppression window will be silently dropped. Cross-reference the
   correlation_id in the audit log.
5. If still not firing, verify the trigger's `read-only-dispatch` policy
   has not been disabled by a recent overlay change. The compliance flag
   `direct_discovery_disabled_for_backend_mcpserver` must remain true.

## Symptom 2: burst control misconfiguration

1. Pull the active `DEDUPE_BURST_CONTROL_V1.yaml`.
2. Compute the actual event rate from the AI runtime dashboard's
   `ai-khook-event-rate` panel.
3. If actual rate > configured `burst.max_per_minute`, KHook will
   intentionally drop excess events; this is by design.
4. To raise the cap, propose a value change in a PR; after merge, validate
   via `bash scripts/ci/validate_khook_trigger_scaffolding.sh` to confirm
   bounds are still within contract.

## Symptom 3: dispatch policy debugging

1. Confirm the dispatch path is `read-only` for trigger-originated calls.
   Read-write dispatch must come through approval flow.
2. If a trigger is incorrectly dispatching writes, check
   `READ_ONLY_DISPATCH_POLICY_V1.yaml` for the violating role and inspect
   the action-gate audit log for the specific blocked decision.
3. Cross-reference with `contracts/policy/IDENTITY_ACCESS_MATRIX_V1.yaml`
   to confirm the service account is bound to read-only permissions.

## Symptom 4: event enrichment failures

1. Check the trigger's enrichment pipeline logs.
2. Validate that all required fields in
   `EVENT_SOURCE_ADAPTER_COMPATIBILITY_V1.yaml.normalization.required_fields`
   are populated. Missing fields cause the event to fail validation.
3. Confirm `bounded_payload.max_bytes` is not being exceeded.

## Validation Commands

```bash
bash scripts/ci/validate_khook_trigger_scaffolding.sh
bash scripts/ci/validate_provider_event_source_adapters.sh
bash scripts/ci/validate_batch14_smoke.sh
```

## Rollback

If a recent KHook change is suspected of breaking dispatch:

1. Revert the offending PR in GitOps.
2. ArgoCD will reconcile the previous KHook deployment.
3. Verify recovery via the `ai-khook-event-rate` panel.
