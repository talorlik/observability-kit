# Management Portal Guide

This guide defines the Batch 21 operator and user flow for the unified
management portal (`TR-22`,
[ADR-0005](../adr/ADR_0005_MANAGEMENT_PORTAL_STACK.md)). The portal is
the operator's single pane over the wrapped systems: it navigates to
every cataloged UI, edits the unified configuration document through
the Batch 19 renderer as GitOps-only commits, delegates tenant
management to the Batch 20 control plane, and summarizes platform
health from the `TR-12` meta-monitoring signals. It wraps, never
forks, and writes persistent configuration only through Git (`TR-17`,
`TR-20`).

> [!NOTE]
> This guide deviates from the single `Pre-checks` / `Procedure` /
> `Verification` layout used by other per-batch guides: it bundles
> several independent procedures (operator setup, SSO configuration,
> the config editing flow, tenant views), so each major section
> carries its own preconditions and verification steps.

## Table of Contents

- [Scope](#scope)
- [Artifacts](#artifacts)
- [Global Pre-Checks](#global-pre-checks)
- [Operator Setup](#operator-setup)
- [SSO Configuration](#sso-configuration)
- [Config Editing Flow](#config-editing-flow)
- [Tenant Views](#tenant-views)
- [Verification](#verification)
- [Rollback](#rollback)

## Scope

The portal serves exactly the four views fixed by
`contracts/management/PORTAL_CONTRACT_V1.yaml` (v1 is minimal by
charter):

- `navigation` - wrapped-UI entry points, one outbound link per
  `ui_catalog` entry of
  `contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml`, each
  resolved against the deployed admin-access profile `endpoints` at
  request time.
- `config` - the unified configuration editor. Every edit is
  validated against
  `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json`, planned with
  the `TR-20` renderer, and materialized only as rendered files plus
  a prepared Git commit reference.
- `tenants` - tenant management, delegated operation-for-operation to
  the tenant control plane API
  (`contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml`).
- `health` - the `TR-12` per-plane health summary with a worst-of
  overall rollup.

The portal deliberately is NOT:

- A live configuration writer. The only mutation the config view can
  perform is `plan_config_edit` followed by `commit_config_edit`
  through the renderer (`fail_if_live_config_write`); the GitOps
  controller reconciles, the portal never applies.
- A tenant lifecycle engine. Transition, approval, and audit
  semantics live in the Batch 20 control plane; every portal tenant
  operation declares a `delegates_to` operation
  (`fail_if_tenant_lifecycle_logic_in_portal`).
- An identity provider. There is no login form, no credential store,
  and no bespoke auth layer (`fail_if_bespoke_portal_auth`); identity
  always arrives from the admin access plane (`TR-03`).
- A break-glass path. The portal follows the admin-access profile
  `break_glass` block and adds no mechanism of its own.

Authoritative references: the portal contract above, ADR-0005 for the
stack decision, and the Batch 16/19/20 contracts it consumes.

## Artifacts

- `contracts/management/PORTAL_CONTRACT_V1.yaml` - views, API
  surface, authentication, and consistency rules.
- `docs/adr/ADR_0005_MANAGEMENT_PORTAL_STACK.md` - stack decision:
  typed Python core, FastAPI adapter, stdlib templates.
- `services/portal/` - the `portalsvc` package (core modules,
  `string.Template` pages, one static stylesheet).
- `install/profiles/admin-access/PROFILE.schema.json` - authn
  provider, `role_mapping` groups, and the `endpoints` object with
  the optional `portal` key.
- `contracts/policy/APPROVAL_FLOW_V1.yaml` - approval rules for
  destructive tenant transitions surfaced in the tenants view.
- `tests/portal/` - the offline test suites and fixtures.

## Global Pre-Checks

Run these before operating the portal; they prove the Batch 16, 19,
and 20 surfaces the portal builds on are present and consistent:

```bash
bash scripts/ci/validate_management_plane_contracts.sh
```

```bash
bash scripts/ci/validate_config_renderer.sh
```

```bash
bash scripts/ci/validate_tenant_control_plane.sh
```

Environment requirements:

- Python 3.11 or newer (`services/portal/pyproject.toml`
  `requires-python`).
- Serving the API requires the `[api]` extra, installed from the
  package's own manifest and never via `requirements-ci.txt`:

  ```bash
  python3 -m pip install "./services/portal[api]"
  ```

  Offline validation needs no install: the `portalsvc` core and the
  suites under `tests/portal/` run with plain `python3`.

- The admin-access profile is deployed with `role_mapping` groups set
  and, when the portal is exposed, the optional `endpoints.portal`
  key. The portal host is profile-owned like every wrapped UI host;
  neither the contract nor the source names one.
- Profile TLS posture is `constrained: true` - the portal sits behind
  the same TLS-terminating, SSO-enforcing edge as every other admin
  surface.

## Operator Setup

The service is assembled by dependency injection: `build_app` in
`services/portal/portalsvc/api.py` takes the fully constructed core
as keyword arguments. Every value is deployment-provided; none is
hardcoded, and the portal source carries no host, URL, or environment
literal (`fail_if_hardcoded_endpoint`).

```python
from pathlib import Path

from portalsvc.api import build_app
from portalsvc.catalog import load_ui_catalog
from portalsvc.configflow import ConfigFlow
from portalsvc.frontend import PortalFrontendRenderer
from portalsvc.health import summarize_health
from portalsvc.security import (
    AdminAccessPlaneSecurityPolicy,
    AdminAccessRoleMapping,
)
from portalsvc.tenants import HttpControlPlaneClient, PortalTenantService

# All inputs below come from deployment configuration (mounted
# profile, environment-provided paths); the literals here are
# placeholders, never defaults baked into the portal.
repo_root = Path("<gitops-working-tree>")
contracts_dir = Path("<repo>/contracts")

app = build_app(
    # Navigation entries come from the single-pane access contract.
    catalog=load_ui_catalog(
        contracts_dir / "management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
    ),
    # The unified document lives inside the GitOps working tree the
    # renderer writes into; contracts_dir is read-only.
    config_flow=ConfigFlow(
        repo_root=repo_root,
        document_path=Path("<unified-config-document-path>"),
        contracts_dir=contracts_dir,
    ),
    # base_url is the control plane service address including its
    # /api/tenancy/v1 base path, taken from deployment config.
    tenant_service=PortalTenantService(
        HttpControlPlaneClient(
            "https://<tenant-control-plane-host>/api/tenancy/v1"
        )
    ),
    # Any callable returning a HealthSummary; summarize_health rolls
    # a TR-12 signal snapshot into the per-plane grid.
    health_provider=lambda: summarize_health(read_signal_snapshot()),
    # role_mapping mirrors the deployed admin-access profile.
    security=AdminAccessPlaneSecurityPolicy(
        role_mapping=AdminAccessRoleMapping(
            readonly_group="<profile role_mapping.readonly_group>",
            admin_group="<profile role_mapping.admin_group>",
        ),
    ),
    # endpoints mirrors the deployed profile `endpoints` object; the
    # navigation view resolves catalog entries against it.
    frontend=PortalFrontendRenderer(endpoints={"<key>": "<host>"}),
)
```

Run the app under `uvicorn`. `portalsvc.api` imports without FastAPI
installed; `build_app` raises a clear error pointing at the `[api]`
extra when the framework is missing.

> [!NOTE]
> The portal holds no state of its own, but its config commit flow
> mutates the working tree at `repo_root` (persist document,
> re-render, prepare commit material). Run exactly ONE portal
> replica with ONE worker per `repo_root` - the same single-writer
> rule ADR-0004 fixes for the tenant control plane store, whose
> writer instance must also stay singular. Read-only portal replicas
> are safe only if they never serve the config commit route and
> share a reconciled checkout.

Setup is verified when `/healthz` (the only unauthenticated route,
process liveness only) answers 200 and every authenticated route
denies requests that lack the identity headers below.

## SSO Configuration

Identity always arrives from the admin access plane: the profile's
OIDC or SAML proxy (`authn.provider`) authenticates the session and
injects the trusted identity headers. The portal performs no
authentication of its own.

| Header            | Content                                        |
| ----------------- | ---------------------------------------------- |
| `x-portal-user`   | Authenticated subject                          |
| `x-portal-groups` | Comma-delimited group memberships              |
| `x-portal-tenant` | Optional tenant scope; absent = platform scope |

> [!WARNING]
> Header trust boundary (portal contract `header_trust_boundary`):
> these headers are trusted only from the admin access plane ingress
> or gateway path, and the edge MUST strip client-supplied copies
> before injecting its own. The portal rejects requests missing the
> subject or groups headers on every authenticated route, but it
> cannot distinguish a forged header from a proxy-injected one - the
> stripping is the deployment's job.

Role mapping follows the contract verbatim, from exactly the two
groups the profile `role_mapping` defines:

| Profile group    | Portal role       | Grants                                            |
| ---------------- | ----------------- | ------------------------------------------------- |
| `readonly_group` | `portal-readonly` | Read-only access to every view within scope       |
| `admin_group`    | `portal-admin`    | Everything above, plus config edits and lifecycle |

Tenant scoping is deny-by-default (`TR-16`): a principal carrying
`x-portal-tenant` sees only that tenant end to end - tenant views
list only it, and reads or transition requests for any other tenant
are denied. Enforcement is portal-side AND at the control plane: the
portal forwards the caller's scope, and the control plane binds it to
its service-layer `caller_scope`, so cross-tenant denial does not
depend on portal filtering alone
(`fail_if_unscoped_tenant_access`). The config view is platform-wide
by nature and requires platform scope; a tenant-scoped principal
cannot load it. Break-glass follows the profile `break_glass` block;
the portal adds none.

Verify by requesting any authenticated route without the headers
(must be rejected), with a `readonly_group` membership (views load,
mutations denied), and with a tenant scope (only that tenant is
visible).

## Config Editing Flow

Preconditions: `portal-admin` role, platform scope, and a green
[Global Pre-Checks](#global-pre-checks) run.

1. Read. Open `/config` (JSON: `GET /api/v1/config`). The view shows
   the current unified configuration document.
2. Edit. Change the document in the no-JS editor - server-rendered
   HTML, no client-side framework (ADR-0005); all validation runs
   server-side.
3. Validate (plan). Submitting for validation calls
   `POST /api/v1/config/plan`: the document is validated against
   `contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json` and the
   response lists the render plan's changed paths. This is a dry run;
   nothing is written.
4. Commit. `POST /api/v1/config/commit` executes the validated plan
   through the Batch 19 renderer (`execute_plan`): rendered files
   land at each binding's `render_target` under `gitops/`, and the
   response carries the prepared commit reference. The GitOps
   controller reconciles the committed revision; the portal never
   applies anything to a live system.

> [!IMPORTANT]
> There is no live write path. Any portal operation that mutated
> platform configuration other than plan-then-commit through the
> renderer would be drift by construction
> (`fail_if_live_config_write`).

Drift detection and response stay with `obskit drift` and the Batch
19 flow - see the
[Unified Configuration Runbook](UNIFIED_CONFIGURATION_RUNBOOK.md).
Verify a commit the same way as any renderer change: the prepared
commit lands in Git, ArgoCD syncs it, and post-sync checks pass per
that runbook.

## Tenant Views

Preconditions: the tenant control plane is reachable at the
deployment-provided `base_url` and the caller holds the role the
action requires (`portal-readonly` to list and inspect,
`portal-admin` for lifecycle transitions).

Listing and inspection are scoped by principal: platform-scoped
callers span tenants, tenant-scoped callers see exactly their own
tenant. Lifecycle actions delegate to the control plane operations
(`provisionTenant`, `suspendTenant`, `resumeTenant`,
`offboardTenant`, `purgeTenant`) and render forms with these fields:

| Action    | Required form fields     | Approval fieldset |
| --------- | ------------------------ | ----------------- |
| provision | none (`reason` optional) | not shown         |
| suspend   | `reason`, `trigger_type` | not shown         |
| resume    | `reason`                 | not shown         |
| offboard  | `reason`                 | required          |
| purge     | none (`reason` optional) | required          |

`trigger_type` must be `operator` or `automated`. The destructive
transitions (offboard, purge) carry the approval fieldset; a request
submitted with it blank is forwarded without an `approval` block, and
the control plane answers with the contract's `approval-required`
denial per `contracts/policy/APPROVAL_FLOW_V1.yaml` - the portal
never fabricates or relaxes approvals.

Actor attribution comes from the authenticated subject
(`x-portal-user`): the portal fills the transition's `actor` from the
principal, never from a form field, so audit records attribute every
transition to the SSO identity that requested it.

Verify a transition end to end with the
[Tenant Administration Runbook](TENANT_ADMINISTRATION_RUNBOOK.md):
the control plane's audit trail, approval handling, and purge
evidence procedures apply unchanged to portal-initiated requests.

## Verification

Offline gates (repository-only, no cluster):

```bash
bash scripts/ci/validate_portal_contracts.sh
```

```bash
bash scripts/ci/validate_batch21_smoke.sh
```

These cover the portal contract's consistency rules and run the three
offline suites under `tests/portal/` (`test_backend_core.py`,
`test_auth_scoping.py`, `test_frontend_views.py`) against fixtures -
run them via the validators, not standalone.

Live reachability (never CI-gated; needs a deployed instance):

```bash
PORTAL_BASE_URL="https://<portal-host>" \
  bash scripts/validate/admin_gui_smoke.sh
```

With `PORTAL_BASE_URL` set, the smoke script probes the portal's
`/healthz` liveness route alongside the wrapped admin UIs.

## Rollback

The portal is stateless: removing or scaling it down removes the
single pane and nothing else. The wrapped systems, the tenant control
plane, and all telemetry data are untouched, and the wrapped UIs
remain directly reachable at their profile endpoints.

Configuration commits made through the portal are ordinary renderer
commits: revert them with Git revert per the Batch 19 rollback drill
(`scripts/ops/run_config_rollback_drill.sh`, dry-run default) and the
[Unified Configuration Runbook](UNIFIED_CONFIGURATION_RUNBOOK.md).

Related guides:
[Visualization Admin Access Plane Guide](VISUALIZATION_ADMIN_ACCESS_PLANE_GUIDE.md)
for the admin access plane the portal authenticates through,
[Unified Configuration Runbook](UNIFIED_CONFIGURATION_RUNBOOK.md) for
the render, drift, and rollback flow,
[Tenant Administration Runbook](TENANT_ADMINISTRATION_RUNBOOK.md) for
the control plane the tenants view delegates to,
[Validation Runbook](VALIDATION_RUNBOOK.md) for per-batch
verification entrypoints, and
[Rollback Runbook](ROLLBACK_RUNBOOK.md) for GitOps revision rollback.
