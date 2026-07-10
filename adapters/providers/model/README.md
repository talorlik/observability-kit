# Model Provider Adapters

This subtree makes the AI runtime's large-language-model provider
pluggable. The runtime consumes providers only through the neutral
invocation envelope fixed by
`contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml`; vendor
specifics live here and nowhere else. The decision record is
`docs/adr/ADR_0008_MODEL_PROVIDER_ADAPTER.md`.

## Files

- `MODEL_PROVIDER_ADAPTER_COMPATIBILITY_V1.yaml` - provider catalog:
  which providers exist, which profiles may select them, and which
  configuration fields each requires.
- `ANTHROPIC_REFERENCE_ADAPTER_STUB_V1.yaml` - the reference vendor
  adapter: declarative mapping from the neutral envelope onto the
  Anthropic Messages API. No code, no live calls.
- `STUB_METADATA.json` - adapter class metadata and fallback
  behavior.
- `ROLLBACK_UNINSTALL_NOTES.md` - reversible activation semantics.

## Providers

| Provider | Mode | Profiles | Credentials |
| --- | --- | --- | --- |
| `local-stub` | deterministic canned completion | quickstart, dev | none |
| `anthropic-reference` | Messages API | staging, prod | `secretref:` only |

`local-stub` exists so the disposable evidence harness (ADR-0007) and
CI rehearse the full trigger-to-approval flow deterministically with
zero external calls and zero spend. Production profiles reject it by
contract (`fail_if_stub_in_production`).

## Key Resolution

Provider keys resolve exclusively through the secrets backend adapter
(`adapters/secrets/`). Catalog entries carry
`api_key_ref: secretref:...` references; the secrets backend
materializes them as Kubernetes Secrets in the `ai-runtime` namespace,
consumed via `secretKeyRef`. A credential literal in configuration or
any Git-tracked file is a seeded validation failure.

## Validation

```bash
bash scripts/ci/validate_ai_activation.sh
```

The activation validator checks house-pattern completeness, catalog
rule conformance, and the rejection rules of the governing contract.
