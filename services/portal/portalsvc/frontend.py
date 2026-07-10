"""Server-rendered HTML frontend for the management portal.

Implements the FrontendRenderer protocol of portalsvc.models for the
four html_routes views fixed by
contracts/management/PORTAL_CONTRACT_V1.yaml (Batch 21 Task 3,
TR-22, ADR-0005). Design constraints, verbatim from the ADR:

- Pages are assembled from string.Template page templates shipped
  inside the package (templates/) and styled by the one static CSS
  file (static/portal.css). Because the portal contract's
  api_surface is exhaustive and defines no static-asset route, the
  CSS is inlined into the layout at import time instead of being
  served separately.
- No client-side framework, no npm, no bundler, no vendored
  third-party JavaScript, and no <script> tag anywhere: every portal
  function is a read, a plain-HTML form post, or an outbound link.
- Config-editor schema validation is server-side (ConfigFlow through
  the Batch 19 renderer); this layer only SURFACES the resulting
  ConfigPlanResult / CommitResult when the caller places one in the
  render context.
- No URL, hostname, or IP is ever stored or embedded
  (fail_if_hardcoded_endpoint): navigation hrefs resolve per request
  from the deployment-provided endpoints mapping injected at
  construction, via portalsvc.catalog.resolve_endpoint.

Every dynamic value is escaped with html.escape before it reaches a
template: tenant names, config text, and error messages are
attacker-influenced (XSS).
"""

from __future__ import annotations

import html
import json
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from string import Template
from typing import Any, Mapping

from portalsvc.catalog import resolve_endpoint
from portalsvc.models import (
    CatalogEntry,
    CommitResult,
    ConfigPlanResult,
    HealthSummary,
    PortalRole,
    Principal,
    RenderedPage,
    TenantSummary,
)

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"
_CSS_FILE = _PACKAGE_DIR / "static" / "portal.css"

# Context keys the API adapter passes on no-JS form posts to
# surface the server-side validation outcome in the config view.
PLAN_RESULT_KEY = "plan_result"
COMMIT_RESULT_KEY = "commit_result"

# Lifecycle transitions, verbatim from the portal contract
# api_surface json_routes (delegated one-to-one to the Batch 20
# control plane).
LIFECYCLE_ACTIONS: tuple[str, ...] = (
    "provision",
    "suspend",
    "resume",
    "offboard",
    "purge",
)

VIEW_TITLES: Mapping[str, str] = {
    "navigation": "Wrapped UI navigation",
    "config": "Unified configuration editor",
    "tenants": "Tenant management",
    "health": "Platform health overview",
}


def _load_template(name: str) -> Template:
    return Template(
        (_TEMPLATES_DIR / name).read_text(encoding="utf-8")
    )


_LAYOUT = _load_template("layout.html")
_NAVIGATION = _load_template("navigation.html")
_CONFIG = _load_template("config.html")
_TENANTS = _load_template("tenants.html")
_HEALTH = _load_template("health.html")
_CSS = _CSS_FILE.read_text(encoding="utf-8")

