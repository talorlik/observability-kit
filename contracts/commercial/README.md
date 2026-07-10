# Commercial Contracts

Authoritative contracts for metering, plans, and billing export
(Batch 22, `TR-23`). Usage is derived from platform telemetry already
in OpenSearch, records are control-plane documents carrying tenant
attribution, plans bind tenant tiers to quota bounds, and the invoice
export surface stays vendor-neutral: vendor billing logic lives under
`adapters/billing/` only. The narrative decision record is
`docs/adr/ADR_0006_METERING_ARCHITECTURE.md` (ADR-0006).

## Files

- `METERING_CONTRACT_V1.yaml` - usage dimensions, telemetry sources,
  record surface, control-plane destination, and rejection rules for
  the metering collector.
- `USAGE_RECORD_SCHEMA_V1.json` - JSON Schema (draft 2020-12) for one
  metered usage measurement; a record without `tenant_id` is rejected.
- `PLAN_CATALOG_V1.yaml` - bijective plan-to-tier binding with quota
  bounds in the Batch 15 tenant quota fields and base-plus-overage
  billing in currency-neutral units.
- `INVOICE_EXPORT_CONTRACT_V1.yaml` - the vendor-neutral export
  document one billing period yields per tenant: derivation, overage
  semantics per dimension, and the `adapters/billing/` boundary.
- `INVOICE_EXPORT_SCHEMA_V1.json` - JSON Schema (draft 2020-12) for
  the export document; currency-neutral by construction (currency
  assignment is adapter-side only).
- `samples/` - both `VALID_*` documents and `INVALID_*`
  seeded-rejection sets (`VALID_USAGE_RECORDS.json`,
  `VALID_PLAN_BINDINGS.json`, `VALID_INVOICE_EXPORT.json`,
  `INVALID_USAGE_RECORD_SAMPLES.json`, `INVALID_PLAN_SAMPLES.json`,
  `INVALID_BILLING_ADAPTER_SAMPLES.json`); every `INVALID_*` sample
  must be rejected, and a sample that validates cleanly is a
  validator failure.

## Validation

`scripts/ci/validate_commercial_contracts.sh` owns validation of this
directory: schema-versus-samples checks with seeded rejection, plan
catalog binding and bound-range checks, invoice export consistency,
and the billing adapter boundary constraints.
