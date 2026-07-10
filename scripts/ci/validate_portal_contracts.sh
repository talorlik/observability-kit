#!/usr/bin/env bash
#
# Batch 21 validator: unified management portal (portalsvc).
#
# Repository-only and offline (TB-21 composed with TR-17 and TR-22:
# CI validation is fixture-driven; nothing here touches a live
# cluster, serves HTTP, or installs anything beyond the shared CI
# venv). Referenced by the Batch 21 smoke wrapper
# validate_batch21_smoke.sh; the live portal endpoint probe lives in
# scripts/validate/admin_gui_smoke.sh and is never CI-gated.
#
# Checks, in order:
#
#   1. the offline portal test suites under tests/portal/, run with
#      plain system python3 - the portal core is stdlib-only and must
#      never need the CI venv:
#        - test_backend_core.py   (UI catalog aggregation over the
#          single-pane access contract, the Git-commit-only config
#          edit flow through the TR-20 renderer, control plane
#          delegation, TR-12 health rollup)
#        - test_frontend_views.py (server-rendered views over the
#          same core)
#        - test_auth_scoping.py   (SSO role mapping from the admin
#          access plane groups, TR-16 tenant scoping)
#   2. the portal aggregation dump (system python3): runs
#      portalsvc.catalog.load_ui_catalog against the real single-pane
#      access contract and captures api.py's HTML_ROUTES constant,
#      for the cross-contract checks below;
#   3. wrap-not-fork and GitOps-only guards over the portal source
#      (greps): no PyYAML anywhere under services/portal/, no
#      subprocess and no requests in portalsvc, urllib.request only
#      in tenants.py (control plane delegation - never in
#      configflow.py, TR-17/TR-20), no literal URLs, hostnames, or
#      IPs in the portal contract, portalsvc source, or templates
#      (fail_if_hardcoded_endpoint), and no password or login-form
#      markers (fail_if_bespoke_portal_auth, TR-03);
#   4. structural validation of
#      contracts/management/PORTAL_CONTRACT_V1.yaml (venv PyYAML; a
#      validator-side dependency only): required top-level blocks,
#      exactly the four contracted views (navigation, config,
#      tenants, health) each with data_sources, write_path, and
#      minimum_role, the three api_surface route lists, and the
#      authentication block (admin-access-plane identity source, the
#      three trusted identity headers, the exact two-row role
#      mapping readonly_group->portal-readonly and
#      admin_group->portal-admin, and a tenant_scoping block);
#   5. mechanical cross-contract enforcement of the contract's
#      consistency_policy (venv PyYAML): every json_route
#      delegates_to resolves to an operationId in
#      contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml
#      (fail_if_tenant_lifecycle_logic_in_portal), the portal's
#      aggregated catalog ids match the single-pane ui_catalog 1:1
#      (fail_if_catalog_entry_unreachable), html and json route
#      parity against services/portal/portalsvc/api.py, and the
#      admin-access profile endpoints object carries the ADR-0005
#      additive `portal` key - plus two seeded-invalid checks proving
#      the cross-checks reject drift (a delegates_to pointing at a
#      nonexistent operationId; a catalog id missing from the portal
#      aggregation).
#
# Markers: TB-21, TR-03, TR-17, TR-22.
#
# Invoke from the repository root. Exit 0 on pass, non-zero on failure.

set -euo pipefail

echo "Running the offline portal test suites (system python3)..."
python3 tests/portal/test_backend_core.py
python3 tests/portal/test_frontend_views.py
python3 tests/portal/test_auth_scoping.py
echo "Offline portal test suites passed."

# The aggregation dump feeds the venv cross-checks below. It runs the
# real portal aggregation code (system python3, stdlib-only) via the
# same sys.path bootstrap the offline tests use, so the comparison in
# check 5 is portal-code-vs-contract, not contract-vs-itself.
PORTAL_AGGREGATION_FILE="$(mktemp)"
trap 'rm -f "$PORTAL_AGGREGATION_FILE"' EXIT
export PORTAL_AGGREGATION_FILE

