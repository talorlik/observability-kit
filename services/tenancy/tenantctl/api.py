"""Thin FastAPI adapter for the tenant control plane (ADR-0004).

Binds the contract-fixed routes of
contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml one-to-one to
TenantControlPlaneService calls and performs no business logic. The
hand-authored OpenAPI document is authoritative; this adapter conforms
to it, never the reverse.

Import guard: this module is importable without FastAPI installed
(offline CI never installs a web framework); build_app then raises a
clear error pointing at the [api] extra.
"""

from __future__ import annotations

from typing import Any

from tenantctl.models import ControlPlaneError
from tenantctl.service import TenantControlPlaneService

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    _FASTAPI_AVAILABLE = False

BASE_PATH = "/api/tenancy/v1"

_TRANSITION_ROUTES = (
    "provision",
    "suspend",
    "resume",
    "offboard",
    "purge",
)


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
        return service.create_tenant(await request.json())

    @app.get(f"{BASE_PATH}/tenants")
    async def list_tenants(
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]:
        return {"tenants": service.list_tenants(lifecycle_state)}

    @app.get(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def get_tenant(tenant_id: str) -> dict[str, Any]:
        return service.get_tenant(tenant_id)

    @app.put(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def update_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        return service.update_tenant(tenant_id, await request.json())

    @app.delete(f"{BASE_PATH}/tenants/{{tenant_id}}")
    async def delete_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        # DELETE is a semantic alias for the approval-gated offboard
        # transition (the lifecycle contract defines no deletion
        # outside offboard-then-purge); it never triggers purge.
        result = service.transition(
            "offboard", tenant_id, await request.json()
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
                name, tenant_id, await request.json()
            )
            return result.to_response()

    for transition_name in _TRANSITION_ROUTES:
        _register_transition(transition_name)
    return app
