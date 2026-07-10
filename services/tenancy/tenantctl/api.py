"""Thin FastAPI adapter for the tenant control plane (ADR-0004).

Binds the contract-fixed routes of
contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml one-to-one to
TenantControlPlaneService calls and performs no business logic. The
hand-authored OpenAPI document is authoritative; this adapter conforms
to it, never the reverse.

Import guard: this module is importable without FastAPI installed
(offline CI never installs a web framework); build_app then raises a
clear error pointing at the [api] extra.

Caller scope (Batch 21 Task 4, TR-16): every route handler binds the
portal-forwarded x-portal-tenant trusted header to the service
layer's caller_scope, closing the Batch 20 gap where every HTTP
caller was platform-scoped. Extraction lives in the pure, FastAPI-free
caller_scope_from_headers helper below.
"""

from __future__ import annotations

from typing import Any, Mapping

from tenantctl.models import ControlPlaneError
from tenantctl.service import TenantControlPlaneService

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    _FASTAPI_AVAILABLE = False

BASE_PATH = "/api/tenancy/v1"

# Trusted identity headers forwarded by the management portal,
# verbatim from PORTAL_CONTRACT_V1.yaml trusted_identity_headers (the
# same names portalsvc.models pins; tenantctl stays import-independent
# of portalsvc, so the names are repeated here as protocol constants).
# The admin access plane strips client-supplied copies at the edge
# (header_trust_boundary), so a present header is authoritative.
SUBJECT_HEADER = "x-portal-user"
GROUPS_HEADER = "x-portal-groups"
TENANT_SCOPE_HEADER = "x-portal-tenant"

_TRANSITION_ROUTES = (
    "provision",
    "suspend",
    "resume",
    "offboard",
    "purge",
)


def caller_scope_from_headers(
    headers: Mapping[str, str]
) -> str | None:
    """Derive the service-layer caller_scope from request headers.

    Pure and FastAPI-free so offline CI can exercise it. Header names
    are matched case-insensitively (plain-dict callers may pass any
    casing; FastAPI's Headers mapping is lowercase already).

    Rules (PORTAL_CONTRACT_V1.yaml tenant_scoping and
    control_plane_binding, TR-16):

    - x-portal-tenant absent -> None (platform-scoped caller, the
      CTR-07 span; also the posture of non-portal callers such as
      in-cluster operators that predate the portal).
    - x-portal-tenant present -> its whitespace-stripped value; the
      service layer denies any operation naming a different tenant.
    - Malformed (present but empty/whitespace) -> the empty string,
      which the service treats as a tenant scope matching NO tenant:
      every scoped operation is denied and lists come back empty.
      Fail-closed by construction - a malformed header must never
      silently widen a caller to platform scope (None).
    - x-portal-user / x-portal-groups are NOT consulted for scope:
      the control plane performs no authentication of its own (the
      admin access plane edge does, and the portal maps roles), so a
      tenant header narrows the caller regardless of whether identity
      headers accompany it. Narrowing on partial identity is
      fail-closed; requiring identity headers before honoring the
      scope would be fail-open.
    """
    normalized = {
        str(name).lower(): value for name, value in headers.items()
    }
    raw_scope = normalized.get(TENANT_SCOPE_HEADER)
    if raw_scope is None:
        return None
    return raw_scope.strip()


def build_app(service: TenantControlPlaneService) -> "FastAPI":
    """Build the FastAPI application over a service instance."""
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed; install services/tenancy with "
            "the [api] extra (pip install 'obskit-tenantctl[api]') to "
            "run the API adapter. The tenantctl core works without it."
        )
    app = FastAPI(title="Tenant Control Plane API", version="1.0.0")

    @app.exception_handler(ControlPlaneError)
    async def _control_plane_error(
        _request: Request, error: ControlPlaneError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.http_status, content=error.to_response()
        )

    @app.post(f"{BASE_PATH}/tenants", status_code=201)
    async def create_tenant(request: Request) -> dict[str, Any]:
        return service.create_tenant(
            await request.json(),
            caller_scope=caller_scope_from_headers(request.headers),
        )

    @app.get(f"{BASE_PATH}/tenants")
    async def list_tenants(
        request: Request,
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]:
        return {
            "tenants": service.list_tenants(
                lifecycle_state,
                caller_scope=caller_scope_from_headers(
                    request.headers
                ),
            )
        }

    @app.get(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def get_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        return service.get_tenant(
            tenant_id,
            caller_scope=caller_scope_from_headers(request.headers),
        )

    @app.put(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def update_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        return service.update_tenant(
            tenant_id,
            await request.json(),
            caller_scope=caller_scope_from_headers(request.headers),
        )

    @app.delete(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def delete_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        # DELETE is a semantic alias for the approval-gated offboard
        # transition (the lifecycle contract defines no deletion
        # outside offboard-then-purge); it never triggers purge.
        result = service.transition(
            "offboard",
            tenant_id,
            await request.json(),
            caller_scope=caller_scope_from_headers(request.headers),
        )
        return result.to_response()

    def _register_transition(name: str) -> None:
        @app.post(
            f"{BASE_PATH}/tenants/{{tenant_id}}/lifecycle/{name}",
            name=f"{name}Tenant",
        )
        async def _transition(
            tenant_id: str, request: Request
        ) -> dict[str, Any]:
            result = service.transition(
                name,
                tenant_id,
                await request.json(),
                caller_scope=caller_scope_from_headers(
                    request.headers
                ),
            )
            return result.to_response()

    for transition_name in _TRANSITION_ROUTES:
        _register_transition(transition_name)
    return app
