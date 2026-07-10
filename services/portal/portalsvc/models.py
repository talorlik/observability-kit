"""Typed core models for the management portal (Batch 21, TR-22).

Pins the values fixed by contracts/management/PORTAL_CONTRACT_V1.yaml:
portal roles and their role_mapping plane groups, per-view minimum
roles, the trusted identity headers, and the contract-fixed error
shapes. Everything here is standard library only (ADR-0005: offline
CI imports and exercises the core without any third-party package).

Two protocols are deliberately defined as dependency-injection
extension points so later Batch 21 tasks plug in without editing the
API adapter:

- SecurityPolicy (Task 4): extracts and authorizes a Principal per
  request from the admin-access-plane identity headers. The safe
  default is DenyAllSecurityPolicy - until a real policy is wired,
  every authenticated route is denied.
- FrontendRenderer (Task 3): renders the HTML pages for the
  contract's html_routes. The safe default returns a 501-style
  placeholder page.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

# Trusted identity headers, verbatim from PORTAL_CONTRACT_V1.yaml
# authentication.trusted_identity_headers. The admin access plane
# proxy injects them; the deployment strips client-supplied copies at
# the edge (header_trust_boundary).
SUBJECT_HEADER = "x-portal-user"
GROUPS_HEADER = "x-portal-groups"
TENANT_SCOPE_HEADER = "x-portal-tenant"


class PortalRole(enum.Enum):
    """Portal roles, verbatim from the contract role_mapping."""

    READONLY = "portal-readonly"
    ADMIN = "portal-admin"


# portal-admin grants everything portal-readonly grants (contract
# role_mapping.grants), so authorization is an ordered comparison.
_ROLE_ORDER: Mapping[PortalRole, int] = {
    PortalRole.READONLY: 1,
    PortalRole.ADMIN: 2,
}

# Weakest portal role that may load each view, verbatim from the
# contract views[].minimum_role. The API adapter binds routes to
# these; it never invents its own role requirements.
VIEW_MINIMUM_ROLE: Mapping[str, PortalRole] = {
    "navigation": PortalRole.READONLY,
    "config": PortalRole.ADMIN,
    "tenants": PortalRole.READONLY,
    "health": PortalRole.READONLY,
}


class PortalError(Exception):
    """Base of every portal error surfaced as a JSON response."""

    error_code: str = "portal-error"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = dict(details) if details is not None else None

    def to_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.details is not None:
            payload["details"] = self.details
        return payload


class NotAuthenticated(PortalError):
    """No trustworthy identity on an authenticated route (401)."""

    error_code = "not-authenticated"
    http_status = 401


class Forbidden(PortalError):
    """Authenticated but not authorized for the operation (403)."""

    error_code = "forbidden"
    http_status = 403


class TenantScopeDenied(Forbidden):
    """A tenant-scoped principal touched another tenant (TR-16)."""

    error_code = "tenant-scope-denied"
    http_status = 403


class ConfigDocumentMissing(PortalError):
    """The unified configuration document is absent (404)."""

    error_code = "config-document-missing"
    http_status = 404


class ConfigEditRejected(PortalError):
    """A submitted config edit failed validation; nothing written."""

    error_code = "config-edit-rejected"
    http_status = 422


class ControlPlaneDelegationError(PortalError):
    """The tenant control plane rejected a delegated call.

    The upstream status and payload are relayed unchanged: the portal
    holds no tenant lifecycle logic, so it never rewrites the control
    plane's contract-fixed error shapes.
    """

    error_code = "control-plane-delegation-error"

    def __init__(
        self,
        message: str,
        *,
        upstream_status: int,
        upstream_payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.http_status = upstream_status
        self.upstream_payload = (
            dict(upstream_payload)
            if upstream_payload is not None
            else None
        )

    def to_response(self) -> dict[str, Any]:
        if self.upstream_payload is not None:
            return self.upstream_payload
        return super().to_response()


@dataclass(frozen=True)
class Principal:
    """An authenticated caller.

    tenant_scope None means platform-scoped (spans tenants per CTR-07
    semantics); a non-None tenant_scope pins every tenant view and
    delegated call to that tenant (TR-16).
    """

    subject: str
    groups: tuple[str, ...]
    roles: tuple[PortalRole, ...]
    tenant_scope: str | None = None

    @property
    def is_platform_scoped(self) -> bool:
        return self.tenant_scope is None

    def has_role(self, minimum: PortalRole) -> bool:
        required = _ROLE_ORDER[minimum]
        return any(
            _ROLE_ORDER[role] >= required for role in self.roles
        )


def require_role(principal: Principal, minimum: PortalRole) -> None:
    """Enforce the contract's minimum_role for a view or operation."""
    if not principal.has_role(minimum):
        raise Forbidden(
            f"principal {principal.subject!r} lacks the "
            f"{minimum.value} role required for this operation"
        )


