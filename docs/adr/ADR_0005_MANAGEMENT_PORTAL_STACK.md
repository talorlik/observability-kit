# ADR-0005: Management Portal Stack

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 21 owner)
**Markers:** TB-21, TR-03, TR-17, TR-22

## Context

Batches 16, 19, and 20 delivered the management-plane contracts, the
configuration rendering runtime (`obskit.configrender`, ADR-0003), and
the tenant control plane (`services/tenancy`, package `tenantctl`,
ADR-0004). Operators still have no single pane: wrapped UIs are
cataloged in
`contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml` but nothing
serves that catalog, unified configuration is editable only through
the `obskit render` CLI, and tenant lifecycle operations require
direct control-plane API calls. Batch 21 delivers the portal that
fronts all of it (`TR-22`).

Forces shaping the decision:

- The portal wraps, never forks: it links to every cataloged wrapped
  UI and drives wrapped systems only through existing contract
  surfaces. It holds no tenant lifecycle logic (delegated to `TR-21`)
  and performs no live configuration writes (edits become Git commits
  through the `TR-20` renderer).
- CI validation is offline and fixture-driven: no live cluster, no
  Git remote, no PyPI at validation time, and `requirements-ci.txt`
  stays lint-only. Every contract-bearing behavior must be testable
  with system `python3` and no third-party imports.
- The admin access plane (`TR-03`) owns authentication: OIDC by
  default, SAML via adapter, role mapping through
  `role_mapping.readonly_group` and `role_mapping.admin_group`, and
  tenant scoping per `TR-16` - a tenant-scoped principal must never
  see another tenant's views.
- v1 must stay minimal by charter: the task list fixes views
  (navigation, unified config editing, tenant management, health
  overview), so the stack choice must not smuggle in scope.

## Decision

Build the portal as a typed Python 3.11+ service under
`services/portal/` (package `portalsvc`) with a server-rendered HTML
frontend and zero JavaScript build toolchain. Fixed boundaries:

- Two-layer architecture, mirroring ADR-0004. The core layer (UI
  catalog aggregation, unified-config edit planning, tenant client,
  health summary, principal and scoping model) is pure typed Python
  with frozen dataclasses and no imports outside the standard library
  and the repo's own packages (`obskit`, consumed as a library via
  the same in-repo `sys.path` fallback tenantctl uses). The API layer
  is a thin FastAPI adapter behind the optional `[api]` extra; it
  binds contract-fixed routes to core calls and holds no business
  logic. Offline CI imports and exercises the core without FastAPI
  installed.
- The service owns its dependency manifest
  (`services/portal/pyproject.toml`) and is never added to
  `requirements-ci.txt` (ADR-0001 posture).
- Frontend: server-rendered HTML built from `string.Template` page
  templates shipped inside the package, styled by one static CSS
  file, with no client-side framework, no npm, no bundler, and no
  vendored third-party JavaScript. Config-editor schema validation
  runs server-side against
  `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json` through the
  renderer's own validation path, and the rendered pages surface the
  errors; client-side JS is not required for any portal function.
- Unified config edits are GitOps-only: the portal validates the
  edited document, plans the render with
  `obskit.configrender.render.plan_render`, and materializes it only
  through `execute_plan`, producing rendered files plus a prepared
  commit reference. The portal never calls a live config endpoint.
- Tenant management is delegated to the control plane over its
  contract-fixed HTTP API
  (`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`) via a typed
  stdlib (`urllib`) client behind a protocol, with an in-process
  double for offline tests. The portal binds the authenticated
  principal's tenant scope to the control plane's `caller_scope` (the
  binding Batch 20 left open); the control plane HTTP adapter gains
  principal extraction from the portal-forwarded scope headers.