# Row-level fragments. Also string.Template so the whole HTML
# surface stays in one templating mechanism (ADR-0005); they live
# here rather than in per-fragment files to keep the template set
# page-scoped.
_NAV_ENTRY = Template(
    '<li class="catalog-entry" id="entry-$entry_id">'
    '<span class="entry-name">$display_name</span>'
    '<span class="entry-system">$system</span>'
    "$link"
    "</li>"
)
_NAV_LINK = Template(
    '<a class="outbound" href="$href" '
    'rel="noopener noreferrer">Open $display_name</a>'
)
_NAV_UNRESOLVED = (
    '<span class="unresolved">endpoint unresolved</span>'
)
_CONFIG_FORM = Template(
    '<form class="config-editor" method="post" '
    'action="/api/v1/config/plan">'
    '<textarea name="document" rows="24" '
    'aria-label="Unified configuration document">'
    "$document</textarea>"
    '<p class="actions">'
    '<button type="submit" '
    'formaction="/api/v1/config/plan">Validate (plan)</button>'
    '<button type="submit" '
    'formaction="/api/v1/config/commit">Commit</button>'
    "</p>"
    "</form>"
)
_CONFIG_READONLY = Template(
    '<pre class="config-document">$document</pre>'
)
_PLAN_VALID = Template(
    '<section class="plan-result plan-valid">'
    "<h2>Plan valid</h2>"
    "<p>Changed paths (dry-run, nothing written):</p>"
    '<ul class="changed-paths">$changed_paths</ul>'
    "</section>"
)
_PLAN_REJECTED = Template(
    '<section class="plan-result plan-rejected">'
    "<h2>Edit rejected</h2>"
    "<p>Schema validation failed; nothing was written:</p>"
    '<ul class="plan-errors">$errors</ul>'
    "</section>"
)
_COMMIT_RESULT = Template(
    '<section class="plan-result commit-result">'
    "<h2>Commit prepared</h2>"
    '<p>Reference <code>$commit_reference</code>: '
    "$commit_message</p>"
    '<ul class="written-paths">$written_paths</ul>'
    "</section>"
)
_TENANT_ROW = Template(
    '<tr class="tenant-row" id="tenant-$row_id">'
    '<td class="tenant-id">$tenant_id</td>'
    "<td>$display_name</td>"
    "<td>$lifecycle_state</td>"
    "<td>$tier</td>"
    "<td>$isolation_class</td>"
    '<td class="tenant-actions">$actions</td>'
    "</tr>"
)
_TENANT_ACTION = Template(
    '<form class="lifecycle-action" method="post" '
    'action="/api/v1/tenants/$tenant_path/lifecycle/$action">'
    "$fields"
    '<button type="submit">$label</button>'
    "</form>"
)

# Per-transition form fields matching the control plane's
# parse_transition_request contract, given the adapter's form-post
# semantics: urlencoded fields with empty values are DROPPED
# server-side (untouched optional input = absent field), dotted
# names NEST (approval.approver -> body["approval"]["approver"]),
# and `actor` is injected from the authenticated principal - so no
# form ever carries an actor field. The approval fieldset is
# optional: leaving its text inputs empty drops them server-side and
# yields the contract-correct approval-required denial. All field
# fragments are static markup (no dynamic values), so nothing here
# needs escaping.
_APPROVAL_FIELDSET = (
    '<fieldset class="approval">'
    "<legend>Approval (optional)</legend>"
    '<input type="text" name="approval.approval_id" '
    'placeholder="approval id">'
    '<input type="text" name="approval.approver" '
    'placeholder="approver">'
    '<input type="text" name="approval.decided_at" '
    'placeholder="decided at (ISO-8601)">'
    '<input type="hidden" name="approval.decision" value="approved">'
    "</fieldset>"
)
_REASON_REQUIRED = (
    '<input type="text" name="reason" placeholder="reason" required>'
)
_REASON_OPTIONAL = (
    '<input type="text" name="reason" '
    'placeholder="reason (optional)">'
)
LIFECYCLE_FORM_FIELDS: Mapping[str, str] = {
    "provision": "",
    "suspend": (
        '<input type="hidden" name="trigger_type" value="operator">'
        + _REASON_REQUIRED
    ),
    "resume": _REASON_REQUIRED,
    "offboard": _REASON_REQUIRED + _APPROVAL_FIELDSET,
    "purge": _REASON_OPTIONAL + _APPROVAL_FIELDSET,
}
_TENANTS_EMPTY_ROW = (
    '<tr class="tenants-empty"><td colspan="6">'
    "No tenants are visible to this principal.</td></tr>"
)
_PLANE = Template(
    '<section class="plane plane-$status">'
    "<h2>$plane</h2>"
    '<span class="badge status-$status">$status</span>'
    '<ul class="signals">$signals</ul>'
    "</section>"
)
_SIGNAL = Template(
    '<li class="signal">'
    '<span class="signal-name">$name</span> '
    '<span class="badge status-$status">$status</span>'
    "$detail"
    "</li>"
)
_SIGNAL_DETAIL = Template(
    '<span class="signal-detail">$detail</span>'
)


def _esc(value: object) -> str:
    """Escape one dynamic value for HTML text or attribute context."""
    return html.escape(str(value), quote=True)