def require_platform_scope(principal: Principal) -> None:
    """Enforce platform scope (the config view is platform-wide)."""
    if not principal.is_platform_scoped:
        raise Forbidden(
            "this operation is platform-wide and requires a "
            "platform-scoped principal; tenant-scoped access is "
            "denied (TR-16)"
        )


@dataclass(frozen=True)
class SsoRoleMapping:
    """One plane-group-to-native-role mapping of a catalog entry."""

    plane_group: str
    native_role: str


@dataclass(frozen=True)
class CatalogEntry:
    """One ui_catalog entry of the single-pane access contract.

    endpoint_profile_key is a REFERENCE into the deployed
    admin-access profile `endpoints` object, never a URL or host;
    None is the contract's documented existing-install exception
    (Argo CD). Resolution to a host happens per request against a
    deployment-provided mapping and is never stored.
    """

    id: str
    system: str
    display_name: str
    endpoint_source: str
    endpoint_profile_key: str | None
    sso_role_mappings: tuple[SsoRoleMapping, ...]

    def to_response(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "system": self.system,
            "display_name": self.display_name,
            "endpoint": {
                "source": self.endpoint_source,
                "profile_key": self.endpoint_profile_key,
            },
            "sso_role_mapping": [
                {
                    "plane_group": mapping.plane_group,
                    "native_role": mapping.native_role,
                }
                for mapping in self.sso_role_mappings
            ],
        }


