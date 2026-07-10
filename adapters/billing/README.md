# Billing Adapters

Billing adapters map vendor billing systems onto the vendor-neutral
invoice-export contract while retaining the core metering, plan catalog, and
export contracts as authoritative. The core produces one export document per
tenant per billing period per
`contracts/commercial/INVOICE_EXPORT_CONTRACT_V1.yaml`; everything
vendor-specific - object mapping, currency, tax, credentials - lives in this
directory only.

## Contract Boundaries

- adapters consume export documents through the invoice-export contract only
- dispatch mode is export-only (no core write-path targets)
- a billing adapter never mutates the platform core; fork-like core mutation
  is rejected by validation
- credentials resolve through the secrets backend adapters
  (`adapters/secrets/`) as secret references, never literal keys
- currency assignment and tax are adapter-side only; the core export
  document stays currency-neutral

## Supported Backends

The full mapping lives in `BILLING_ADAPTER_COMPATIBILITY_V1.yaml`. The table
below summarizes each backend.

| Backend          | Mode                | Vendor Neutral | Profiles      |
| ---------------- | ------------------- | -------------- | ------------- |
| file-export      | export-file         | yes            | all profiles  |
| stripe-reference | invoice-export-push | no (stub)      | staging, prod |

Generated values: both backends emit `billing.enabled` and `billing.mode`;
`stripe-reference` additionally emits `billing.adapterRef`. The
`file-export` profiles are `quickstart`, `dev`, `staging`, and `prod`.

The `stripe-reference` backend is a declarative stub
(`STRIPE_REFERENCE_ADAPTER_STUB_V1.yaml`): field mapping, auth references,
and non-goals only - no code, no live calls.

## Adding a New Vendor

1. Add an entry under `billing_backends:` in
   `BILLING_ADAPTER_COMPATIBILITY_V1.yaml`.
2. Set `mode` (e.g., `invoice-export-push`) and `vendor_neutral: false`.
3. List `supported_profiles` and `required_fields`; credentials must be
   secret references resolved through the secrets backend.
4. Set `outputs.generated_values` (must include `billing.enabled` and
   `billing.mode`).
5. Add a `<VENDOR>_REFERENCE_ADAPTER_STUB_V1.yaml` mapping the neutral
   export fields to vendor objects; keep every vendor name and vendor field
   inside `adapters/billing/`.
6. Run `bash scripts/ci/validate_commercial_contracts.sh` to verify.

## Validation

`scripts/ci/validate_commercial_contracts.sh` enforces:

- `core_contracts_unchanged: true`
- `dispatch_mode: export-only`
- `deny_core_contract_mutation: true` with `fork` in
  `forbidden_wrap_methods`
- per-backend `billing.enabled` and `billing.mode` generated values
- `secrets_via_secrets_backend_only: true` and
  `currency_assignment: adapter-side-only`
- the seeded rejection samples in
  `contracts/commercial/samples/INVALID_BILLING_ADAPTER_SAMPLES.json`

## Rollback

See `ROLLBACK_UNINSTALL_NOTES.md` for the disable, fall-back, and remove
procedures. Disabling a vendor billing adapter must fall back to the
`file-export` backend with the core contracts unchanged.
