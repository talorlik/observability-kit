# Per-Tenant GitOps Overlays

This directory holds generated, per-tenant GitOps overlays. Each
subdirectory is the rendered output of the tenant overlay generator for
one tenant descriptor and is consumed by the tenant delivery
ApplicationSet. The governing contract is
[TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml][contract].

[contract]: ../../../contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml

> [!WARNING]
> Everything under this directory except this README is generated from
> tenant descriptors. Do not edit generated files by hand. Change the
> tenant descriptor and regenerate; hand edits are overwritten by the
> next regeneration and rejected in review.

## Naming Rule

- One directory per tenant: `gitops/overlays/tenants/<tenant_id>/`,
  where `<tenant_id>` is the descriptor `tenant_id` verbatim
  (lowercase slug per `TENANT_CONTRACT_SCHEMA_V1.json`).
- Each tenant directory contains exactly `tenant-values.yaml` and
  `applicationset-element.yaml`, both carrying the generated-file
  header marker.
- `EXAMPLE_TENANT_OVERLAY/` is a reserved, committed example of
  generator output for the `VALID_TENANT_BASIC.json` sample. Its
  uppercase name is deliberately outside the `tenant_id` pattern so it
  can never collide with a real tenant.

## Invariants (Summary)

- Core charts under `gitops/charts/` are never modified per tenant.
- Overlays propagate through git commits only (GitOps-only delivery).
- Regeneration is deterministic and idempotent: the same descriptor
  renders byte-identical output.
- Generated files carry only tenant descriptor fields - never
  environment names, cluster endpoints, repository URLs, or secrets.

See the contract for the full invariant list and the control-plane
versus data-plane separation rules.
