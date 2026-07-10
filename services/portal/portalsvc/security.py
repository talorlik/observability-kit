"""Admin-access-plane security policy (Batch 21 Task 4, TR-03/TR-16).

The real SecurityPolicy implementation behind the Task 2 dependency
injection point in portalsvc.models: the portal implements no login
form and no credential store (PORTAL_CONTRACT_V1.yaml authentication,
fail_if_bespoke_portal_auth). Identity arrives from the admin access
plane proxy as trusted headers (header_trust_boundary: the deployment
strips client-supplied copies at the edge, so by the time a request
reaches the portal these headers are authoritative), and this module
maps them to a Principal:

- subject from x-portal-user (models.SUBJECT_HEADER);
- groups from x-portal-groups (models.GROUPS_HEADER), a
  comma-delimited list - segments are whitespace-stripped and empty
  segments are dropped;
- optional tenant scope from x-portal-tenant
  (models.TENANT_SCOPE_HEADER).

Role mapping follows the contract's role_mapping block verbatim: the
deployed admin-access profile's role_mapping.readonly_group maps to
portal-readonly and role_mapping.admin_group maps to portal-admin
(which grants everything portal-readonly grants - the ordered-role
comparison in models.Principal.has_role encodes that implication).
Group values are DATA from the deployed profile, injected at
construction time; no group name is hardcoded here. Groups outside
the two mapped ones are ignored; a principal whose groups map to no
portal role is Forbidden.

Tenant scoping per the contract's tenant_scoping model (TR-16): no
tenant header means platform-scoped (spans tenants per CTR-07); a
tenant header pins the Principal to that tenant. Scope ENFORCEMENT
lives downstream (PortalTenantService deny-by-default,
models.require_platform_scope for the platform-wide config view);
this module only constructs the Principal faithfully and never widens
visibility - every ambiguous input fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from portalsvc.models import (
    Forbidden,
    GROUPS_HEADER,
    NotAuthenticated,
    PortalRole,
    Principal,
    SUBJECT_HEADER,
    TENANT_SCOPE_HEADER,
)

# The groups header is a single comma-delimited value (the common
# OIDC-proxy encoding). Segments are stripped of surrounding
# whitespace; empty segments (",,", trailing commas) are dropped.
GROUP_DELIMITER = ","


def parse_groups(raw: str) -> tuple[str, ...]:
    """Parse the x-portal-groups header value.

    Comma-delimited, whitespace-stripped, empty segments dropped,
    order preserved, duplicates removed (a duplicate group carries no
    additional grant).
    """
    seen: dict[str, None] = {}
    for segment in raw.split(GROUP_DELIMITER):
        group = segment.strip()
        if group:
            seen.setdefault(group, None)
    return tuple(seen)


def _normalize_headers(
    headers: Mapping[str, str]
) -> dict[str, str]:
    """Lowercase header names (HTTP header names are
    case-insensitive; plain-dict callers may pass any casing)."""
    return {str(name).lower(): value for name, value in headers.items()}


@dataclass(frozen=True)
class AdminAccessRoleMapping:
    """The deployed admin-access profile's role_mapping values.

    Exactly the two groups the profile schema
    (install/profiles/admin-access/PROFILE.schema.json role_mapping)
    defines - readonly_group and admin_group. The single-pane access
    contract and the portal contract map no third plane group, so
    this type deliberately has no room for one.
    """

    readonly_group: str
    admin_group: str

    def __post_init__(self) -> None:
        # Empty group names would make membership tests meaningless
        # (parse_groups never yields an empty group, so an empty
        # mapping value could never match - but failing loudly at
        # construction beats a policy that silently denies everyone).
        for field_name in ("readonly_group", "admin_group"):
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(
                    f"role_mapping.{field_name} must be a non-empty "
                    "group name from the deployed admin-access "
                    "profile"
                )


@dataclass(frozen=True)
class AdminAccessPlaneSecurityPolicy:
    """SecurityPolicy that trusts the admin-access-plane headers.

    role_mapping is injected from the deployed admin-access profile.
    authn_provider and mfa_required are recorded facts from the same
    profile's authn block (oidc|saml-adapter, mfa posture); the
    portal performs no authentication of its own, so they are carried
    for surfacing/audit only and never branch authorization logic.
    """

    role_mapping: AdminAccessRoleMapping
    authn_provider: str | None = None
    mfa_required: bool | None = None

    def principal_for(
        self, headers: Mapping[str, str]
    ) -> Principal:
        normalized = _normalize_headers(headers)

        # header_trust_boundary: every authenticated route rejects
        # requests missing the subject or groups headers. A present
        # but empty/whitespace value is equally untrustworthy.
        subject = (normalized.get(SUBJECT_HEADER) or "").strip()
        raw_groups = normalized.get(GROUPS_HEADER)
        if not subject or raw_groups is None:
            raise NotAuthenticated(
                "request carries no trustworthy identity: the "
                f"{SUBJECT_HEADER} and {GROUPS_HEADER} headers "
                "injected by the admin access plane are required on "
                "every authenticated route"
            )
        groups = parse_groups(raw_groups)
        if not groups:
            raise NotAuthenticated(
                f"the {GROUPS_HEADER} header carries no group "
                "membership; the admin access plane must inject at "
                "least one group"
            )

        # Contract role_mapping: readonly_group -> portal-readonly,
        # admin_group -> portal-admin. Unmapped groups are ignored;
        # mapping to NO portal role is an authenticated-but-not-
        # authorized caller (403, not 401).
        roles: list[PortalRole] = []
        if self.role_mapping.readonly_group in groups:
            roles.append(PortalRole.READONLY)
        if self.role_mapping.admin_group in groups:
            roles.append(PortalRole.ADMIN)
        if not roles:
            raise Forbidden(
                f"principal {subject!r} belongs to no group mapped "
                "to a portal role (profile role_mapping grants "
                "portal access to exactly readonly_group and "
                "admin_group members)"
            )

        # tenant_scoping model (TR-16): header absent ->
        # platform-scoped; header present -> tenant-scoped. A present
        # but empty value is malformed plane output - fail closed
        # (NotAuthenticated) rather than guess a scope in either
        # direction: defaulting to platform scope would WIDEN
        # visibility, which this policy must never do.
        tenant_scope: str | None = None
        raw_tenant = normalized.get(TENANT_SCOPE_HEADER)
        if raw_tenant is not None:
            tenant_scope = raw_tenant.strip()
            if not tenant_scope:
                raise NotAuthenticated(
                    f"the {TENANT_SCOPE_HEADER} header is present "
                    "but empty; a malformed tenant scope is rejected "
                    "rather than defaulted (TR-16 fail-closed)"
                )

        return Principal(
            subject=subject,
            groups=groups,
            roles=tuple(roles),
            tenant_scope=tenant_scope,
        )


__all__ = [
    "GROUP_DELIMITER",
    "parse_groups",
    "AdminAccessRoleMapping",
    "AdminAccessPlaneSecurityPolicy",
]
