"""Offline tests for portal SSO role mapping and tenant scoping
(Batch 21 Task 4, TR-03/TR-16/TR-17).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 21 validator - never under pytest. No socket is
ever opened: the control plane client runs against the same fake
opener double test_backend_core.py uses.

Covers the Task 4 completion check:

- header_trust_boundary: authenticated routes reject requests missing
  the subject or groups identity headers (NotAuthenticated);
- role mapping consistent with the single-pane access contract:
  exactly role_mapping.readonly_group -> portal-readonly and
  role_mapping.admin_group -> portal-admin (admin implies readonly
  grants), unmapped groups map to no role (Forbidden), no third plane
  group exists;
- group header parsing: comma delimiter, whitespace stripping, empty
  segments dropped, duplicates deduplicated, header-name case
  insensitivity;
- tenant scoping (TR-16): tenant header -> tenant-scoped Principal
  that lists only its own tenant and is denied cross-tenant reads and
  transitions BEFORE any delegation; no tenant header ->
  platform-scoped Principal; the platform-wide config view requires
  platform scope even for tenant-scoped admins;
- the tenantctl HTTP adapter's caller_scope_from_headers helper binds
  the same x-portal-tenant header to the service-layer caller_scope
  (the Batch 20 gap), importable without FastAPI, with the malformed
  (present-but-empty) header failing closed.

All group and tenant names below are synthetic placeholders.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
PORTAL_CONTRACT = (
    REPO_ROOT / "contracts" / "management" / "PORTAL_CONTRACT_V1.yaml"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "portal"))
sys.path.insert(0, str(REPO_ROOT / "services" / "tenancy"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from portalsvc import models  # noqa: E402
from portalsvc.catalog import (  # noqa: E402
    ADMIN_PLANE_GROUP,
    READONLY_PLANE_GROUP,
)
from portalsvc.models import (  # noqa: E402
    Forbidden,
    GROUPS_HEADER,
    NotAuthenticated,
    PortalRole,
    Principal,
    SUBJECT_HEADER,
    TENANT_SCOPE_HEADER,
    TenantScopeDenied,
    require_platform_scope,
)
from portalsvc.security import (  # noqa: E402
    AdminAccessPlaneSecurityPolicy,
    AdminAccessRoleMapping,
    GROUP_DELIMITER,
    parse_groups,
)
from portalsvc.tenants import (  # noqa: E402
    HttpControlPlaneClient,
    PortalTenantService,
)

import tenantctl.api as tenantctl_api  # noqa: E402

# Synthetic placeholders only (no real environment values). The
# mapping is DATA injected from a deployed admin-access profile's
# role_mapping block, never hardcoded policy.
READONLY_GROUP = "obs-platform-viewers"
ADMIN_GROUP = "obs-platform-admins"
POLICY = AdminAccessPlaneSecurityPolicy(
    role_mapping=AdminAccessRoleMapping(
        readonly_group=READONLY_GROUP,
        admin_group=ADMIN_GROUP,
    ),
    authn_provider="oidc",
    mfa_required=True,
)

# Synthetic placeholder only (RFC 6761 example domain); no socket is
# ever opened - the fake opener below intercepts every request.
FAKE_BASE_URL = "http://control-plane.example/api/tenancy/v1"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._raw = json.dumps(payload).encode("utf-8")
        self.status = 200

    def read(self) -> bytes:
        return self._raw


class _FakeOpener:
    """In-process urllib double: records requests, opens no socket."""

    def __init__(
        self, payload: dict[str, Any] | None = None
    ) -> None:
        self.payload = payload if payload is not None else {}
        self.requests: list[Any] = []

    def __call__(self, request: Any, timeout: float) -> _FakeResponse:
        self.requests.append(request)
        return _FakeResponse(self.payload)


def _expect(exc_type: type[BaseException], func) -> BaseException:
    try:
        func()
    except exc_type as error:
        return error
    raise AssertionError(f"expected {exc_type.__name__}")


def test_missing_identity_headers_are_not_authenticated() -> None:
    # header_trust_boundary: the portal rejects requests missing the
    # subject or groups headers on every authenticated route.
    for headers in (
        {},
        {SUBJECT_HEADER: "op@example.com"},
        {GROUPS_HEADER: READONLY_GROUP},
        {SUBJECT_HEADER: "", GROUPS_HEADER: READONLY_GROUP},
        {SUBJECT_HEADER: "   ", GROUPS_HEADER: READONLY_GROUP},
        # Groups header present but carrying no group membership.
        {SUBJECT_HEADER: "op@example.com", GROUPS_HEADER: ""},
        {SUBJECT_HEADER: "op@example.com", GROUPS_HEADER: "  , ,"},
    ):
        error = _expect(
            NotAuthenticated,
            lambda h=headers: POLICY.principal_for(h),
        )
        assert error.http_status == 401


def test_role_mapping_follows_the_contract() -> None:
    # readonly_group membership -> portal-readonly only.
    reader = POLICY.principal_for(
        {
            SUBJECT_HEADER: "viewer@example.com",
            GROUPS_HEADER: READONLY_GROUP,
        }
    )
    assert reader.subject == "viewer@example.com"
    assert reader.roles == (PortalRole.READONLY,)
    assert reader.has_role(PortalRole.READONLY)
    assert not reader.has_role(PortalRole.ADMIN)
    assert reader.is_platform_scoped

    # admin_group membership -> portal-admin, which grants everything
    # portal-readonly grants (contract role_mapping.grants).
    admin = POLICY.principal_for(
        {
            SUBJECT_HEADER: "op@example.com",
            GROUPS_HEADER: ADMIN_GROUP,
        }
    )
    assert PortalRole.ADMIN in admin.roles
    assert admin.has_role(PortalRole.ADMIN)
    assert admin.has_role(PortalRole.READONLY)

    # Membership in both mapped groups carries both roles.
    both = POLICY.principal_for(
        {
            SUBJECT_HEADER: "op@example.com",
            GROUPS_HEADER: f"{READONLY_GROUP},{ADMIN_GROUP}",
        }
    )
    assert set(both.roles) == {PortalRole.READONLY, PortalRole.ADMIN}

    # Unmapped groups are ignored; mapping to NO portal role is an
    # authenticated-but-unauthorized caller (403, not 401).
    error = _expect(
        Forbidden,
        lambda: POLICY.principal_for(
            {
                SUBJECT_HEADER: "outsider@example.com",
                GROUPS_HEADER: "finance-team,random-group",
            }
        ),
    )
    assert error.http_status == 403

    # Unmapped groups alongside a mapped one add no grant.
    mixed = POLICY.principal_for(
        {
            SUBJECT_HEADER: "viewer@example.com",
            GROUPS_HEADER: f"finance-team,{READONLY_GROUP}",
        }
    )
    assert mixed.roles == (PortalRole.READONLY,)


def test_group_header_parsing() -> None:
    # Comma delimiter, whitespace stripping, empty segments dropped,
    # duplicates removed, order preserved.
    assert GROUP_DELIMITER == ","
    assert parse_groups(
        f"  {READONLY_GROUP} , other ,, {READONLY_GROUP} ,"
    ) == (READONLY_GROUP, "other")
    assert parse_groups("   ") == ()

    principal = POLICY.principal_for(
        {
            SUBJECT_HEADER: "  viewer@example.com  ",
            GROUPS_HEADER: f" {READONLY_GROUP} ,, other , ",
        }
    )
    assert principal.subject == "viewer@example.com"
    assert principal.groups == (READONLY_GROUP, "other")

    # Header names are case-insensitive.
    upper = POLICY.principal_for(
        {
            "X-Portal-User": "viewer@example.com",
            "X-Portal-Groups": READONLY_GROUP,
            "X-Portal-Tenant": "tenant-a",
        }
    )
    assert upper.roles == (PortalRole.READONLY,)
    assert upper.tenant_scope == "tenant-a"


def test_tenant_scoping_constructs_the_principal_faithfully() -> None:
    # Header present -> tenant-scoped (TR-16); absent ->
    # platform-scoped (CTR-07 span).
    scoped = POLICY.principal_for(
        {
            SUBJECT_HEADER: "acme-op@example.com",
            GROUPS_HEADER: ADMIN_GROUP,
            TENANT_SCOPE_HEADER: " acme ",
        }
    )
    assert scoped.tenant_scope == "acme"
    assert not scoped.is_platform_scoped

    platform = POLICY.principal_for(
        {
            SUBJECT_HEADER: "op@example.com",
            GROUPS_HEADER: ADMIN_GROUP,
        }
    )
    assert platform.is_platform_scoped

    # The platform-wide config view: a platform principal passes
    # require_platform_scope; a tenant-scoped principal fails it even
    # with the admin role (models.require_platform_scope enforces
    # this - verified here, not duplicated in the policy).
    require_platform_scope(platform)
    error = _expect(
        Forbidden, lambda: require_platform_scope(scoped)
    )
    assert error.http_status == 403

    # Present-but-empty tenant header is malformed plane output:
    # fail closed (never default to the wider platform scope).
    _expect(
        NotAuthenticated,
        lambda: POLICY.principal_for(
            {
                SUBJECT_HEADER: "op@example.com",
                GROUPS_HEADER: ADMIN_GROUP,
                TENANT_SCOPE_HEADER: "   ",
            }
        ),
    )


def test_scoped_principal_never_sees_another_tenant() -> None:
    # End-to-end with the Task 2 core: a policy-built tenant-scoped
    # principal drives PortalTenantService against a fake opener.
    scoped_admin = POLICY.principal_for(
        {
            SUBJECT_HEADER: "acme-op@example.com",
            GROUPS_HEADER: ADMIN_GROUP,
            TENANT_SCOPE_HEADER: "acme",
        }
    )
    opener = _FakeOpener(payload={"tenant_id": "acme"})
    service = PortalTenantService(
        HttpControlPlaneClient(FAKE_BASE_URL, opener=opener)
    )

    # Listing yields only the principal's own tenant, via a
    # scope-forwarded get (TR-16).
    listed = service.list_tenants(scoped_admin)
    assert listed == {"tenants": [{"tenant_id": "acme"}]}
    request = opener.requests[-1]
    assert request.full_url == f"{FAKE_BASE_URL}/tenants/acme"
    assert request.get_header("X-portal-tenant") == "acme"
    assert request.get_header("X-portal-user") == (
        "acme-op@example.com"
    )

    # Cross-tenant read and transition are denied BEFORE any
    # delegation: no HTTP request happens.
    seen = len(opener.requests)
    _expect(
        TenantScopeDenied,
        lambda: service.get_tenant("globex", scoped_admin),
    )
    _expect(
        TenantScopeDenied,
        lambda: service.transition(
            "suspend", "globex", {}, scoped_admin
        ),
    )
    assert len(opener.requests) == seen


def test_caller_scope_from_headers_binds_the_batch20_gap() -> None:
    # The helper is pure and import-safe without FastAPI: reaching
    # this point proves the import; the guard flag records whether
    # FastAPI happened to be installed, and the helper never needs it.
    assert isinstance(tenantctl_api._FASTAPI_AVAILABLE, bool)
    helper = tenantctl_api.caller_scope_from_headers

    # Same trusted header names as the portal contract pins.
    assert tenantctl_api.TENANT_SCOPE_HEADER == TENANT_SCOPE_HEADER
    assert tenantctl_api.SUBJECT_HEADER == SUBJECT_HEADER
    assert tenantctl_api.GROUPS_HEADER == GROUPS_HEADER

    # Platform caller: no tenant header -> None (identity headers do
    # not change that; scope derives from x-portal-tenant only).
    assert helper({}) is None
    assert helper(
        {
            SUBJECT_HEADER: "op@example.com",
            GROUPS_HEADER: ADMIN_GROUP,
        }
    ) is None

    # Scoped caller: header value, whitespace-stripped, matched
    # case-insensitively by header name.
    assert helper({TENANT_SCOPE_HEADER: "acme"}) == "acme"
    assert helper({"X-Portal-Tenant": " acme "}) == "acme"
    # Scope narrows regardless of identity header presence.
    assert helper(
        {TENANT_SCOPE_HEADER: "acme", SUBJECT_HEADER: "op@x.example"}
    ) == "acme"

    # Malformed rule (documented in tenantctl.api): present but
    # empty/whitespace -> empty string, a scope matching NO tenant,
    # so the service layer denies everything. Never None (that would
    # widen a malformed caller to platform scope).
    assert helper({TENANT_SCOPE_HEADER: ""}) == ""
    assert helper({TENANT_SCOPE_HEADER: "   "}) == ""


def test_role_mapping_is_consistent_with_the_single_pane_contract() -> None:
    # The plane defines exactly two mapped groups
    # (role_mapping.readonly_group and role_mapping.admin_group); the
    # policy's injected mapping has exactly those two slots - no
    # third group invented.
    field_names = tuple(
        field.name
        for field in dataclasses.fields(AdminAccessRoleMapping)
    )
    assert field_names == ("readonly_group", "admin_group")
    assert READONLY_PLANE_GROUP == "role_mapping.readonly_group"
    assert ADMIN_PLANE_GROUP == "role_mapping.admin_group"
    for field_name in field_names:
        assert f"role_mapping.{field_name}" in (
            READONLY_PLANE_GROUP,
            ADMIN_PLANE_GROUP,
        )

    # The portal contract pins the same headers, plane groups, and
    # portal role names this policy implements (read as text: the
    # test stays stdlib-only, no YAML parser).
    contract_text = PORTAL_CONTRACT.read_text(encoding="utf-8")
    for needle in (
        f"subject: {SUBJECT_HEADER}",
        f"groups: {GROUPS_HEADER}",
        f"tenant_scope: {TENANT_SCOPE_HEADER}",
        f"plane_group: {READONLY_PLANE_GROUP}",
        f"plane_group: {ADMIN_PLANE_GROUP}",
        f"portal_role: {PortalRole.READONLY.value}",
        f"portal_role: {PortalRole.ADMIN.value}",
    ):
        assert needle in contract_text, needle
    # Exactly the two contract role_mapping entries, no third.
    assert contract_text.count("plane_group:") >= 2
    assert contract_text.count("portal_role:") == 2

    # An empty group name in the deployed profile data fails loudly
    # at construction instead of denying everyone silently.
    try:
        AdminAccessRoleMapping(readonly_group=" ", admin_group="x")
    except ValueError:
        pass
    else:
        raise AssertionError(
            "expected an empty role_mapping group to be rejected"
        )

    # The policy satisfies the models.SecurityPolicy protocol slot
    # the API adapter injects (structural check - the protocol is not
    # runtime_checkable, so isinstance is unavailable by design).
    assert callable(getattr(POLICY, "principal_for", None))
    assert models.SecurityPolicy is not None


def main() -> int:
    tests = [
        (name, func)
        for name, func in sorted(globals().items())
        if name.startswith("test_") and callable(func)
    ]
    for name, func in tests:
        func()
        print(f"PASS {name}")
    print(f"{len(tests)} tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
