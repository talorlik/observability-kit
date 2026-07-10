"""Serve the management portal live for the harness GUI smoke.

Wires portalsvc.api.build_app with the real repository contracts (UI
catalog, unified-config flow, admin-access security policy, portal
frontend) and serves it over TLS with uvicorn so
scripts/validate/admin_gui_smoke.sh can probe PORTAL_BASE_URL/healthz
against a live process. The tenant control plane client points at a
loopback placeholder: the smoke probes liveness and the portal
delegates tenant calls lazily, so no control plane process is needed
for this check.

Run from the repository root inside the harness venv
(services/portal[api] installed). Single portal writer per repo root,
per the portal runbook deployment rule.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import uvicorn

from portalsvc.api import build_app
from portalsvc.catalog import load_ui_catalog
from portalsvc.configflow import ConfigFlow
from portalsvc.frontend import PortalFrontendRenderer
from portalsvc.health import summarize_health
from portalsvc.models import HealthSummary
from portalsvc.security import (
    AdminAccessPlaneSecurityPolicy,
    AdminAccessRoleMapping,
)
from portalsvc.tenants import (
    HttpControlPlaneClient,
    PortalTenantService,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
SINGLE_PANE_CONTRACT = (
    REPO_ROOT
    / "contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml"
)
HEALTH_SNAPSHOT = (
    REPO_ROOT / "tests/portal/fixtures/health_snapshot.json"
)


def _health_provider() -> HealthSummary:
    snapshot = json.loads(HEALTH_SNAPSHOT.read_text())["snapshot"]
    return summarize_health(snapshot)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--certfile", required=True)
    parser.add_argument("--keyfile", required=True)
    args = parser.parse_args()

    catalog = load_ui_catalog(SINGLE_PANE_CONTRACT)
    endpoints = {
        (entry.endpoint_profile_key or entry.id): (
            f"https://{entry.id}.evidence.observability-kit.local"
        )
        for entry in catalog
    }
    app = build_app(
        catalog=catalog,
        config_flow=ConfigFlow(
            repo_root=REPO_ROOT,
            document_path=Path(
                "gitops/platform/config/unified_config_document.json"
            ),
            contracts_dir=REPO_ROOT / "contracts",
        ),
        tenant_service=PortalTenantService(
            HttpControlPlaneClient(
                "http://127.0.0.1:9/api/tenancy/v1"
            )
        ),
        health_provider=_health_provider,
        security=AdminAccessPlaneSecurityPolicy(
            role_mapping=AdminAccessRoleMapping(
                readonly_group="obskit-platform-readonly",
                admin_group="obskit-platform-admins",
            ),
            authn_provider="oidc",
            mfa_required=True,
        ),
        frontend=PortalFrontendRenderer(endpoints=endpoints),
    )
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=args.port,
        ssl_certfile=args.certfile,
        ssl_keyfile=args.keyfile,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
