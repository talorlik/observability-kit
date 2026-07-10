# Model Provider Adapter Rollback and Uninstall Notes

The model-provider adapter is profile-scoped, additive, and
reversible. Governing contracts:
`contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml` and
`docs/adr/ADR_0008_MODEL_PROVIDER_ADAPTER.md`.

## Rollback (Provider Swap)

1. Change the profile's `aiRuntime.modelProvider.name` back to the
   previous catalog entry (GitOps commit; no runtime mutation).
2. Argo CD reconciles the AI runtime configuration; the runtime
   reloads the provider registry on rollout.
3. Verify with the activation validator:

```bash
bash scripts/ci/validate_ai_activation.sh
```

No casefile, audit, or persistence data is touched by a provider
swap: the invocation envelope is provider-neutral, so historical
audit records remain readable regardless of the active provider.

## Uninstall (Disable the Vendor Adapter)

1. Remove the vendor entry selection from the profile
   (`aiRuntime.modelProvider.name: local-stub` for dev and
   quickstart; production profiles must instead disable the AI tier,
   because `local-stub` is rejected there by contract).
2. Delete the provider credential from the secrets backend
   (`secretref:ai/model-provider/anthropic-api-key`). The Kubernetes
   Secret materialization is garbage-collected by the secrets
   backend adapter; nothing in Git changes because the key was never
   in Git.
3. The core platform is unaffected: the AI/MCP layer is a
   higher-order tier and the platform must stay fully operational
   with it disabled (TR-15).

## Invariants

- Rollback and uninstall are GitOps-only operations plus a secrets
  backend deletion; no kubectl edits, no chart forks.
- Cross-tenant isolation guarantees do not depend on the provider:
  redaction profiles apply before any prompt leaves the runtime.