echo "Aggregating the portal UI catalog via portalsvc (system python3)..."
python3 - <<'PY'
"""Dump the portal's aggregated catalog ids and HTML route table."""
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path.cwd()
sys.path.insert(0, str(REPO_ROOT / "services" / "portal"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from portalsvc.api import HTML_ROUTES  # noqa: E402
from portalsvc.catalog import load_ui_catalog  # noqa: E402

SINGLE_PANE_CONTRACT = (
    REPO_ROOT / "contracts" / "management"
    / "SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
)

entries = load_ui_catalog(SINGLE_PANE_CONTRACT)
payload: dict[str, list] = {
    "catalog_ids": [entry.id for entry in entries],
    "html_routes": [[path, view] for path, view in HTML_ROUTES],
}
Path(os.environ["PORTAL_AGGREGATION_FILE"]).write_text(
    json.dumps(payload, indent=2), encoding="utf-8"
)
print(
    f"aggregated {len(payload['catalog_ids'])} catalog ids and "
    f"{len(payload['html_routes'])} HTML routes from portalsvc"
)
PY
echo "Portal aggregation dump complete."

echo "Enforcing wrap-not-fork and GitOps-only source guards (greps)..."

PORTAL_CONTRACT="contracts/management/PORTAL_CONTRACT_V1.yaml"

# The portal core is stdlib-only; PyYAML is a validator-side
# dependency and must never leak into the portal runtime.
if grep -rnE '(^|[[:space:]])(import yaml|from yaml)' services/portal \
    --include='*.py' --exclude-dir=__pycache__; then
  echo "ERROR: PyYAML import found under services/portal/ (portal core is stdlib-only)"
  exit 1
fi
echo "  guard ok: no PyYAML under services/portal/"

# No live config write primitives: propagation is GitOps-only
# (TR-17, TR-20), so the portal source must not shell out or speak
# HTTP outside the contracted control plane delegation.
if grep -rn 'subprocess' services/portal/portalsvc \
    --include='*.py' --exclude-dir=__pycache__; then
  echo "ERROR: subprocess usage found in portalsvc (no live write primitives)"
  exit 1
fi
echo "  guard ok: no subprocess in portalsvc"

if grep -rnE '(^|[[:space:]])(import requests|from requests)' \
    services/portal/portalsvc --include='*.py' --exclude-dir=__pycache__; then
  echo "ERROR: requests import found in portalsvc (no live write primitives)"
  exit 1
fi
echo "  guard ok: no requests in portalsvc"

# urllib.request is the stdlib HTTP client; the only permitted user
# is tenants.py (control plane delegation per the portal contract).
# configflow.py in particular must never carry it: config edits are
# renderer-and-Git only.
if grep -rn 'urllib\.request' services/portal/portalsvc \
    --include='*.py' --exclude-dir=__pycache__ \
    | grep -v '/tenants\.py:'; then
  echo "ERROR: urllib.request outside tenants.py (config edits are GitOps-only; delegation lives in tenants.py)"
  exit 1
fi
echo "  guard ok: urllib.request confined to tenants.py"

# Hosts are environment data owned by the deployed admin-access
# profile (fail_if_hardcoded_endpoint). The bare "https://" scheme
# prefix constant in frontend.py is allowed by construction: the
# pattern requires a host character after the scheme.
if grep -rnE 'https?://[A-Za-z0-9]' "$PORTAL_CONTRACT" services/portal \
    --exclude-dir=__pycache__; then
  echo "ERROR: literal URL found in the portal contract or portal source"
  exit 1
fi
if grep -rnE '(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}' "$PORTAL_CONTRACT" \
    services/portal --exclude-dir=__pycache__; then
  echo "ERROR: literal IP address found in the portal contract or portal source"
  exit 1
fi
echo "  guard ok: no literal URLs, hostnames, or IPs"

# Bespoke-auth guard (TR-03, fail_if_bespoke_portal_auth): identity
# arrives from the admin access plane; the portal ships no login
# form, password field, or basic-auth handling of its own.
if grep -rniE 'password|htpasswd|www-authenticate|login[-_ ]form|basic[-_ ]auth' \
    services/portal/portalsvc --exclude-dir=__pycache__; then
  echo "ERROR: password/login-form/basic-auth marker found in portalsvc (auth flows through the admin access plane)"
  exit 1
fi
echo "  guard ok: no bespoke-auth markers in portalsvc"

# caller_scope wiring guard (TR-16, the Batch 20 gap closed by Batch
# 21 Task 4): every scoped tenantctl HTTP handler must derive
# caller_scope from the trusted headers. Six wiring sites cover
# create/list/get/update/delete plus the transition registrar; a
# dropped kwarg would silently re-open platform scope for HTTP
# callers, so the count is a floor.
scope_wirings="$(grep -c 'caller_scope=caller_scope_from_headers(' \
    services/tenancy/tenantctl/api.py || true)"
if [ "${scope_wirings}" -lt 6 ]; then
  echo "ERROR: expected at least 6 caller_scope_from_headers wiring sites in services/tenancy/tenantctl/api.py, found ${scope_wirings}"
  exit 1
fi
echo "  guard ok: caller_scope bound to trusted headers in tenantctl (${scope_wirings} sites)"

echo "Source guards passed."

# PyYAML is needed for the contract checks below; the portal core
# itself stays stdlib-only, so the venv is a validator-side
# dependency exactly as in the sibling YAML-consuming validators.
# shellcheck source=/dev/null
source scripts/ci/setup_python_env.sh

echo "Validating PORTAL_CONTRACT_V1.yaml structurally..."
python - <<'PY'
"""Structural validation of PORTAL_CONTRACT_V1.yaml."""
import sys
from pathlib import Path
from typing import Any

import yaml

CONTRACT_PATH = Path("contracts/management/PORTAL_CONTRACT_V1.yaml")
REQUIRED_BLOCKS = (
    "contract",
    "contract_version",
    "views",
    "api_surface",
    "authentication",
    "consistency_policy",
)
EXPECTED_VIEW_IDS = ("navigation", "config", "tenants", "health")
REQUIRED_VIEW_KEYS = ("data_sources", "write_path", "minimum_role")
ROUTE_LISTS = ("html_routes", "json_routes", "unauthenticated_routes")
EXPECTED_HEADER_KEYS = ("subject", "groups", "tenant_scope")
EXPECTED_ROLE_MAPPING = {
    "role_mapping.readonly_group": "portal-readonly",
    "role_mapping.admin_group": "portal-admin",
}


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


doc: dict[str, Any] = yaml.safe_load(
    CONTRACT_PATH.read_text(encoding="utf-8")
)

for block in REQUIRED_BLOCKS:
    if block not in doc:
        fail(f"{CONTRACT_PATH}: required top-level block {block!r} missing")
if doc["contract"] != "portal":
    fail(f"{CONTRACT_PATH}: contract must be 'portal', got {doc['contract']!r}")
if doc["contract_version"] != 1:
    fail(
        f"{CONTRACT_PATH}: contract_version must be 1, "
        f"got {doc['contract_version']!r}"
    )

views = doc["views"]
if not isinstance(views, list):
    fail(f"{CONTRACT_PATH}: views must be a list")
view_ids = [view.get("id") for view in views]
if view_ids != list(EXPECTED_VIEW_IDS):
    fail(
        f"{CONTRACT_PATH}: views must be exactly "
        f"{list(EXPECTED_VIEW_IDS)}, got {view_ids}"
    )
for view in views:
    for key in REQUIRED_VIEW_KEYS:
        if key not in view:
            fail(f"{CONTRACT_PATH}: view {view.get('id')!r} lacks {key!r}")
    if not isinstance(view["data_sources"], list) or not view["data_sources"]:
        fail(
            f"{CONTRACT_PATH}: view {view.get('id')!r} data_sources "
            "must be a non-empty list"
        )

api_surface = doc["api_surface"]
for key in ROUTE_LISTS:
    routes = api_surface.get(key)
    if not isinstance(routes, list) or not routes:
        fail(
            f"{CONTRACT_PATH}: api_surface.{key} must be a "
            "non-empty list"
        )

auth = doc["authentication"]
if auth.get("identity_source") != "admin-access-plane":
    fail(
        f"{CONTRACT_PATH}: authentication.identity_source must be "
        f"'admin-access-plane', got {auth.get('identity_source')!r}"
    )
headers = auth.get("trusted_identity_headers")
if not isinstance(headers, dict) or sorted(headers) != sorted(
    EXPECTED_HEADER_KEYS
):
    fail(
        f"{CONTRACT_PATH}: trusted_identity_headers must carry exactly "
        f"{sorted(EXPECTED_HEADER_KEYS)}, got "
        f"{sorted(headers) if isinstance(headers, dict) else headers!r}"
    )
for key, value in headers.items():
    if not isinstance(value, str) or not value:
        fail(
            f"{CONTRACT_PATH}: trusted_identity_headers.{key} must be "
            "a non-empty header name"
        )
role_mapping = auth.get("role_mapping")
if not isinstance(role_mapping, list) or len(role_mapping) != 2:
    fail(
        f"{CONTRACT_PATH}: role_mapping must carry exactly two "
        "entries (readonly and admin)"
    )
mapping = {
    entry.get("plane_group"): entry.get("portal_role")
    for entry in role_mapping
}
if mapping != EXPECTED_ROLE_MAPPING:
    fail(
        f"{CONTRACT_PATH}: role_mapping must be exactly "
        f"{EXPECTED_ROLE_MAPPING}, got {mapping}"
    )
tenant_scoping = auth.get("tenant_scoping")
if not isinstance(tenant_scoping, dict) or not tenant_scoping:
    fail(
        f"{CONTRACT_PATH}: authentication.tenant_scoping block is "
        "missing or empty"
    )

print(
    f"portal contract v{doc['contract_version']}: "
    f"{len(views)} views, "
    f"{len(api_surface['html_routes'])} html + "
    f"{len(api_surface['json_routes'])} json + "
    f"{len(api_surface['unauthenticated_routes'])} unauthenticated "
    "routes, authentication block well-formed"
)
PY
echo "Portal contract structural checks passed."

echo "Cross-checking the portal contract against its consumed surfaces..."
python - <<'PY'
"""Mechanical enforcement of the portal consistency_policy.

Cross-checks by name: delegates_to -> control plane operationIds,
aggregated catalog ids -> single-pane ui_catalog (1:1), api_surface
routes -> the FastAPI adapter source, and the admin-access profile's
`portal` endpoints key. Ends with two seeded-invalid checks proving
the delegation and catalog-parity checks reject bad input.
"""
import copy
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

PORTAL_CONTRACT = Path("contracts/management/PORTAL_CONTRACT_V1.yaml")
SINGLE_PANE = Path(
    "contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
)
CONTROL_PLANE_API = Path(
    "contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml"
)
API_MODULE = Path("services/portal/portalsvc/api.py")
PROFILE_SCHEMA = Path("install/profiles/admin-access/PROFILE.schema.json")
HTTP_METHODS = (
    "get", "put", "post", "delete", "options", "head", "patch", "trace",
)
# Literal source text of the parameterized transition decorator in
# api.py; lifecycle json_routes are registered through it, so their
# concrete paths never appear verbatim in the source.
TRANSITION_TEMPLATE = "/api/v1/tenants/{{tenant_id}}/lifecycle/{name}"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}")
    sys.exit(1)


def delegation_errors(
    json_routes: list[dict[str, Any]], operation_ids: set[str]
) -> list[str]:
    """fail_if_tenant_lifecycle_logic_in_portal, mechanically."""
    errors: list[str] = []
    for route in json_routes:
        target = route.get("delegates_to")
        if route.get("view") == "tenants" and target is None:
            errors.append(
                f"tenant route {route.get('path')} declares no "
                "delegates_to operationId"
            )
        if target is not None and target not in operation_ids:
            errors.append(
                f"route {route.get('path')}: delegates_to {target!r} "
                f"is not an operationId in {CONTROL_PLANE_API}"
            )
    return errors


def catalog_parity_errors(
    contract_ids: list[str], aggregated_ids: list[str]
) -> list[str]:
    """fail_if_catalog_entry_unreachable, mechanically (1:1)."""
    errors: list[str] = []
    missing = [i for i in contract_ids if i not in aggregated_ids]
    extra = [i for i in aggregated_ids if i not in contract_ids]
    if missing:
        errors.append(
            f"ui_catalog ids unreachable from the portal navigation "
            f"view: {missing}"
        )
    if extra:
        errors.append(
            f"portal aggregates ids absent from the single-pane "
            f"ui_catalog: {extra}"
        )
    return errors


portal = yaml.safe_load(PORTAL_CONTRACT.read_text(encoding="utf-8"))
single_pane = yaml.safe_load(SINGLE_PANE.read_text(encoding="utf-8"))
control_plane = yaml.safe_load(
    CONTROL_PLANE_API.read_text(encoding="utf-8")
)
aggregation = json.loads(
    Path(os.environ["PORTAL_AGGREGATION_FILE"]).read_text(
        encoding="utf-8"
    )
)
api_source = API_MODULE.read_text(encoding="utf-8")

operation_ids: set[str] = {
    operation["operationId"]
    for path_item in control_plane["paths"].values()
    for method, operation in path_item.items()
    if method in HTTP_METHODS
    and isinstance(operation, dict)
    and operation.get("operationId")
}

json_routes = portal["api_surface"]["json_routes"]
errors = delegation_errors(json_routes, operation_ids)
if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)
delegating = sum(1 for r in json_routes if r.get("delegates_to"))
print(
    f"delegation: {delegating} delegating routes all resolve to "
    f"operationIds in {CONTROL_PLANE_API.name}"
)

