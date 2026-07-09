# ADR-0004: Tenant Control Plane Service

**Status:** Accepted
**Date:** 2026-07-10
**Deciders:** Platform engineering (Batch 20 owner)
**Markers:** TB-20, TR-21, TR-16, TR-09

## Context

Batch 15 fixed the tenancy contracts: tenant identity
(`contracts/tenancy/TENANT_CONTRACT_SCHEMA_V1.json`), the lifecycle
state machine
(`contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml`), the isolation
matrix (`contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml`), and
per-tenant overlay generation
(`contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml`).
Batch 19 delivered the configuration rendering runtime (ADR-0003).
Nothing yet executes the tenant lifecycle behind an API: every
transition is contract-defined but operator-manual. Batch 20 delivers
the tenant control plane service (`TR-21`).

Forces shaping the decision:

- The API surface is contract-first: it is fixed by
  `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` (OpenAPI),
  covering tenant CRUD plus the provision, suspend, resume, offboard,
  and purge transitions with exactly the state machine and
  idempotent-replay semantics of the lifecycle contract. The service
  conforms to the contract file, never the reverse.
- Every lifecycle transition materializes as a GitOps render: the
  service renders per-tenant overlays per the overlay generation
  contract, reusing the `TR-20` renderer as a library, and performs no
  direct mutable cluster writes for persistent configuration
  (`TR-10`).
- Destructive transitions (offboard, purge) are blocked without an
  approval record per `contracts/policy/APPROVAL_FLOW_V1.yaml`,
  honoring its timeout and escalation rules. Every transition attempt
  (applied, replayed, or denied) emits an audit record carrying the
  tenant id (`TR-09`).
- CI validation is offline and fixture-driven: no live cluster, no Git
  remote, no PyPI, and `requirements-ci.txt` stays lint-only. CI can
  never install a web framework, so every contract-bearing behavior of
  the service must be testable without FastAPI importable.
- Tenant isolation is deny-by-default and layers on Batch 8 team
  isolation without weakening it; cross-tenant operations must be
  rejected and the rejections proven by seeded denial fixtures.

## Decision

Build the tenant control plane as a FastAPI service in typed Python
3.11+ under `services/tenancy/`, with these fixed boundaries:

- The service owns its dependency manifest
  (`services/tenancy/pyproject.toml`) and is never added to
  `requirements-ci.txt`. This mirrors the `tools/obskit/` posture
  fixed by ADR-0001: runtime dependencies live with the runtime, CI
  stays lint-only.
- Two-layer architecture. The core layer implements the lifecycle
  state machine, idempotent-replay evaluation, approval-gate checks,
  audit-record construction, and render planning as pure typed Python
  with frozen dataclasses and no imports outside the standard library
  and the repo's own packages. The API layer is a thin FastAPI adapter
  that binds contract-fixed routes to core calls and performs no
  business logic. Offline CI fixtures import and exercise the core
  without FastAPI installed.
- The OpenAPI document is hand-authored and authoritative. Its
  `x-lifecycle-binding` block restates the lifecycle contract's
  states, initial and terminal states, and per-transition from/to,
  idempotency, and approval risk classes by name, so the Batch 20
  validator cross-checks the two contracts mechanically and fails on
  drift.
- Lifecycle execution is GitOps-only. Transitions call the Batch 19
  renderer (`obskit.configrender`) and the Batch 15 overlay generation
  rules as libraries; the output of a transition is rendered files
  plus a prepared commit reference, never a live store or cluster
  mutation. Transition responses therefore carry a GitOps render
  reference, not an applied-infrastructure report.
- Deletion maps to the lifecycle contract, not to row removal: the
  CRUD delete operation is an alias for the approval-gated offboard
  transition, and purge remains a separate, explicitly requested,
  `write.critical`-gated transition. No API operation deletes tenant
  data outside the purge path.

## Options Considered

### Option A: Standard-Library HTTP Service (http.server)

Extend the zero-dependency discipline of `tools/obskit/` to the
service tier and hand-roll routing, request validation, and OpenAPI
conformance on `http.server`. Rejected: the zero-dependency contract
exists to keep an operator CLI runnable anywhere with bare Python; a
long-running network service with typed request models, an
OpenAPI-first surface, and auth middleware would re-implement a web
framework badly. The offline-CI force is satisfied by the core/adapter
split instead, without giving up a production server.

### Option B: Flask

Use Flask as the service framework. Rejected: Flask is untyped at its
boundary, has no native request/response model validation, and needs a
plugin ecosystem to emit or verify OpenAPI. With a hand-authored
OpenAPI contract as the source of truth, the framework should make
conformance cheap; Flask makes it a third-party concern and invites
drift.

### Option C: FastAPI With a Framework-Free Core (Chosen)

FastAPI on typed Python 3.11+, exactly as `TR-21` requires, with all
contract-bearing logic in a framework-free core package. FastAPI's
typed request/response models map one-to-one onto the contract's
component schemas, and its native OpenAPI emission lets the Batch 20
validator compare the served surface against the authoritative
contract. The core/adapter split keeps CI offline and stdlib-only.

## Trade-Off Analysis

FastAPI brings a real dependency tree (pydantic, starlette, an ASGI
server) that repo CI can never install. That is acceptable because the
dependency boundary is the service's own manifest - the same trade
ADR-0001 made for `obskit`'s optional `[k8s]` extra - and because the
two-layer split means nothing CI must prove requires those imports:
the state machine, replay semantics, approval gating, audit records,
and render planning are all core-layer and fixture-testable with the
stdlib alone. A hand-authored contract and a framework-generated
schema can drift; the posture is that the hand-authored file wins, the
validator checks the contract against the lifecycle contract on every
PR, and served-schema comparison is a live check, not a CI gate.
Aliasing CRUD delete to offboard makes the destructive path slightly
less obvious than a bare DELETE, but it is the only reading consistent
with the lifecycle contract, which defines no deletion outside
offboard-then-purge and forbids automated purge.

## Consequences

- `services/tenancy/` becomes the repository's first long-running
  control-plane service, with its own manifest and test surface;
  `tools/obskit/` remains the operator CLI runtime and is consumed by
  the service as a library, never re-implemented.
- `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` is the fixed
  API surface. Batch 21 (portal) and Batch 22 (billing) consume this
  API and must not re-implement lifecycle logic or bypass its approval
  gates.
- Every transition response carries the tenant id, an audit record
  reference, a replay flag, and a GitOps render reference; illegal
  transitions and cross-tenant access return contract-fixed error
  shapes and still emit audit records (denial gates of the lifecycle
  contract).
- Seeded denial fixtures must prove that unapproved destructive
  transitions and cross-tenant operations are rejected, extending the
  Batch 15 seeded-rejection pattern to the API surface.
- The Batch 20 validator cross-checks the OpenAPI document against
  the lifecycle contract by name (states, transitions, risk classes),
  so a future lifecycle contract change fails CI until both files
  move together.
- The file-backed store assumes a single writer process: run exactly
  one API worker per store root. Audit record id assignment is
  sequential per store root, so concurrent writers would collide; a
  multi-writer deployment requires a coordinated store, deferred and
  noted for Batch 21+.

## Action Items

- Publish `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml` (this
  batch, Task 1).
- Implement the framework-free core and the FastAPI adapter under
  `services/tenancy/` (later Batch 20 tasks).
- Gate with the Batch 20 validator, seeded denial fixtures, and the
  Batch 20 smoke wrapper (later Batch 20 tasks).
- Add tenant lifecycle operations to `docs/runbooks/` (later Batch 20
  tasks).