def _document_json(document: Mapping[str, Any]) -> str:
    """Deterministic pretty-printed JSON for the config editor."""
    return json.dumps(document, indent=2, sort_keys=True)


def _safe_href(value: str) -> str | None:
    """Constrain a resolved endpoint value to an https href.

    Defense in depth over the deployment-provided endpoints mapping:
    a value carrying any explicit scheme other than https (http,
    javascript, data, ...) renders linkless, and a bare host gets the
    https scheme prefixed - the admin-access profile constrains every
    wrapped UI to TLS, so https is the only legitimate scheme.
    urlsplit lowercases the scheme, so the check is case-insensitive.
    """
    scheme = urllib.parse.urlsplit(value).scheme
    if scheme:
        return value if scheme == "https" else None
    return "https://" + value


def _tenant_summary(payload: object) -> TenantSummary:
    """Normalize a tenants-context item to a TenantSummary.

    The API adapter passes the control plane's raw dicts
    (list_tenants(...)["tenants"]); typed TenantSummary values are
    accepted too so callers can render pre-parsed records.
    """
    if isinstance(payload, TenantSummary):
        return payload
    if isinstance(payload, Mapping):
        return TenantSummary.from_response(payload)
    raise TypeError(
        "tenants context items must be mappings or TenantSummary, "
        f"got {type(payload).__name__}"
    )