@dataclass(frozen=True)
class ConfigPlanResult:
    """Outcome of a dry-run config edit plan (nothing written)."""

    valid: bool
    changed_paths: tuple[str, ...]
    errors: tuple[str, ...]

    def to_response(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "changed_paths": list(self.changed_paths),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class CommitResult:
    """Outcome of an executed config edit: Git commit material only.

    commit_reference is an opaque prepared-commit reference derived
    from the document digest (mirroring tenantctl.renders); no git
    command runs in the portal, and no live endpoint is written.
    """

    commit_reference: str
    commit_message: str
    written_paths: tuple[str, ...]

    def to_response(self) -> dict[str, Any]:
        return {
            "commit_reference": self.commit_reference,
            "commit_message": self.commit_message,
            "written_paths": list(self.written_paths),
        }


@dataclass(frozen=True)
class TenantSummary:
    """Portal-facing summary of one control-plane tenant record."""

    tenant_id: str
    display_name: str
    lifecycle_state: str
    tier: str
    isolation_class: str

    @classmethod
    def from_response(
        cls, payload: Mapping[str, Any]
    ) -> "TenantSummary":
        return cls(
            tenant_id=str(payload.get("tenant_id", "")),
            display_name=str(payload.get("display_name", "")),
            lifecycle_state=str(payload.get("lifecycle_state", "")),
            tier=str(payload.get("tier", "")),
            isolation_class=str(payload.get("isolation_class", "")),
        )


class HealthStatus(enum.Enum):
    """Per-signal and per-plane status values (TR-12)."""

    OK = "ok"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HealthSignal:
    """One meta-monitoring signal reading."""

    name: str
    status: HealthStatus
    detail: str | None = None


@dataclass(frozen=True)
class PlaneHealth:
    """Worst-of rollup of one TR-12 signal family."""

    plane: str
    status: HealthStatus
    signals: tuple[HealthSignal, ...]


@dataclass(frozen=True)
class HealthSummary:
    """Platform health: per-plane statuses plus the overall rollup."""

    overall: HealthStatus
    planes: tuple[PlaneHealth, ...]

    def to_response(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "planes": [
                {
                    "plane": plane.plane,
                    "status": plane.status.value,
                    "signals": [
                        {
                            "name": signal.name,
                            "status": signal.status.value,
                            **(
                                {"detail": signal.detail}
                                if signal.detail is not None
                                else {}
                            ),
                        }
                        for signal in plane.signals
                    ],
                }
                for plane in self.planes
            ],
        }


@dataclass(frozen=True)
class RenderedPage:
    """A server-rendered HTML page produced by a FrontendRenderer."""

    status_code: int
    html: str


class SecurityPolicy(Protocol):
    """Extracts and authorizes the request principal (Task 4 DI).

    Implementations read the trusted identity headers injected by the
    admin access plane, map role_mapping.readonly_group and
    role_mapping.admin_group to portal roles, and derive tenant
    scope. Raises NotAuthenticated when the request carries no
    trustworthy identity.
    """

    def principal_for(
        self, headers: Mapping[str, str]
    ) -> Principal: ...


class FrontendRenderer(Protocol):
    """Renders HTML for the contract's html_routes (Task 3 DI)."""

    def render_view(
        self, view: str, context: Mapping[str, Any]
    ) -> RenderedPage: ...


@dataclass(frozen=True)
class DenyAllSecurityPolicy:
    """Safe default: every authenticated route is denied.

    The portal ships deny-by-default; Batch 21 Task 4 replaces this
    with the header-trusting policy without touching the API adapter.
    """

    def principal_for(
        self, headers: Mapping[str, str]
    ) -> Principal:
        raise NotAuthenticated(
            "no security policy is configured; the portal denies all "
            "authenticated routes by default (install the Task 4 "
            "admin-access-plane policy)"
        )


@dataclass(frozen=True)
class PlaceholderFrontendRenderer:
    """Safe default: a 501-style placeholder for every HTML view.

    Batch 21 Task 3 supplies the real string.Template frontend
    without touching the API adapter. The placeholder embeds no
    platform data and no endpoint.
    """

    def render_view(
        self, view: str, context: Mapping[str, Any]
    ) -> RenderedPage:
        del context
        return RenderedPage(
            status_code=501,
            html=(
                "<!doctype html>\n"
                "<title>portal view not implemented</title>\n"
                f"<h1>View {view!r} is not implemented</h1>\n"
                "<p>The portal frontend renderer is not installed "
                "(Batch 21 Task 3).</p>\n"
            ),
        )


__all__ = [
    "SUBJECT_HEADER",
    "GROUPS_HEADER",
    "TENANT_SCOPE_HEADER",
    "PortalRole",
    "VIEW_MINIMUM_ROLE",
    "PortalError",
    "NotAuthenticated",
    "Forbidden",
    "TenantScopeDenied",
    "ConfigDocumentMissing",
    "ConfigEditRejected",
    "ControlPlaneDelegationError",
    "Principal",
    "require_role",
    "require_platform_scope",
    "SsoRoleMapping",
    "CatalogEntry",
    "ConfigPlanResult",
    "CommitResult",
    "TenantSummary",
    "HealthStatus",
    "HealthSignal",
    "PlaneHealth",
    "HealthSummary",
    "RenderedPage",
    "SecurityPolicy",
    "FrontendRenderer",
    "DenyAllSecurityPolicy",
    "PlaceholderFrontendRenderer",
]
