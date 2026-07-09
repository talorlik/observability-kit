# Tenant Control Plane Service

Batch 20 Task 2 (TR-21, ADR-0004). Executes the tenant lifecycle fixed
by `contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml` behind the API
surface of `contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`: tenant
CRUD plus the provision, suspend, resume, offboard, and purge
transitions, each materialized as a GitOps render, never a direct
mutable cluster or store write (TR-10).

## Architecture

Two layers, per ADR-0004:

- `tenantctl/` core: state machine (contract-loaded at runtime with a
  line-based stdlib extractor, no PyYAML), idempotent-replay
  evaluation, approval gating, audit records (TR-09), and per-tenant
  overlay render planning. Standard library only, plus the repo's own
  `tools/obskit` package consumed as a library.
- `tenantctl/api.py`: thin FastAPI adapter binding contract-fixed
  routes to core calls. Importable without FastAPI; `build_app` raises
  a clear error when the `[api]` extra is missing.

## GitOps Rendering

Transitions produce per-tenant overlays per
`contracts/tenancy/TENANT_OVERLAY_GENERATION_CONTRACT_V1.yaml` through
the Batch 19 renderer library: `tenantctl.renders` packages the two
required overlay files into an `obskit.configrender.models.RenderPlan`
and writes and diff-checks them exclusively via
`obskit.configrender.render.execute_plan` and `changed_paths`.
Overlays exist only for the `dedicated-stack` isolation class; replays
of completed transitions are audited no-ops with
`render_action: replayed-no-diff`.

## Dependencies

This package owns its manifest (`pyproject.toml`) and is never added
to `requirements-ci.txt`. `obskit` is a logical dependency resolved
in-repo: when it is not pip-installed, `tenantctl.renders` adds
`tools/obskit` to `sys.path` relative to the source tree, the same
pattern the offline tests use.

## Tests

Offline tests live in `tests/controlplane/` and run with bare
`python3` (no pytest, no venv):

```bash
python3 tests/controlplane/test_lifecycle_service.py
```

## Later Batch 20 Tasks

- Task 3 fills `tenantctl/isolation.py` (isolation-matrix renders).
- Task 4 hardens `tenantctl/approval.py` (timeout, escalation) and
  extends `tenantctl/audit.py`.
