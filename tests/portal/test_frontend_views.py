"""Offline tests for the management portal frontend (Batch 21
Task 3).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 21 validator - never under pytest. The real
single-pane access contract drives the navigation assertions; every
endpoint value is a synthetic RFC 6761 .example host injected through
the deployment-provided endpoints mapping - no socket is opened and
no real host is named anywhere.

Covers the Task 3 completion check:

- the navigation page renders one outbound link per cataloged
  wrapped UI, resolved from the injected endpoints mapping;
- the config editor page carries the unified config document in a
  form posting to the contract's plan/commit routes and surfaces
  both a passing ConfigPlanResult (changed paths) and a rejection
  (per-error list);
- the tenants page renders rows for the given tenant payloads with
  the five contract lifecycle action forms (admin only);
- the health page renders per-plane status badges;
- XSS: attacker-influenced values (tenant names) appear only
  escaped, and no page contains a <script> tag;
- no literal URL, hostname, or IP appears in any shipped template,
  stylesheet, or the frontend module itself.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS = REPO_ROOT / "contracts"
SINGLE_PANE_CONTRACT = (
    CONTRACTS / "management" / "SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
)
SAMPLE_DOCUMENT = (
    CONTRACTS / "management" / "samples" / "VALID_UNIFIED_CONFIG.json"
)
PORTAL_PKG = REPO_ROOT / "services" / "portal" / "portalsvc"

sys.path.insert(0, str(REPO_ROOT / "services" / "portal"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from portalsvc.catalog import load_ui_catalog  # noqa: E402
from portalsvc.frontend import (  # noqa: E402
    COMMIT_RESULT_KEY,
    LIFECYCLE_ACTIONS,
    LIFECYCLE_FORM_FIELDS,
    PLAN_RESULT_KEY,
    PortalFrontendRenderer,
)
from portalsvc.models import (  # noqa: E402
    CommitResult,
    ConfigPlanResult,
    FrontendRenderer,
    HealthSignal,
    HealthStatus,
    HealthSummary,
    PlaneHealth,
    PortalRole,
    Principal,
)

CATALOG = load_ui_catalog(SINGLE_PANE_CONTRACT)

# Deployment-provided endpoints mapping: one synthetic .example host
# per catalog entry, keyed by the entry's profile_key (or its id for
# the documented null-profile_key Argo CD exception).
ENDPOINTS: dict[str, str] = {
    (entry.endpoint_profile_key or entry.id): (
        f"https://{entry.id}.portal.example"
    )
    for entry in CATALOG
}

ADMIN = Principal(
    subject="platform-operator",
    groups=("obskit-platform-admins",),
    roles=(PortalRole.ADMIN,),
)
READONLY = Principal(
    subject="platform-viewer",
    groups=("obskit-platform-readonly",),
    roles=(PortalRole.READONLY,),
)
TENANT_SCOPED = Principal(
    subject="tenant-operator",
    groups=("obskit-tenant-a-admins",),
    roles=(PortalRole.ADMIN,),
    tenant_scope="tenant-a",
)

TENANT_A: dict[str, Any] = {
    "tenant_id": "tenant-a",
    "display_name": "Tenant A",
    "lifecycle_state": "active",
    "tier": "standard",
    "isolation_class": "namespace",
}
TENANT_B: dict[str, Any] = {
    "tenant_id": "tenant-b",
    "display_name": "Tenant B",
    "lifecycle_state": "suspended",
    "tier": "premium",
    "isolation_class": "dedicated-nodepool",
}

HEALTH_SUMMARY = HealthSummary(
    overall=HealthStatus.DEGRADED,
    planes=(
        PlaneHealth(
            plane="collector",
            status=HealthStatus.OK,
            signals=(
                HealthSignal(
                    name="collector_pipeline_up",
                    status=HealthStatus.OK,
                    detail="all pipelines reporting",
                ),
            ),
        ),
        PlaneHealth(
            plane="backend",
            status=HealthStatus.DEGRADED,
            signals=(
                HealthSignal(
                    name="opensearch_cluster_status",
                    status=HealthStatus.DEGRADED,
                    detail="yellow: replica shards unassigned",
                ),
            ),
        ),
        PlaneHealth(
            plane="install_discovery",
            status=HealthStatus.UNKNOWN,
            signals=(
                HealthSignal(
                    name="preflight_report_age",
                    status=HealthStatus.UNKNOWN,
                ),
            ),
        ),
    ),
)


def _renderer() -> PortalFrontendRenderer:
    return PortalFrontendRenderer(endpoints=ENDPOINTS)


def _render(view: str, context: Mapping[str, Any]) -> str:
    page = _renderer().render_view(view, context)
    assert page.status_code == 200, (
        f"view {view!r} rendered status {page.status_code}"
    )
    assert page.html.lstrip().lower().startswith("<!doctype html>")
    assert "<script" not in page.html.lower()
    return page.html


def _document() -> dict[str, Any]:
    return json.loads(SAMPLE_DOCUMENT.read_text(encoding="utf-8"))


def test_renderer_satisfies_protocol() -> None:
    # FrontendRenderer is a plain (non-runtime_checkable) Protocol;
    # the annotation is the static check, the attribute check the
    # runtime one.
    renderer: FrontendRenderer = _renderer()
    assert callable(getattr(renderer, "render_view", None))


def test_navigation_links_every_catalog_entry() -> None:
    page = _render(
        "navigation", {"principal": READONLY, "entries": CATALOG}
    )
    assert len(CATALOG) >= 4
    for entry in CATALOG:
        assert f'id="entry-{entry.id}"' in page, entry.id
        assert html.escape(entry.display_name) in page, entry.id
        href = ENDPOINTS[entry.endpoint_profile_key or entry.id]
        assert f'href="{html.escape(href, quote=True)}"' in page, (
            f"{entry.id} did not resolve to its injected endpoint"
        )
    assert page.count('class="catalog-entry"') == len(CATALOG)
    # The caller's identity and roles are shown.
    assert "platform-viewer" in page
    assert PortalRole.READONLY.value in page


def test_navigation_unresolved_entry_renders_without_link() -> None:
    page = _render(
        "navigation", {"principal": READONLY, "entries": CATALOG}
    )
    assert "endpoint unresolved" not in page
    empty = PortalFrontendRenderer(endpoints={})
    bare = empty.render_view(
        "navigation", {"principal": READONLY, "entries": CATALOG}
    ).html
    assert bare.count("endpoint unresolved") == len(CATALOG)
    assert 'class="outbound"' not in bare


def test_config_editor_shows_document_and_contract_actions() -> None:
    document = _document()
    page = _render(
        "config", {"principal": ADMIN, "document": document}
    )
    expected = html.escape(
        json.dumps(document, indent=2, sort_keys=True), quote=True
    )
    assert expected in page, (
        "config editor does not carry the unified config document"
    )
    assert "<textarea" in page
    assert 'action="/api/v1/config/plan"' in page
    assert 'formaction="/api/v1/config/plan"' in page
    assert 'formaction="/api/v1/config/commit"' in page


def test_config_editor_hides_actions_for_readonly() -> None:
    # The backend already gates /config at portal-admin; the
    # frontend additionally renders no mutating form for a
    # readonly principal (defense in depth).
    page = _render(
        "config", {"principal": READONLY, "document": _document()}
    )
    assert "<form" not in page
    assert "<textarea" not in page
    assert 'class="config-document"' in page


def test_config_plan_valid_surfaces_changed_paths() -> None:
    plan = ConfigPlanResult(
        valid=True,
        changed_paths=(
            "gitops/rendered/collector/values.yaml",
            "gitops/rendered/search/ilm-policy.json",
        ),
        errors=(),
    )
    page = _render(
        "config",
        {
            "principal": ADMIN,
            "document": _document(),
            PLAN_RESULT_KEY: plan,
        },
    )
    assert 'class="plan-result plan-valid"' in page
    for path in plan.changed_paths:
        assert html.escape(path) in page, path


def test_config_plan_rejection_surfaces_errors() -> None:
    plan = ConfigPlanResult(
        valid=False,
        changed_paths=(),
        errors=(
            "document does not validate against "
            "UNIFIED_CONFIG_SCHEMA_V1.json: 'retention_days' is "
            "not of type 'integer'",
            "unknown top-level key 'extra'",
        ),
    )
    page = _render(
        "config",
        {
            "principal": ADMIN,
            "document": _document(),
            PLAN_RESULT_KEY: plan,
        },
    )
    assert 'class="plan-result plan-rejected"' in page
    for error in plan.errors:
        assert html.escape(error) in page, error
    assert 'class="plan-valid"' not in page


def test_config_commit_result_surfaced() -> None:
    commit = CommitResult(
        commit_reference="prepared-commit-0123abcd",
        commit_message="portal: unified config edit",
        written_paths=("gitops/rendered/collector/values.yaml",),
    )
    page = _render(
        "config",
        {
            "principal": ADMIN,
            "document": _document(),
            COMMIT_RESULT_KEY: commit,
        },
    )
    assert "prepared-commit-0123abcd" in page
    assert html.escape(commit.written_paths[0]) in page


def test_tenants_rows_and_lifecycle_action_forms() -> None:
    page = _render(
        "tenants",
        {"principal": ADMIN, "tenants": [TENANT_A, TENANT_B]},
    )
    for tenant in (TENANT_A, TENANT_B):
        for value in tenant.values():
            assert html.escape(str(value)) in page, value
        for action in LIFECYCLE_ACTIONS:
            expected = (
                f'action="/api/v1/tenants/{tenant["tenant_id"]}'
                f'/lifecycle/{action}"'
            )
            assert expected in page, expected
    assert set(LIFECYCLE_ACTIONS) == {
        "provision",
        "suspend",
        "resume",
        "offboard",
        "purge",
    }
    assert page.count('class="tenant-row"') == 2


def test_tenants_readonly_gets_no_action_forms() -> None:
    page = _render(
        "tenants", {"principal": READONLY, "tenants": [TENANT_A]}
    )
    assert "<form" not in page
    assert "/lifecycle/" not in page


def test_tenants_scoped_principal_sees_only_given_tenant() -> None:
    # The backend forwards only the caller's tenant; the view must
    # render exactly what it is given and add no cross-tenant link.
    page = _render(
        "tenants",
        {"principal": TENANT_SCOPED, "tenants": [TENANT_A]},
    )
    assert "tenant-a" in page
    assert "tenant-b" not in page
    assert page.count('class="tenant-row"') == 1


def test_tenants_empty_list_renders_placeholder_row() -> None:
    page = _render(
        "tenants", {"principal": READONLY, "tenants": []}
    )
    assert "No tenants are visible" in page


def _action_form(page: str, tenant_id: str, action: str) -> str:
    """Extract one lifecycle <form> element from a tenants page."""
    marker = (
        f'action="/api/v1/tenants/{tenant_id}/lifecycle/{action}"'
    )
    anchor = page.index(marker)
    start = page.rindex("<form", 0, anchor)
    end = page.index("</form>", anchor)
    return page[start:end]


def test_lifecycle_forms_carry_contract_fields() -> None:
    # parse_transition_request contract, given the adapter's
    # form-post semantics: actor is injected from the principal
    # (never a form field), empty optional inputs drop server-side,
    # dotted names nest into the approval block.
    page = _render(
        "tenants", {"principal": ADMIN, "tenants": [TENANT_A]}
    )
    assert 'name="actor"' not in page

    provision = _action_form(page, "tenant-a", "provision")
    assert "<input" not in provision

    suspend = _action_form(page, "tenant-a", "suspend")
    assert (
        '<input type="hidden" name="trigger_type" value="operator">'
        in suspend
    )
    assert (
        '<input type="text" name="reason" placeholder="reason" '
        "required>" in suspend
    )
    assert "approval" not in suspend

    resume = _action_form(page, "tenant-a", "resume")
    assert (
        '<input type="text" name="reason" placeholder="reason" '
        "required>" in resume
    )
    assert "trigger_type" not in resume
    assert "approval" not in resume

    approval_inputs = (
        '<input type="text" name="approval.approval_id" ',
        '<input type="text" name="approval.approver" ',
        '<input type="text" name="approval.decided_at" ',
        '<input type="hidden" name="approval.decision" '
        'value="approved">',
    )
    offboard = _action_form(page, "tenant-a", "offboard")
    assert (
        '<input type="text" name="reason" placeholder="reason" '
        "required>" in offboard
    )
    for fragment in approval_inputs:
        assert fragment in offboard, fragment

    purge = _action_form(page, "tenant-a", "purge")
    assert (
        '<input type="text" name="reason" '
        'placeholder="reason (optional)">' in purge
    )
    assert "required" not in purge
    for fragment in approval_inputs:
        assert fragment in purge, fragment

    # The exported field catalog covers exactly the five transitions.
    assert set(LIFECYCLE_FORM_FIELDS) == set(LIFECYCLE_ACTIONS)


def test_navigation_href_scheme_guard() -> None:
    entry = CATALOG[0]
    key = entry.endpoint_profile_key or entry.id

    # Any non-https scheme renders linkless (defense in depth).
    for hostile_value in (
        "javascript:alert(1)",
        "JAVASCRIPT:alert(1)",
        "data:text/html,x",
    ):
        hostile = dict(ENDPOINTS, **{key: hostile_value})
        page = PortalFrontendRenderer(
            endpoints=hostile
        ).render_view(
            "navigation",
            {"principal": READONLY, "entries": CATALOG},
        ).html
        assert 'href="javascript' not in page.lower(), hostile_value
        assert 'href="data' not in page.lower(), hostile_value
        assert "alert(1)" not in page, hostile_value
        assert page.count("endpoint unresolved") == 1

    insecure = dict(
        ENDPOINTS, **{key: "http://insecure.portal.example"}
    )
    page = PortalFrontendRenderer(endpoints=insecure).render_view(
        "navigation", {"principal": READONLY, "entries": CATALOG}
    ).html
    assert "insecure.portal.example" not in page
    assert page.count("endpoint unresolved") == 1

    # A bare host (no scheme) gets https prefixed: the profile
    # constrains every wrapped UI to TLS.
    bare = dict(ENDPOINTS, **{key: "bare-host.portal.example"})
    page = PortalFrontendRenderer(endpoints=bare).render_view(
        "navigation", {"principal": READONLY, "entries": CATALOG}
    ).html
    assert 'href="https://bare-host.portal.example"' in page
    assert "endpoint unresolved" not in page


def test_health_renders_per_plane_badges() -> None:
    page = _render(
        "health", {"principal": READONLY, "summary": HEALTH_SUMMARY}
    )
    assert 'class="plane plane-ok"' in page
    assert 'class="plane plane-degraded"' in page
    assert 'class="plane plane-unknown"' in page
    for plane in HEALTH_SUMMARY.planes:
        assert html.escape(plane.plane) in page, plane.plane
        for signal in plane.signals:
            assert html.escape(signal.name) in page, signal.name
            if signal.detail is not None:
                assert html.escape(signal.detail) in page
    # Overall rollup badge.
    assert 'class="badge status-degraded"' in page


def test_xss_tenant_name_is_escaped() -> None:
    hostile = dict(
        TENANT_A, display_name="<script>alert(1)</script>"
    )
    page = _render(
        "tenants", {"principal": ADMIN, "tenants": [hostile]}
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script" not in page.lower()


def test_xss_config_errors_are_escaped() -> None:
    plan = ConfigPlanResult(
        valid=False,
        changed_paths=(),
        errors=('<img src=x onerror="alert(1)"> bad value',),
    )
    page = _render(
        "config",
        {
            "principal": ADMIN,
            "document": {"key": "<b>bold</b>"},
            PLAN_RESULT_KEY: plan,
        },
    )
    assert "<img" not in page
    assert "&lt;img" in page
    assert "<b>bold</b>" not in page


def test_no_hardcoded_url_or_host_in_shipped_frontend() -> None:
    # fail_if_hardcoded_endpoint: hrefs come exclusively from the
    # injected endpoints mapping. Nothing shipped in the package may
    # name a URL, hostname, or IP.
    # A scheme followed by an actual host character: the bare
    # "https://" prefix constant in _safe_href names no host and is
    # exactly the mechanism that keeps hosts deployment-provided.
    url_pattern = re.compile(r"https?://[A-Za-z0-9\[]", re.IGNORECASE)
    ip_pattern = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
    shipped = [
        PORTAL_PKG / "frontend.py",
        *sorted((PORTAL_PKG / "templates").glob("*.html")),
        *sorted((PORTAL_PKG / "static").glob("*.css")),
    ]
    assert len(shipped) >= 7, [str(path) for path in shipped]
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        assert not url_pattern.search(text), f"URL in {path}"
        assert not ip_pattern.search(text), f"IP in {path}"
        assert ".example" not in text, f"hostname in {path}"


def test_templates_contain_no_script_or_inline_handlers() -> None:
    handler_pattern = re.compile(r"\son[a-z]+\s*=", re.IGNORECASE)
    for path in sorted((PORTAL_PKG / "templates").glob("*.html")):
        text = path.read_text(encoding="utf-8")
        assert "<script" not in text.lower(), str(path)
        assert not handler_pattern.search(text), str(path)


def test_unknown_view_is_a_404_page() -> None:
    page = _renderer().render_view(
        "not-a-view", {"principal": READONLY}
    )
    assert page.status_code == 404
    assert "not part of the portal contract" in page.html


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
