# Management Plane Contracts

Contracts for the unified configuration and management plane (Batch 16,
`TR-17`). The platform wraps every bundled open-source system so
operators manage, configure, and view everything from one place, while
each wrapped system remains upgradable through its own upstream
mechanism. Wrapping is configuration-only: upstream code, images, and
charts are never modified, and `fork` is a forbidden wrap method that
validation must reject.

## Files

- `WRAPPED_SYSTEM_REGISTRY_V1.yaml` - one entry per bundled system
  (OpenTelemetry Collector, OpenSearch, OpenSearch Dashboards, Grafana,
  Neo4j, Argo CD) with upstream source, version pin, upgrade mechanism,
  managed config surface, wrap method, and UI exposure. A top-level
  `policy` block defines the closed wrap-method enum (`helm-values`,
  `kubernetes-crd`, `provisioning-api`, `sidecar`), forbids `fork` via
  the `fail_if_wrap_method_fork` rule, and requires concrete version
  pins in production profiles. Enabled adapters are covered by the
  `adapters_extension` pointer to `contracts/adapters/` instead of
  duplicated entries; the policy block applies to them unchanged.
- `samples/INVALID_REGISTRY_SAMPLES.json` - seeded invalid registry
  entries keyed by case name, each with a single intended violation and
  an `expected_rejection_reason` (`fork` wrap method, unknown wrap
  method, missing upgrade mechanism). Mirrors the multi-case pattern in
  `contracts/tenancy/samples/INVALID_TENANT_SAMPLES.json` and feeds the
  Batch 16 rejection fixtures.

- `UNIFIED_CONFIG_SCHEMA_V1.json` - unified configuration document
  schema: the one place operators change platform configuration. Every
  config key carries propagation bindings that must target systems
  registered in the registry; render targets are GitOps paths only.
- `samples/VALID_UNIFIED_CONFIG.yaml` - complete valid document with
  every key bound and every binding grounded in a real repo config
  path.
- `samples/INVALID_UNIFIED_CONFIG_SAMPLES.json` - seeded invalid
  documents (unbound key, unregistered target system, unknown unified
  key, forbidden top-level property).
- `PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml` - GitOps-only render,
  commit, reconcile, verify, and drift-detection flow with rollback
  semantics and the direct-API-write prohibition.
- `SINGLE_PANE_ACCESS_CONTRACT_V1.yaml` - UI catalog built from the
  registry's `ui` fields, with SSO role mapping, tenant scoping, and
  admin-access-plane consistency rules.

## Validation

Owned by `scripts/ci/validate_management_plane_contracts.sh` (Batch 16
Task 5), aggregated by `validate_batch16_smoke.sh` and registered in
`validate_all_batches_with_report.sh`. The validator must assert that
the registry lists every bundled system with all required fields, that
every `wrap_method` is in the allowed enum, and that every case in
`samples/INVALID_REGISTRY_SAMPLES.json` - including the seeded `fork`
entry - is rejected with its expected reason.
