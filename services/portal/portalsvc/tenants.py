"""Tenant management by delegation to the Batch 20 control plane.

The portal holds no tenant lifecycle logic
(fail_if_tenant_lifecycle_logic_in_portal): every read and every
transition is a pure delegation to the operations fixed by
contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml (operationIds
listTenants, getTenant, provisionTenant, suspendTenant,
resumeTenant, offboardTenant, purgeTenant). The caller's scope is
forwarded on EVERY call via the trusted identity headers
(x-portal-user / x-portal-groups / x-portal-tenant), so cross-tenant
denial is enforced by the control plane itself, not only by portal
filtering (portal contract control_plane_binding, TR-16).

The portal layer additionally enforces the same scope locally
(deny-by-default): a tenant-scoped principal lists exactly its own
tenant and is denied any read or transition request naming another
tenant (fail_if_unscoped_tenant_access).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Mapping, Protocol

from portalsvc.models import (
    ControlPlaneDelegationError,
    GROUPS_HEADER,
    PortalRole,
    Principal,
    SUBJECT_HEADER,
    TENANT_SCOPE_HEADER,
    TenantScopeDenied,
    require_role,
)

# Portal operation -> control plane operationId, verbatim from the
# portal contract's delegates_to declarations.
DELEGATED_OPERATIONS: Mapping[str, str] = {
    "portal_list_tenants": "listTenants",
    "portal_get_tenant": "getTenant",
    "portal_provision_tenant": "provisionTenant",
    "portal_suspend_tenant": "suspendTenant",
    "portal_resume_tenant": "resumeTenant",
    "portal_offboard_tenant": "offboardTenant",
    "portal_purge_tenant": "purgeTenant",
}

TRANSITION_NAMES = (
    "provision",
    "suspend",
    "resume",
    "offboard",
    "purge",
)


class ControlPlaneClient(Protocol):
    """The five lifecycle operations plus list/get, per the Batch 20
    API contract. Every method receives the acting principal so the
    caller scope is forwarded on every call."""

    def list_tenants(
        self,
        principal: Principal,
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]: ...

    def get_tenant(
        self, tenant_id: str, principal: Principal
    ) -> dict[str, Any]: ...

    def provision_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]: ...

    def suspend_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]: ...

    def resume_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]: ...

    def offboard_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]: ...

    def purge_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]: ...


def scope_headers(principal: Principal) -> dict[str, str]:
    """Caller-scope headers forwarded on every delegated call."""
    headers = {
        SUBJECT_HEADER: principal.subject,
        GROUPS_HEADER: ",".join(principal.groups),
    }
    if principal.tenant_scope is not None:
        headers[TENANT_SCOPE_HEADER] = principal.tenant_scope
    return headers


class HttpControlPlaneClient:
    """Stdlib urllib client for the tenant control plane API.

    base_url is deployment-provided (the control plane service
    address including its /api/tenancy/v1 base path); it is injected,
    never defaulted, so no host lives in portal source. The opener is
    injectable for offline tests (an in-process double records the
    request instead of opening a socket).
    """

    def __init__(
        self,
        base_url: str,
        *,
        opener: Callable[..., Any] = urllib.request.urlopen,
        timeout: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._opener = opener
        self._timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        principal: Principal,
        body: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"accept": "application/json"}
        headers.update(scope_headers(principal))
        data: bytes | None = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["content-type"] = "application/json"
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            response = self._opener(
                request, timeout=self._timeout
            )
            payload = response.read()
        except urllib.error.HTTPError as error:
            raw = error.read()
            upstream: Mapping[str, Any] | None
            try:
                parsed = json.loads(raw) if raw else None
                upstream = (
                    parsed if isinstance(parsed, dict) else None
                )
            except json.JSONDecodeError:
                upstream = None
            raise ControlPlaneDelegationError(
                f"control plane rejected {method} {path} with "
                f"status {error.code}",
                upstream_status=error.code,
                upstream_payload=upstream,
            ) from error
        except OSError as error:
            raise ControlPlaneDelegationError(
                f"control plane unreachable for {method} {path}: "
                f"{error}",
                upstream_status=502,
            ) from error
        try:
            parsed = json.loads(payload) if payload else {}
        except json.JSONDecodeError as error:
            raise ControlPlaneDelegationError(
                f"control plane returned a non-JSON payload for "
                f"{method} {path}",
                upstream_status=502,
            ) from error
        if not isinstance(parsed, dict):
            raise ControlPlaneDelegationError(
                f"control plane returned a non-object payload for "
                f"{method} {path}",
                upstream_status=502,
            )
        return parsed

    def list_tenants(
        self,
        principal: Principal,
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]:
        path = "/tenants"
        if lifecycle_state is not None:
            query = urllib.parse.urlencode(
                {"lifecycle_state": lifecycle_state}
            )
            path = f"{path}?{query}"
        return self._request("GET", path, principal)

    def get_tenant(
        self, tenant_id: str, principal: Principal
    ) -> dict[str, Any]:
        encoded = urllib.parse.quote(tenant_id, safe="")
        return self._request(
            "GET", f"/tenants/{encoded}", principal
        )

    def _transition(
        self,
        name: str,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        encoded = urllib.parse.quote(tenant_id, safe="")
        return self._request(
            "POST",
            f"/tenants/{encoded}/lifecycle/{name}",
            principal,
            body,
        )

    def provision_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        return self._transition(
            "provision", tenant_id, body, principal
        )

    def suspend_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        return self._transition(
            "suspend", tenant_id, body, principal
        )

    def resume_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        return self._transition(
            "resume", tenant_id, body, principal
        )

    def offboard_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        return self._transition(
            "offboard", tenant_id, body, principal
        )

    def purge_tenant(
        self,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        return self._transition(
            "purge", tenant_id, body, principal
        )


class PortalTenantService:
    """Scope-enforcing delegation layer over a ControlPlaneClient.

    Pure delegation: no transition, approval, or audit semantics live
    here - only TR-16 scope enforcement (deny-by-default) and the
    contract's role requirements (reads are portal-readonly;
    lifecycle transition requests are portal-admin).
    """

    def __init__(self, client: ControlPlaneClient) -> None:
        self._client = client
        self._transitions: Mapping[
            str,
            Callable[
                [str, Mapping[str, Any], Principal],
                dict[str, Any],
            ],
        ] = {
            "provision": client.provision_tenant,
            "suspend": client.suspend_tenant,
            "resume": client.resume_tenant,
            "offboard": client.offboard_tenant,
            "purge": client.purge_tenant,
        }

    @staticmethod
    def _check_scope(
        principal: Principal, tenant_id: str
    ) -> None:
        if (
            principal.tenant_scope is not None
            and tenant_id != principal.tenant_scope
        ):
            raise TenantScopeDenied(
                f"principal {principal.subject!r} is scoped to a "
                "different tenant; cross-tenant access is denied "
                "(TR-16)"
            )

    def list_tenants(
        self,
        principal: Principal,
        lifecycle_state: str | None = None,
    ) -> dict[str, Any]:
        require_role(principal, PortalRole.READONLY)
        if principal.tenant_scope is not None:
            # A tenant-scoped principal lists exactly its own tenant;
            # the scoped get is still delegated with the caller's
            # scope so the control plane enforces the same boundary.
            record = self._client.get_tenant(
                principal.tenant_scope, principal
            )
            if (
                lifecycle_state is not None
                and record.get("lifecycle_state") != lifecycle_state
            ):
                # Honor the filter the platform-scoped path delegates
                # upstream: a scoped caller filtering on a state its
                # tenant is not in gets an empty list, not its tenant.
                return {"tenants": []}
            return {"tenants": [record]}
        return self._client.list_tenants(
            principal, lifecycle_state
        )

    def get_tenant(
        self, tenant_id: str, principal: Principal
    ) -> dict[str, Any]:
        require_role(principal, PortalRole.READONLY)
        self._check_scope(principal, tenant_id)
        return self._client.get_tenant(tenant_id, principal)

    def transition(
        self,
        name: str,
        tenant_id: str,
        body: Mapping[str, Any],
        principal: Principal,
    ) -> dict[str, Any]:
        require_role(principal, PortalRole.ADMIN)
        self._check_scope(principal, tenant_id)
        delegate = self._transitions.get(name)
        if delegate is None:
            raise ValueError(
                f"unknown lifecycle transition {name!r}; the portal "
                f"delegates exactly {list(TRANSITION_NAMES)}"
            )
        return delegate(tenant_id, body, principal)
