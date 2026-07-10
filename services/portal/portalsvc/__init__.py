"""Management portal service core (Batch 21, TR-22, ADR-0005).

Typed Python 3.11+ core of the operator's single pane: UI catalog
aggregation from the single-pane access contract, unified
configuration read/edit through the Batch 19 renderer (edits become
Git commit material, never live writes - TR-17), tenant management
by pure delegation to the Batch 20 control plane API, and the TR-12
platform health summary. Identity arrives from the admin access
plane (TR-03); the portal ships deny-by-default security and a
placeholder frontend as dependency-injection extension points for
Batch 21 Tasks 3-4.

The FastAPI adapter (portalsvc.api) is a thin optional layer behind
the [api] extra; the core imports only the standard library and the
repo's own obskit package.
"""

from __future__ import annotations

from portalsvc.catalog import (
    CatalogContractError,
    load_ui_catalog,
    resolve_endpoint,
)
from portalsvc.configflow import ConfigFlow
from portalsvc.health import (
    SIGNAL_FAMILIES,
    summarize_health,
    worst_of,
)
from portalsvc.models import (
    CatalogEntry,
    CommitResult,
    ConfigDocumentMissing,
    ConfigEditRejected,
    ConfigPlanResult,
    ControlPlaneDelegationError,
    DenyAllSecurityPolicy,
    Forbidden,
    FrontendRenderer,
    HealthSignal,
    HealthStatus,
    HealthSummary,
    NotAuthenticated,
    PlaceholderFrontendRenderer,
    PlaneHealth,
    PortalError,
    PortalRole,
    Principal,
    RenderedPage,
    SecurityPolicy,
    SsoRoleMapping,
    TenantScopeDenied,
    TenantSummary,
    VIEW_MINIMUM_ROLE,
    require_platform_scope,
    require_role,
)
from portalsvc.frontend import PortalFrontendRenderer
from portalsvc.security import (
    AdminAccessPlaneSecurityPolicy,
    AdminAccessRoleMapping,
)
from portalsvc.tenants import (
    ControlPlaneClient,
    HttpControlPlaneClient,
    PortalTenantService,
)

__all__ = [
    "CatalogContractError",
    "load_ui_catalog",
    "resolve_endpoint",
    "ConfigFlow",
    "SIGNAL_FAMILIES",
    "summarize_health",
    "worst_of",
    "CatalogEntry",
    "CommitResult",
    "ConfigDocumentMissing",
    "ConfigEditRejected",
    "ConfigPlanResult",
    "ControlPlaneDelegationError",
    "DenyAllSecurityPolicy",
    "Forbidden",
    "FrontendRenderer",
    "HealthSignal",
    "HealthStatus",
    "HealthSummary",
    "NotAuthenticated",
    "PlaceholderFrontendRenderer",
    "PlaneHealth",
    "PortalError",
    "PortalRole",
    "Principal",
    "RenderedPage",
    "SecurityPolicy",
    "SsoRoleMapping",
    "TenantScopeDenied",
    "TenantSummary",
    "VIEW_MINIMUM_ROLE",
    "require_platform_scope",
    "require_role",
    "ControlPlaneClient",
    "HttpControlPlaneClient",
    "PortalTenantService",
    "PortalFrontendRenderer",
    "AdminAccessPlaneSecurityPolicy",
    "AdminAccessRoleMapping",
]