- Authentication follows the admin access plane profile
  (`install/profiles/admin-access/PROFILE.schema.json`): the portal
  trusts OIDC-proxy identity headers injected at the ingress or
  gateway per the profile `mode`, maps `readonly_group` and
  `admin_group` to portal roles, and derives tenant scope per the
  single-pane access contract. The portal implements no login form,
  no password store, and no bespoke auth layer (rule
  `fail_if_bespoke_portal_auth` of the portal contract, matching
  `fail_if_bespoke_ui_auth` of the single-pane access contract).
- The admin-access profile `endpoints` object gains an optional
  `portal` key (additive schema change, contract-first) so the portal
  endpoint is profile-owned like every other UI host, and
  `scripts/validate/admin_gui_smoke.sh` can check it.

## Options Considered

### Option A: Single-Page Application (React or Vue + Vite)

Industry-default portal stack. Rejected: it introduces a Node
toolchain, a bundler, and a large third-party dependency tree that
offline CI can neither install nor audit; the supply-chain and
maintenance cost is unjustifiable for four v1 views, and a compiled
asset bundle would be the one artifact in the repo CI cannot rebuild.

### Option B: Server-Rendered With a Template Engine (Flask + Jinja2)

Smaller than an SPA, but still two third-party runtime dependencies
whose contract-bearing behavior (template rendering of scoped views)
would then be untestable in offline CI, violating the rule that CI
exercises real logic, not stubs.

### Option C: Typed Python Core + FastAPI Adapter + Stdlib Templates (Chosen)

Matches ADR-0004 exactly on the backend, so the two services share
posture, test strategy, and packaging. `string.Template` HTML with
one CSS file covers navigation links, a config editor form, tenant
tables, and a health grid without any client framework; every view
renders as a pure function of typed core state and is asserted
byte-level in offline tests.

## Trade-Off Analysis

Option C trades UI richness for auditability and offline
verifiability. The known costs: no client-side interactivity beyond
plain HTML forms (acceptable - every v1 action is a read, a form
post, or an outbound link), HTML assembled from `string.Template` is
less ergonomic than Jinja2 (mitigated by keeping templates small and
per-view), and a future richer UI may replace the frontend layer
(the core/API boundary is unaffected by that swap, which keeps the
exit cheap). FastAPI in the adapter keeps parity with the control
plane and gives the same OpenAPI-alignment ergonomics at zero cost to
offline CI because the adapter stays optional.

## Consequences

- `services/portal/` follows the exact test topology of
  `services/tenancy/`: offline tests under `tests/portal/` run with
  system `python3` and import only the core; the FastAPI adapter is
  exercised only where installed (never in CI).
- The portal contract
  (`contracts/management/PORTAL_CONTRACT_V1.yaml`) is the single
  source of portal scope: views, API surface, and authentication.
  The Batch 21 validator cross-checks the contract against the UI
  catalog so a cataloged UI can never be missing from portal
  navigation.
- The control plane HTTP adapter change (principal extraction to
  `caller_scope`) closes the Batch 20 gap where every HTTP caller was
  platform-scoped; tenant-scoped portal principals are now enforced
  end to end (`TR-16`).
- The additive `portal` endpoints key keeps hosts profile-owned;
  no URL or hostname appears in any contract or portal source.
- A future SPA or design-system frontend is a frontend-layer swap
  behind the same core and JSON API; this ADR fixes the v1 floor,
  not the ceiling.

## Action Items

- Implement `services/portal/` (package `portalsvc`) per this ADR
  (Batch 21 Tasks 2-4).
- Publish `contracts/management/PORTAL_CONTRACT_V1.yaml` (Task 1)
  and validate it in `scripts/ci/validate_portal_contracts.sh`
  (Task 5).
- Add the optional `portal` key to the admin-access profile
  `endpoints` schema and extend
  `scripts/validate/admin_gui_smoke.sh` (Task 5).
- Document operator setup, SSO configuration, config editing, and
  tenant views in `docs/runbooks/MANAGEMENT_PORTAL_GUIDE.md`
  (Task 6).