contract_catalog_ids = [
    entry["id"] for entry in single_pane["ui_catalog"]
]
aggregated_ids = aggregation["catalog_ids"]
errors = catalog_parity_errors(contract_catalog_ids, aggregated_ids)
if errors:
    for error in errors:
        print(f"ERROR: {error}")
    sys.exit(1)
print(
    f"catalog parity: portal aggregation covers all "
    f"{len(contract_catalog_ids)} ui_catalog ids, 1:1"
)

contract_html = [
    [route["path"], route["view"]]
    for route in portal["api_surface"]["html_routes"]
]
if contract_html != aggregation["html_routes"]:
    fail(
        f"html route drift: contract {contract_html} != "
        f"api.py HTML_ROUTES {aggregation['html_routes']}"
    )
for route in json_routes:
    path = route["path"]
    if path in api_source:
        continue
    if "/lifecycle/" in path:
        name = path.rsplit("/", 1)[1]
        if TRANSITION_TEMPLATE in api_source and f'"{name}"' in api_source:
            continue
    fail(f"json_route {path} is not bound in {API_MODULE}")
for route in portal["api_surface"]["unauthenticated_routes"]:
    if route["path"] not in api_source:
        fail(
            f"unauthenticated route {route['path']} is not bound in "
            f"{API_MODULE}"
        )
