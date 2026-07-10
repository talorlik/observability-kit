"""Thin FastAPI adapter for the management portal (ADR-0005).

Binds the contract-fixed routes of
contracts/management/PORTAL_CONTRACT_V1.yaml api_surface one-to-one
to core calls and performs no business logic: every authenticated
route resolves the Principal through the injected SecurityPolicy
first, role checks follow the contract's per-view minimum_role
mapping (navigation/tenants/health: portal-readonly; config:
portal-admin, platform scope), HTML routes delegate to the injected
FrontendRenderer, and /healthz is the only unauthenticated route.

Import guard: this module is importable without FastAPI installed
(offline CI never installs a web framework); build_app then raises a
clear error pointing at the [api] extra.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Callable, Mapping

from portalsvc.configflow import ConfigFlow
from portalsvc.models import (
    CatalogEntry,
    FrontendRenderer,
    HealthSummary,
    PortalError,
    PortalRole,
    Principal,
    SecurityPolicy,
    VIEW_MINIMUM_ROLE,
    require_platform_scope,
    require_role,
)
from portalsvc.tenants import PortalTenantService

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import (
        HTMLResponse,
        JSONResponse,
        RedirectResponse,
    )

    _FASTAPI_AVAILABLE = True
except ModuleNotFoundError:
    _FASTAPI_AVAILABLE = False

# html_routes, verbatim from the portal contract api_surface.
HTML_ROUTES: tuple[tuple[str, str], ...] = (
    ("/", "navigation"),
    ("/config", "config"),
    ("/tenants", "tenants"),
    ("/health", "health"),
)

_FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def _is_form_request(content_type: str | None) -> bool:
    return bool(
        content_type
        and content_type.split(";", 1)[0].strip() == _FORM_CONTENT_TYPE
    )


def _form_fields(raw: bytes) -> dict[str, str]:
    parsed = urllib.parse.parse_qs(
        raw.decode("utf-8"), keep_blank_values=True
    )
    return {key: values[-1] for key, values in parsed.items()}


def _form_body(fields: Mapping[str, str]) -> dict[str, Any]:
    """Build a delegation body from no-JS form fields.

    Empty values are dropped (an untouched optional input means the
    field is absent, so e.g. an empty approval fieldset yields the
    contract's approval-required denial rather than a malformed
    block), and dotted names nest (`approval.approver` becomes
    `body["approval"]["approver"]`) so flat HTML forms can express
    the API's nested objects.
    """
    body: dict[str, Any] = {}
    for name, value in fields.items():
        if value == "":
            continue
        parts = name.split(".")
        target = body
        for part in parts[:-1]:
            existing = target.get(part)
            if not isinstance(existing, dict):
                existing = {}
                target[part] = existing
            target = existing
        target[parts[-1]] = value
    # An approval block whose only member is the form's hidden
    # decision field means the operator left the approval inputs
    # blank: drop the block so the control plane answers with the
    # contract's approval-required denial, not approval-invalid.
    approval = body.get("approval")
    if isinstance(approval, dict) and set(approval) <= {"decision"}:
        del body["approval"]
    return body


def build_app(
    *,
    catalog: tuple[CatalogEntry, ...],
    config_flow: ConfigFlow,
    tenant_service: PortalTenantService,
    health_provider: Callable[[], HealthSummary],
    security: SecurityPolicy,
    frontend: FrontendRenderer,
) -> "FastAPI":
    """Build the FastAPI application over the injected core.

    security and frontend are the Task 4 / Task 3 extension points;
    passing the models module defaults (DenyAllSecurityPolicy,
    PlaceholderFrontendRenderer) yields a deny-by-default portal
    whose HTML views answer 501.
    """
    if not _FASTAPI_AVAILABLE:
        raise RuntimeError(
            "FastAPI is not installed; install services/portal with "
            "the [api] extra (pip install 'obskit-portalsvc[api]') "
            "to run the API adapter. The portalsvc core works "
            "without it."
        )
    # The contract's api_surface is exhaustive and /healthz is the only
    # unauthenticated route, so the framework's schema and docs
    # endpoints (all pre-auth) must not exist.
    app = FastAPI(
        title="Management Portal API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    @app.exception_handler(PortalError)
    async def _portal_error(
        _request: Request, error: PortalError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=error.http_status,
            content=error.to_response(),
        )

    def _authenticate(
        request: Request, view: str
    ) -> Principal:
        principal = security.principal_for(request.headers)
        require_role(principal, VIEW_MINIMUM_ROLE[view])
        if view == "config":
            # The config view is platform-wide by nature (portal
            # contract tenant_scoping.model).
            require_platform_scope(principal)
        return principal

    def _view_context(
        view: str, principal: Principal
    ) -> Mapping[str, Any]:
        # The same core data the JSON routes serve, so the frontend
        # renders as a pure function of typed core state.
        context: dict[str, Any] = {"principal": principal}
        if view == "navigation":
            context["entries"] = catalog
        elif view == "config":
            context["document"] = config_flow.get_document()
        elif view == "tenants":
            context["tenants"] = tenant_service.list_tenants(
                principal
            )["tenants"]
        elif view == "health":
            context["summary"] = health_provider()
        return context

    def _register_html_route(path: str, view: str) -> None:
        @app.get(path, name=f"view_{view}", response_class=HTMLResponse)
        async def _html(request: Request) -> HTMLResponse:
            principal = _authenticate(request, view)
            page = frontend.render_view(
                view, _view_context(view, principal)
            )
            return HTMLResponse(
                content=page.html, status_code=page.status_code
            )

    for html_path, html_view in HTML_ROUTES:
        _register_html_route(html_path, html_view)

    @app.get("/healthz")
    async def liveness() -> dict[str, str]:
        # Unauthenticated by contract: process liveness only, no
        # platform data.
        return {"status": "ok"}

    @app.get("/api/v1/catalog")
    async def list_catalog_entries(
        request: Request,
    ) -> dict[str, Any]:
        _authenticate(request, "navigation")
        return {
            "entries": [entry.to_response() for entry in catalog]
        }

    @app.get("/api/v1/config")
    async def get_unified_config(
        request: Request,
    ) -> dict[str, Any]:
        _authenticate(request, "config")
        return config_flow.get_document()

    def _submitted_document(request: Request, raw: bytes) -> bytes:
        # Browser form posts (the frontend's no-JS editor) carry the
        # document in the urlencoded `document` field; API callers
        # send the document as the raw JSON body. Same contract
        # route, same semantics.
        if _is_form_request(request.headers.get("content-type")):
            fields = _form_fields(raw)
            if "document" not in fields:
                raise PortalError(
                    "form submission is missing the document field"
                )
            return fields["document"].encode("utf-8")
        return raw

    def _config_page_response(
        principal: Principal,
        result_key: str,
        result: Any,
        submitted: bytes | None = None,
    ) -> HTMLResponse:
        context = dict(_view_context("config", principal))
        context[result_key] = result
        if submitted is not None:
            # Re-render the operator's edit (not the stored document)
            # so a rejected submission can be corrected and resent;
            # unparseable JSON falls back to the stored document and
            # the error list carries the parse failure.
            try:
                parsed = json.loads(submitted)
            except (UnicodeDecodeError, json.JSONDecodeError):
                parsed = None
            if isinstance(parsed, dict):
                context["document"] = parsed
        page = frontend.render_view("config", context)
        return HTMLResponse(
            content=page.html, status_code=page.status_code
        )

    @app.post("/api/v1/config/plan")
    async def plan_config_edit(request: Request) -> Any:
        principal = _authenticate(request, "config")
        raw = await request.body()
        result = config_flow.plan_edit(
            _submitted_document(request, raw)
        )
        if _is_form_request(request.headers.get("content-type")):
            return _config_page_response(
                principal,
                "plan_result",
                result,
                submitted=_submitted_document(request, raw),
            )
        return result.to_response()

    @app.post("/api/v1/config/commit")
    async def commit_config_edit(request: Request) -> Any:
        principal = _authenticate(request, "config")
        raw = await request.body()
        submitted = _submitted_document(request, raw)
        plan = config_flow.plan_edit(submitted)
        if not plan.valid:
            # Fail closed before any write; surface the same shape a
            # plan would.
            if _is_form_request(request.headers.get("content-type")):
                return _config_page_response(
                    principal, "plan_result", plan, submitted=submitted
                )
            return plan.to_response()
        result = config_flow.commit_edit(submitted)
        if _is_form_request(request.headers.get("content-type")):
            return _config_page_response(
                principal, "commit_result", result
            )
        return result.to_response()

    @app.get("/api/v1/tenants")
    async def portal_list_tenants(
        request: Request, lifecycle_state: str | None = None
    ) -> dict[str, Any]:
        principal = _authenticate(request, "tenants")
        return tenant_service.list_tenants(
            principal, lifecycle_state
        )

    @app.get("/api/v1/tenants/{tenant_id}")
    async def portal_get_tenant(
        tenant_id: str, request: Request
    ) -> dict[str, Any]:
        principal = _authenticate(request, "tenants")
        return tenant_service.get_tenant(tenant_id, principal)

    def _register_transition(name: str) -> None:
        @app.post(
            f"/api/v1/tenants/{{tenant_id}}/lifecycle/{name}",
            name=f"portal_{name}_tenant",
        )
        async def _transition(
            tenant_id: str, request: Request
        ) -> dict[str, Any]:
            # Lifecycle transition requests are a portal-admin grant
            # (contract role_mapping); the tenants view itself loads
            # at portal-readonly.
            principal = _authenticate(request, "tenants")
            require_role(principal, PortalRole.ADMIN)
            raw = await request.body()
            is_form = _is_form_request(
                request.headers.get("content-type")
            )
            if is_form:
                # The tenants view's no-JS lifecycle forms post
                # urlencoded fields; empty optionals drop out and
                # dotted names nest (approval.*). The actor is ALWAYS
                # the authenticated subject - a browser could inject
                # an actor field into the form data, so audit
                # attribution never trusts it.
                body: dict[str, Any] = _form_body(_form_fields(raw))
                body["actor"] = principal.subject
            else:
                try:
                    body = json.loads(raw) if raw else {}
                except json.JSONDecodeError as error:
                    raise PortalError(
                        "request body is not valid JSON"
                    ) from error
                if not isinstance(body, dict):
                    raise PortalError(
                        "request body must be a JSON object"
                    )
            result = tenant_service.transition(
                name, tenant_id, body, principal
            )
            if is_form:
                # Post/redirect/get: the no-JS form flow lands back
                # on the tenants view showing the new state.
                return RedirectResponse("/tenants", status_code=303)
            return result

    for transition_name in (
        "provision",
        "suspend",
        "resume",
        "offboard",
        "purge",
    ):
        _register_transition(transition_name)

    @app.get("/api/v1/health")
    async def get_health_summary(
        request: Request,
    ) -> dict[str, Any]:
        _authenticate(request, "health")
        return health_provider().to_response()

    return app
