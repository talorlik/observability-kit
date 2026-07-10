"""Offline tests for the management portal backend core (Batch 21
Task 2).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 21 validator - never under pytest. Every render
happens in a temp copy of tests/configrender/fixtures/repo/; the
repository's own gitops/ tree is never touched, and the real
contracts/ directory is used read-only.

Covers the Task 2 completion check:

- UI catalog aggregation from the real single-pane access contract
  (all four catalog ids, endpoint references only, never URLs);
- unified config read/edit through the Batch 19 renderer as a
  library: plan (dry-run, nothing written) + commit (rendered files
  plus a prepared commit reference) round trip, idempotent re-plan;
- an invalid document is rejected with errors and writes nothing;
- tenant management is pure delegation to the Batch 20 control plane
  API with the caller's scope forwarded on every call (TR-16
  deny-by-default enforced locally as well);
- TR-12 health summary worst-of rollup;
- DenyAllSecurityPolicy denies by default and the FastAPI adapter
  module imports without FastAPI installed.
"""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import urllib.error
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
CONTRACTS = REPO_ROOT / "contracts"
SINGLE_PANE_CONTRACT = (
    CONTRACTS / "management" / "SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
)
SAMPLE_DOCUMENT = (
    CONTRACTS / "management" / "samples" / "VALID_UNIFIED_CONFIG.json"
)
FIXTURE_REPO = (
    REPO_ROOT / "tests" / "configrender" / "fixtures" / "repo"
)
HEALTH_FIXTURE = TESTS_DIR / "fixtures" / "health_snapshot.json"