print(
    f"route parity: {len(contract_html)} html + {len(json_routes)} "
    f"json + "
    f"{len(portal['api_surface']['unauthenticated_routes'])} "
    f"unauthenticated routes all bound in {API_MODULE.name}"
)

profile = json.loads(PROFILE_SCHEMA.read_text(encoding="utf-8"))
endpoint_properties = (
    profile.get("properties", {})
    .get("endpoints", {})
    .get("properties", {})
)
if "portal" not in endpoint_properties:
    fail(
        f"{PROFILE_SCHEMA}: endpoints carries no `portal` key "
        "(ADR-0005 additive change missing)"
    )
print(f"profile: {PROFILE_SCHEMA.name} endpoints carries `portal`")

# Seeded rejection: prove the checks above FAIL on bad input. Both
# run against in-memory copies; nothing on disk is touched.
seeded_routes = copy.deepcopy(json_routes)
seeded_delegating = [
    route for route in seeded_routes if route.get("delegates_to")
]
if not seeded_delegating:
    fail("seeded check needs at least one delegating route")
seeded_delegating[0]["delegates_to"] = "operationThatDoesNotExist"
if not delegation_errors(seeded_routes, operation_ids):
    fail(
        "seeded-invalid delegates_to was NOT rejected; the "
        "delegation check is broken"
    )
print(
    "seeded rejection 1/2: nonexistent delegates_to operationId "
    "rejected as expected"
)

if not catalog_parity_errors(contract_catalog_ids, aggregated_ids[:-1]):
    fail(
        "seeded-missing catalog id was NOT rejected; the catalog "
        "parity check is broken"
    )
print(
    "seeded rejection 2/2: catalog id missing from the portal "
    "aggregation rejected as expected"
)
PY
echo "Cross-contract checks passed."

echo "Portal contract validation passed."
