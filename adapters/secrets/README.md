# Secrets Adapters

Secrets adapters extend backend secret-store integration without changing core
observability contracts. They are cloud-agnostic by construction: each backend
maps an external secret store into the same `secrets.externalRef` shape that
the core platform consumes.

## Contract Boundaries

- no mutation of core identity or boundary contract fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
- read-only dispatch mode (no write-path targets)
- bounded mapping count per backend

## Supported Backends

The full mapping lives in `SECRETS_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`. The
table below summarizes each backend — the contract is open to additional
backends that conform to the same secret-store-ref shape.

| Backend                | Mode               | Supported Clusters | Bounded Mappings |
| ---------------------- | ------------------ | ------------------ | ---------------- |
| aws-secrets-manager    | secret-store-ref   | eks                | 12 entries       |
| gcp-secret-manager     | secret-store-ref   | gke                | 12 entries       |
| azure-key-vault        | secret-store-ref   | aks                | 12 entries       |
| vault-kv               | secret-store-ref   | conformant k8s     | 12 entries       |

All backends generate the same value set:
`secrets.enabled`, `secrets.mode`, `secrets.externalRef`.

## Adding a New Backend

1. Add an entry under `secrets_backends:` in
   `SECRETS_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Specify supported cluster types and required secret fields.
3. Define `outputs.generated_values` (must include the three values above) and
   `outputs.bounded_mappings.max_entries`.
4. Run `bash scripts/ci/validate_secrets_backend_adapters.sh` to verify.

## Validation

`scripts/ci/validate_secrets_backend_adapters.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- per-backend required fields and bounded mapping limits
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling a secrets adapter does not affect any other adapter or
any core platform behavior.