@dataclass(frozen=True)
class PortalFrontendRenderer:
    """string.Template frontend over the injected endpoints mapping.

    `endpoints` mirrors the deployed admin-access profile `endpoints`
    object (plus, optionally, the catalog id of a null-profile_key
    entry such as the existing Argo CD install). It is
    deployment-provided at construction; this module never names a
    host.
    """

    endpoints: Mapping[str, str] = field(default_factory=dict)

    def render_view(
        self, view: str, context: Mapping[str, Any]
    ) -> RenderedPage:
        principal = context.get("principal")
        if view == "navigation":
            content = self._navigation(context)
        elif view == "config":
            content = self._config(context, principal)
        elif view == "tenants":
            content = self._tenants(context, principal)
        elif view == "health":
            content = self._health(context)
        else:
            return RenderedPage(
                status_code=404,
                html=self._page(
                    title="Unknown view",
                    identity=self._identity(principal),
                    content=(
                        "<p>The requested view is not part of the "
                        "portal contract.</p>"
                    ),
                ),
            )
        return RenderedPage(
            status_code=200,
            html=self._page(
                title=VIEW_TITLES[view],
                identity=self._identity(principal),
                content=content,
            ),
        )

    def _page(
        self, *, title: str, identity: str, content: str
    ) -> str:
        return _LAYOUT.substitute(
            title=_esc(title),
            css=_CSS,
            identity=identity,
            content=content,
        )

    @staticmethod
    def _identity(principal: object) -> str:
        if not isinstance(principal, Principal):
            return "Not authenticated"
        roles = ", ".join(role.value for role in principal.roles)
        scope = (
            "platform scope"
            if principal.is_platform_scoped
            else f"tenant scope: {principal.tenant_scope}"
        )
        return (
            f"Signed in as <strong>{_esc(principal.subject)}</strong>"
            f" ({_esc(roles)}) - {_esc(scope)}"
        )

    def _navigation(self, context: Mapping[str, Any]) -> str:
        items: list[str] = []
        for entry in context.get("entries", ()):
            if not isinstance(entry, CatalogEntry):
                raise TypeError(
                    "navigation context entries must be CatalogEntry "
                    f"instances, got {type(entry).__name__}"
                )
            resolved = resolve_endpoint(entry, self.endpoints)
            href = (
                _safe_href(resolved) if resolved is not None else None
            )
            if href is not None:
                link = _NAV_LINK.substitute(
                    href=_esc(href),
                    display_name=_esc(entry.display_name),
                )
            else:
                link = _NAV_UNRESOLVED
            items.append(
                _NAV_ENTRY.substitute(
                    entry_id=_esc(entry.id),
                    display_name=_esc(entry.display_name),
                    system=_esc(entry.system),
                    link=link,
                )
            )
        return _NAVIGATION.substitute(entries="\n".join(items))

    @staticmethod
    def _config(
        context: Mapping[str, Any], principal: object
    ) -> str:
        document = _esc(
            _document_json(context.get("document", {}))
        )
        can_edit = isinstance(
            principal, Principal
        ) and principal.has_role(PortalRole.ADMIN)
        if can_edit:
            editor = _CONFIG_FORM.substitute(document=document)
        else:
            # Backend authorization already gates the view at
            # portal-admin; hiding the actions here is
            # defense-in-depth for readonly principals.
            editor = _CONFIG_READONLY.substitute(document=document)
        result = ""
        plan = context.get(PLAN_RESULT_KEY)
        if isinstance(plan, ConfigPlanResult):
            if plan.valid:
                result = _PLAN_VALID.substitute(
                    changed_paths="".join(
                        f"<li>{_esc(path)}</li>"
                        for path in plan.changed_paths
                    )
                )
            else:
                result = _PLAN_REJECTED.substitute(
                    errors="".join(
                        f"<li>{_esc(error)}</li>"
                        for error in plan.errors
                    )
                )
        commit = context.get(COMMIT_RESULT_KEY)
        if isinstance(commit, CommitResult):
            result += _COMMIT_RESULT.substitute(
                commit_reference=_esc(commit.commit_reference),
                commit_message=_esc(commit.commit_message),
                written_paths="".join(
                    f"<li>{_esc(path)}</li>"
                    for path in commit.written_paths
                ),
            )
        return _CONFIG.substitute(result=result, editor=editor)

    @staticmethod
    def _tenants(
        context: Mapping[str, Any], principal: object
    ) -> str:
        can_transition = isinstance(
            principal, Principal
        ) and principal.has_role(PortalRole.ADMIN)
        rows: list[str] = []
        for index, payload in enumerate(
            context.get("tenants", ())
        ):
            tenant = _tenant_summary(payload)
            if can_transition:
                # The tenant id becomes a URL path segment before it
                # becomes an attribute value: percent-encode first,
                # then HTML-escape.
                tenant_path = _esc(
                    urllib.parse.quote(tenant.tenant_id, safe="")
                )
                actions = "".join(
                    _TENANT_ACTION.substitute(
                        tenant_path=tenant_path,
                        action=action,
                        fields=LIFECYCLE_FORM_FIELDS[action],
                        label=_esc(action),
                    )
                    for action in LIFECYCLE_ACTIONS
                )
            else:
                actions = (
                    '<span class="unresolved">read-only</span>'
                )
            rows.append(
                _TENANT_ROW.substitute(
                    row_id=_esc(str(index)),
                    tenant_id=_esc(tenant.tenant_id),
                    display_name=_esc(tenant.display_name),
                    lifecycle_state=_esc(tenant.lifecycle_state),
                    tier=_esc(tenant.tier),
                    isolation_class=_esc(tenant.isolation_class),
                    actions=actions,
                )
            )
        if not rows:
            rows.append(_TENANTS_EMPTY_ROW)
        return _TENANTS.substitute(rows="\n".join(rows))

    @staticmethod
    def _health(context: Mapping[str, Any]) -> str:
        summary = context.get("summary")
        if not isinstance(summary, HealthSummary):
            raise TypeError(
                "health context summary must be a HealthSummary, "
                f"got {type(summary).__name__}"
            )
        planes: list[str] = []
        for plane in summary.planes:
            signals = "".join(
                _SIGNAL.substitute(
                    name=_esc(signal.name),
                    status=_esc(signal.status.value),
                    detail=(
                        _SIGNAL_DETAIL.substitute(
                            detail=_esc(signal.detail)
                        )
                        if signal.detail is not None
                        else ""
                    ),
                )
                for signal in plane.signals
            )
            planes.append(
                _PLANE.substitute(
                    plane=_esc(plane.plane),
                    status=_esc(plane.status.value),
                    signals=signals,
                )
            )
        return _HEALTH.substitute(
            overall=_esc(summary.overall.value),
            planes="\n".join(planes),
        )


__all__ = [
    "LIFECYCLE_ACTIONS",
    "LIFECYCLE_FORM_FIELDS",
    "PLAN_RESULT_KEY",
    "COMMIT_RESULT_KEY",
    "VIEW_TITLES",
    "PortalFrontendRenderer",
]