sys.path.insert(0, str(REPO_ROOT / "services" / "portal"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from portalsvc.catalog import (  # noqa: E402
    ADMIN_PLANE_GROUP,
    READONLY_PLANE_GROUP,
    load_ui_catalog,
    resolve_endpoint,
)
from portalsvc.configflow import ConfigFlow  # noqa: E402
from portalsvc.health import summarize_health  # noqa: E402
from portalsvc.models import (  # noqa: E402
    ConfigEditRejected,
    ControlPlaneDelegationError,
    DenyAllSecurityPolicy,
    Forbidden,
    HealthStatus,
    NotAuthenticated,
    PlaceholderFrontendRenderer,
    PortalRole,
    Principal,
    TenantScopeDenied,
)
from portalsvc.tenants import (  # noqa: E402
    HttpControlPlaneClient,
    PortalTenantService,
)

# Synthetic placeholder only (RFC 6761 example domain); no socket is
# ever opened - the fake opener below intercepts every request.
FAKE_BASE_URL = "http://control-plane.example/api/tenancy/v1"

DOCUMENT_RELPATH = Path("config/unified-config.json")

EXPECTED_CATALOG_IDS = (
    "opensearch-dashboards-ui",
    "grafana-ui",
    "neo4j-browser-ui",
    "argocd-ui",
)

PLATFORM_ADMIN = Principal(
    subject="op@example.com",
    groups=("platform-admins",),
    roles=(PortalRole.ADMIN,),
    tenant_scope=None,
)
PLATFORM_READER = Principal(
    subject="viewer@example.com",
    groups=("platform-viewers",),
    roles=(PortalRole.READONLY,),
    tenant_scope=None,
)
TENANT_ADMIN = Principal(
    subject="acme-op@example.com",
    groups=("acme-admins",),
    roles=(PortalRole.ADMIN,),
    tenant_scope="acme",
)


def _tree_digests(root: Path) -> dict[str, str]:
    return {
        entry.relative_to(root).as_posix(): hashlib.sha256(
            entry.read_bytes()
        ).hexdigest()
        for entry in sorted(root.rglob("*"))
        if entry.is_file()
    }


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


class _HTTPErrorOpener:
    """Fake opener that answers with a control plane denial."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self._status = status
        self._raw = json.dumps(payload).encode("utf-8")

    def __call__(self, request: Any, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(
            request.full_url,
            self._status,
            "denied",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(self._raw),
        )


def test_catalog_extraction_against_real_contract() -> None:
    entries = load_ui_catalog(SINGLE_PANE_CONTRACT)
    assert tuple(entry.id for entry in entries) == (
        EXPECTED_CATALOG_IDS
    )
    by_id = {entry.id: entry for entry in entries}
    assert (
        by_id["opensearch-dashboards-ui"].endpoint_profile_key
        == "opensearch_dashboards"
    )
    assert by_id["grafana-ui"].endpoint_profile_key == "grafana"
    assert (
        by_id["neo4j-browser-ui"].endpoint_profile_key
        == "neo4j_browser"
    )
    # Documented exception: Argo CD is a bring-your-own prerequisite
    # with profile_key null.
    assert by_id["argocd-ui"].endpoint_profile_key is None
    assert (
        by_id["argocd-ui"].endpoint_source
        == "existing-argocd-install"
    )
    for entry in entries:
        assert entry.system
        assert entry.display_name
        groups = {
            mapping.plane_group
            for mapping in entry.sso_role_mappings
        }
        assert READONLY_PLANE_GROUP in groups
        assert ADMIN_PLANE_GROUP in groups
        for mapping in entry.sso_role_mappings:
            assert mapping.native_role.strip()
        # Endpoint values stay profile-key references; no URL, host,
        # or IP is ever extracted or stored
        # (fail_if_hardcoded_endpoint).
        stored = [
            entry.id,
            entry.system,
            entry.display_name,
            entry.endpoint_source,
            entry.endpoint_profile_key or "",
        ]
        for value in stored:
            assert "http://" not in value
            assert "https://" not in value
            assert "://" not in value


def test_catalog_endpoint_resolution_is_a_lookup() -> None:
    entries = load_ui_catalog(SINGLE_PANE_CONTRACT)
    by_id = {entry.id: entry for entry in entries}
    # Deployment-provided mapping, keyed by profile endpoints keys
    # (plus the catalog id for the null-profile_key exception).
    endpoints = {
        "grafana": "grafana.observability.example",
        "opensearch_dashboards": "dashboards.observability.example",
        "argocd-ui": "argocd.delivery.example",
    }
    assert (
        resolve_endpoint(by_id["grafana-ui"], endpoints)
        == "grafana.observability.example"
    )
    assert (
        resolve_endpoint(by_id["argocd-ui"], endpoints)
        == "argocd.delivery.example"
    )
    # No deployment value -> unresolved, never a fabricated host.
    assert (
        resolve_endpoint(by_id["neo4j-browser-ui"], endpoints)
        is None
    )
    # The lookup stores nothing on the entry.
    assert not hasattr(by_id["grafana-ui"], "url")


class _ConfigEnv:
    def __init__(self) -> None:
        self._workdir = tempfile.mkdtemp(prefix="portal-config-")
        self.repo = Path(self._workdir) / "repo"
        shutil.copytree(FIXTURE_REPO, self.repo)
        self.document = self.repo / DOCUMENT_RELPATH
        self.document.parent.mkdir(parents=True, exist_ok=True)
        self.document.write_bytes(SAMPLE_DOCUMENT.read_bytes())
        self.flow = ConfigFlow(
            repo_root=self.repo,
            document_path=DOCUMENT_RELPATH,
            contracts_dir=CONTRACTS,
        )

    def cleanup(self) -> None:
        shutil.rmtree(self._workdir, ignore_errors=True)


def test_configflow_plan_and_commit_round_trip() -> None:
    env = _ConfigEnv()
    try:
        submitted = SAMPLE_DOCUMENT.read_bytes()
        document = env.flow.get_document()
        assert document["schema_version"] == "v1"

        before = _tree_digests(env.repo)
        plan_result = env.flow.plan_edit(submitted)
        assert plan_result.valid
        assert plan_result.errors == ()
        assert plan_result.changed_paths
        # Dry-run: nothing is written.
        assert _tree_digests(env.repo) == before

        commit = env.flow.commit_edit(submitted)
        assert commit.commit_reference.startswith(
            "prepared:sha256:"
        )
        assert "Unified-Config-Digest" in commit.commit_message or (
            "sha256" in commit.commit_message
        )
        assert str(DOCUMENT_RELPATH) in commit.written_paths
        for relpath in plan_result.changed_paths:
            assert (env.repo / relpath).is_file()
            assert relpath in commit.written_paths
        # A rendered target (not just the manifest) landed.
        assert (
            env.repo
            / "gitops/platform/search/opensearch/ilm/"
            "logs-ilm-policy.json"
        ).is_file()

        # Idempotent: re-planning the committed document changes
        # nothing.
        replan = env.flow.plan_edit(submitted)
        assert replan.valid
        assert replan.changed_paths == ()
    finally:
        env.cleanup()


def test_invalid_document_rejected_and_writes_nothing() -> None:
    env = _ConfigEnv()
    try:
        valid = json.loads(SAMPLE_DOCUMENT.read_text())
        del valid["schema_version"]
        invalid = json.dumps(valid).encode("utf-8")

        before = _tree_digests(env.repo)
        plan_result = env.flow.plan_edit(invalid)
        assert not plan_result.valid
        assert plan_result.errors
        assert plan_result.changed_paths == ()
        assert _tree_digests(env.repo) == before

        try:
            env.flow.commit_edit(invalid)
        except ConfigEditRejected as error:
            assert error.http_status == 422
            assert error.details is not None
            assert error.details["errors"]
        else:
            raise AssertionError(
                "expected commit_edit to reject the invalid document"
            )
        assert _tree_digests(env.repo) == before

        # Malformed JSON is rejected the same way, nothing written.
        garbage = env.flow.plan_edit(b"{not json")
        assert not garbage.valid
        assert garbage.errors
        assert _tree_digests(env.repo) == before
    finally:
        env.cleanup()


def test_tenants_delegation_forwards_caller_scope() -> None:
    opener = _FakeOpener(payload={"tenants": []})
    client = HttpControlPlaneClient(
        FAKE_BASE_URL, opener=opener
    )
    service = PortalTenantService(client)

    result = service.list_tenants(PLATFORM_READER)
    assert result == {"tenants": []}
    request = opener.requests[-1]
    assert request.full_url == f"{FAKE_BASE_URL}/tenants"
    assert request.get_method() == "GET"
    # Caller scope headers forwarded on EVERY call.
    assert (
        request.get_header("X-portal-user")
        == "viewer@example.com"
    )
    assert (
        request.get_header("X-portal-groups")
        == "platform-viewers"
    )
    assert request.get_header("X-portal-tenant") is None

    opener.payload = {"tenant_id": "acme"}
    transition = service.transition(
        "suspend",
        "acme",
        {"actor": "acme-op@example.com", "reason": "maintenance"},
        TENANT_ADMIN,
    )
    assert transition == {"tenant_id": "acme"}
    request = opener.requests[-1]
    assert request.full_url == (
        f"{FAKE_BASE_URL}/tenants/acme/lifecycle/suspend"
    )
    assert request.get_method() == "POST"
    assert (
        request.get_header("X-portal-tenant") == "acme"
    )
    assert json.loads(request.data.decode("utf-8")) == {
        "actor": "acme-op@example.com",
        "reason": "maintenance",
    }


def test_tenant_scope_is_deny_by_default() -> None:
    opener = _FakeOpener(payload={"tenant_id": "acme"})
    service = PortalTenantService(
        HttpControlPlaneClient(FAKE_BASE_URL, opener=opener)
    )

    # A tenant-scoped principal lists exactly its own tenant (via a
    # scope-forwarded get, never an unscoped list).
    listed = service.list_tenants(TENANT_ADMIN)
    assert listed == {"tenants": [{"tenant_id": "acme"}]}
    request = opener.requests[-1]
    assert request.full_url == f"{FAKE_BASE_URL}/tenants/acme"
    assert request.get_header("X-portal-tenant") == "acme"

    # Cross-tenant reads and transitions are denied locally, before
    # any delegation.
    seen = len(opener.requests)
    for attempt in (
        lambda: service.get_tenant("globex", TENANT_ADMIN),
        lambda: service.transition(
            "suspend", "globex", {}, TENANT_ADMIN
        ),
    ):
        try:
            attempt()
        except TenantScopeDenied:
            pass
        else:
            raise AssertionError(
                "expected cross-tenant access to be denied"
            )
    assert len(opener.requests) == seen

    # Transitions are a portal-admin grant; readonly is denied.
    try:
        service.transition("suspend", "acme", {}, PLATFORM_READER)
    except Forbidden:
        pass
    else:
        raise AssertionError(
            "expected a readonly principal to be denied transitions"
        )
    assert len(opener.requests) == seen


def test_control_plane_errors_relay_upstream_payload() -> None:
    upstream = {
        "error_code": "approval-required",
        "message": "destructive transition requires approval",
    }
    service = PortalTenantService(
        HttpControlPlaneClient(
            FAKE_BASE_URL,
            opener=_HTTPErrorOpener(403, upstream),
        )
    )
    try:
        service.transition(
            "purge", "acme", {"actor": "op@example.com"},
            PLATFORM_ADMIN,
        )
    except ControlPlaneDelegationError as error:
        assert error.http_status == 403
        assert error.to_response() == upstream
    else:
        raise AssertionError(
            "expected the upstream denial to propagate"
        )


def test_health_rollup_worst_of() -> None:
    fixture = json.loads(HEALTH_FIXTURE.read_text())
    summary = summarize_health(fixture["snapshot"])
    by_plane = {plane.plane: plane for plane in summary.planes}
    assert set(by_plane) == {
        "collector",
        "backend",
        "install_discovery",
    }
    # One degraded collector signal degrades the plane and the
    # overall status.
    assert by_plane["collector"].status is HealthStatus.DEGRADED
    assert by_plane["backend"].status is HealthStatus.OK
    # A missing reading is unknown, and unknown dominates ok.
    assert (
        by_plane["install_discovery"].status
        is HealthStatus.UNKNOWN
    )
    assert summary.overall is HealthStatus.DEGRADED

    signals = {
        signal.name: signal
        for signal in by_plane["install_discovery"].signals
    }
    assert (
        signals["discovery_completeness"].status
        is HealthStatus.UNKNOWN
    )

    all_ok = {
        plane: {name: "ok" for name in names}
        for plane, names in (
            ("collector", ("queue_depth", "dropped_telemetry",
                           "retry_failure")),
            ("backend", ("ingest_errors_lag", "storage_pressure")),
            ("install_discovery", ("preflight_failure_rate",
                                   "discovery_completeness",
                                   "generation_apply_success")),
        )
    }
    assert summarize_health(all_ok).overall is HealthStatus.OK

    empty = summarize_health({})
    assert empty.overall is HealthStatus.UNKNOWN
    assert all(
        plane.status is HealthStatus.UNKNOWN
        for plane in empty.planes
    )

    response = summary.to_response()
    assert response["overall"] == "degraded"
    assert len(response["planes"]) == 3


def test_deny_all_security_policy_denies_by_default() -> None:
    policy = DenyAllSecurityPolicy()
    try:
        policy.principal_for(
            {"x-portal-user": "op@example.com"}
        )
    except NotAuthenticated as error:
        assert error.http_status == 401
    else:
        raise AssertionError(
            "expected DenyAllSecurityPolicy to deny"
        )


def test_placeholder_frontend_is_501() -> None:
    page = PlaceholderFrontendRenderer().render_view(
        "navigation", {}
    )
    assert page.status_code == 501
    assert "not implemented" in page.html


def test_api_module_imports_without_fastapi() -> None:
    import portalsvc.api as api

    if api._FASTAPI_AVAILABLE:
        # FastAPI happens to be installed in this interpreter; the
        # import-guard branch is exercised in offline CI, which never
        # installs a web framework.
        return
    try:
        api.build_app(
            catalog=(),
            config_flow=None,  # type: ignore[arg-type]
            tenant_service=None,  # type: ignore[arg-type]
            health_provider=lambda: None,  # type: ignore[arg-type,return-value]
            security=DenyAllSecurityPolicy(),
            frontend=PlaceholderFrontendRenderer(),
        )
    except RuntimeError as error:
        assert "[api]" in str(error)
    else:
        raise AssertionError(
            "expected build_app to fail without FastAPI"
        )


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
