# Identity Adapters

Identity adapters extend backend identity integration without changing core
observability contracts. They are cloud-agnostic by construction: each backend
maps an external identity provider into the same Kubernetes service-account
shape that the core platform already consumes.

## Contract Boundaries

- no mutation of core identity access matrix fields
- explicit profile-driven activation only
- reversible disablement path required
- fallback must return to core defaults
- read-only dispatch mode (no write-path targets)
- bounded service-account annotation count per backend

## Supported Backends

The full mapping lives in `IDENTITY_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`. The
table below summarizes each backend — the contract is open to additional
backends that conform to the same OIDC-federation shape.

| Backend                    | Mode             | Supported Clusters | Bounded Annotations |
| -------------------------- | ---------------- | ------------------ | ------------------- |
| aws-irsa                   | oidc-federation  | eks                | 8 entries           |
| gcp-workload-identity      | oidc-federation  | gke                | 8 entries           |
| azure-workload-identity    | oidc-federation  | aks                | 8 entries           |
| generic-oidc               | oidc-federation  | conformant k8s     | 8 entries           |

All backends generate the same value set:
`identity.enabled`, `identity.mode`, `identity.serviceAccountAnnotations`.

## Adding a New Backend

1. Add an entry under `identity_backends:` in
   `IDENTITY_BACKEND_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Specify supported cluster types and required identity fields.
3. Define `outputs.generated_values` (must include the three values above) and
   `outputs.bounded_annotations.max_entries`.
4. Run `bash scripts/ci/validate_identity_backend_adapters.sh` to verify.

## Validation

`scripts/ci/validate_identity_backend_adapters.sh` enforces:
- `core_contracts_unchanged: true`
- `dispatch_mode: read-only`
- per-backend required fields and bounded annotation limits
- referenced service accounts exist in `IDENTITY_ACCESS_MATRIX_V1.yaml`
- presence of rollback/uninstall notes referencing the validator

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, validate, and remove
procedures. Disabling an identity adapter does not affect any other adapter
or any core platform behavior.
