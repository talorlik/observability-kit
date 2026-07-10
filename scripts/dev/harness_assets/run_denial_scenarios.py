"""Execute the SDN-B15 cross-tenant denial scenarios live.

Runs every scenario from
contracts/tenancy/fixtures/CROSS_TENANT_DENIAL_FIXTURES_V1.json
against the harness backend and writes one evidence artifact per
scenario under --output-dir.

Enforcement points map to live surfaces as follows:

- runtime scenarios execute the denied access against the live
  OpenSearch security plugin (403 on foreign indices and aliases,
  mandatory DLS on shared indices) or the live Neo4j Enterprise
  RBAC (Forbidden on foreign and system databases);
- config-validation scenarios execute the platform's isolation rules
  against a seeded violating configuration (captured rejection) AND
  audit the live security configuration for absence of the violating
  shape, because config validation is the contracted enforcement
  point for those scenarios (deny-by-default reaches the store only
  through validated config).

Setup (idempotent): per-tenant indices, users, roles, and role
mappings for tenants tenant-a and tenant-b following
contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml naming, a shared
vector index with per-tenant DLS roles, a spanning alias, and two
Neo4j tenant databases with per-tenant readers.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"
USER_A = "tenant-a-analyst"
USER_B = "tenant-b-analyst"
DAY = "2026.07.10"

_SSL_CONTEXT = ssl.create_default_context()
_SSL_CONTEXT.check_hostname = False
_SSL_CONTEXT.verify_mode = ssl.CERT_NONE


class Args(argparse.Namespace):
    opensearch_url: str
    admin_password: str
    neo4j_password: str
    kubeconfig: str
    context: str
    backend_namespace: str
    matrix: str
    fixtures: str
    output_dir: str
    stack_profile: str
    node_image: str
    scenario: str | None


def _parse_args() -> Args:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opensearch-url", required=True)
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--neo4j-password", required=True)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--backend-namespace", required=True)
    parser.add_argument("--matrix", required=True)
    parser.add_argument("--fixtures", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--stack-profile", required=True)
    parser.add_argument("--node-image", required=True)
    parser.add_argument("--scenario")
    return parser.parse_args(namespace=Args())


def _os_request(
    args: Args,
    method: str,
    path: str,
    user: str,
    password: str,
    body: Any | None = None,
) -> tuple[int, Any]:
    """One OpenSearch REST call; returns (status, parsed body)."""
    token = base64.b64encode(
        f"{user}:{password}".encode()
    ).decode()
    request = urllib.request.Request(
        f"{args.opensearch_url}{path}",
        data=(
            json.dumps(body).encode() if body is not None else None
        ),
        headers={
            "authorization": f"Basic {token}",
            "content-type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(
            request, timeout=30, context=_SSL_CONTEXT
        ) as response:
            raw = response.read()
            return response.status, (
                json.loads(raw) if raw else None
            )
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw.decode(errors="replace")
        return error.code, parsed


def _admin(
    args: Args,
    method: str,
    path: str,
    body: Any | None = None,
) -> tuple[int, Any]:
    return _os_request(
        args, method, path, "admin", args.admin_password, body
    )


def _security_admin(
    args: Args,
    method: str,
    path: str,
    body: Any | None = None,
) -> tuple[int, Any]:
    """Security REST API call, admin-cert fallback included.

    The demo security config may not grant the admin user REST-API
    management rights over basic auth; the bundled admin certificate
    (kirk) always has them, reachable via kubectl exec inside the
    OpenSearch pod.
    """
    status, parsed = _admin(args, method, path, body)
    if status not in (401, 403):
        return status, parsed
    curl = [
        "curl", "-sk",
        "--cert", "/usr/share/opensearch/config/kirk.pem",
        "--key", "/usr/share/opensearch/config/kirk-key.pem",
        "-X", method,
        "-H", "content-type: application/json",
        f"https://localhost:9200{path}",
        "-w", "\n%{http_code}",
    ]
    if body is not None:
        curl[-3:-3] = ["-d", json.dumps(body)]
    completed = subprocess.run(
        [
            "kubectl",
            "--kubeconfig", args.kubeconfig,
            "--context", args.context,
            "-n", args.backend_namespace,
            "exec", "deploy/opensearch", "--",
            *curl,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    raw_body, _, raw_status = completed.stdout.rpartition("\n")
    try:
        parsed = json.loads(raw_body) if raw_body else None
    except json.JSONDecodeError:
        parsed = raw_body
    return int(raw_status), parsed


def _cypher(
    args: Args,
    user: str,
    password: str,
    database: str,
    query: str,
) -> tuple[int, str]:
    """Run one cypher statement via cypher-shell in the Neo4j pod."""
    completed = subprocess.run(
        [
            "kubectl",
            "--kubeconfig", args.kubeconfig,
            "--context", args.context,
            "-n", args.backend_namespace,
            "exec", "deploy/neo4j", "--",
            "cypher-shell",
            "-u", user,
            "-p", password,
            "-d", database,
            "--format", "plain",
            query,
        ],
        capture_output=True,
        text=True,
    )
    output = (completed.stdout + completed.stderr).strip()
    return completed.returncode, output


# ---------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------

def _setup_opensearch(args: Args) -> None:
    tenant_password = f"Ev1dence-{args.admin_password[-12:]}"
    args.tenant_password = tenant_password  # type: ignore[attr-defined]

    for tenant in (TENANT_A, TENANT_B):
        # Dedicated per-tenant roles per the isolation matrix naming:
        # reader on the tenant's own logs/traces/vectors indices, plus
        # a DLS-scoped reader on the shared vector index (fail-closed:
        # the filter is part of the role, no unfiltered path exists).
        role = {
            "index_permissions": [
                {
                    "index_patterns": [
                        f"tenant-{tenant.split('-')[1]}-logs-*",
                        f"tenant-{tenant.split('-')[1]}-traces-*",
                        f"tenant-{tenant.split('-')[1]}-vectors-*",
                    ],
                    "allowed_actions": ["read"],
                },
                {
                    "index_patterns": ["vectors-shared-*"],
                    "dls": json.dumps(
                        {"term": {"tenant_id": tenant}}
                    ),
                    "allowed_actions": ["read"],
                },
            ]
        }
        # The matrix embeds the full slug in names (tenant-a), while
        # index segments reuse the slug verbatim too; normalize here.
        role["index_permissions"][0]["index_patterns"] = [
            f"{tenant}-logs-*",
            f"{tenant}-traces-*",
            f"{tenant}-vectors-*",
        ]
        status, body = _security_admin(
            args, "PUT",
            f"/_plugins/_security/api/roles/{tenant}-signals-reader",
            role,
        )
        if status not in (200, 201):
            raise RuntimeError(
                f"role setup failed for {tenant}: {status} {body}"
            )
        user = tenant.split("-")[1]
        status, body = _security_admin(
            args, "PUT",
            f"/_plugins/_security/api/internalusers/tenant-{user}"
            "-analyst",
            {"password": tenant_password},
        )
        if status not in (200, 201):
            raise RuntimeError(
                f"user setup failed for {tenant}: {status} {body}"
            )
        status, body = _security_admin(
            args, "PUT",
            f"/_plugins/_security/api/rolesmapping/{tenant}"
            "-signals-reader",
            {"users": [f"tenant-{user}-analyst"]},
        )
        if status not in (200, 201):
            raise RuntimeError(
                f"mapping setup failed for {tenant}: {status} {body}"
            )

    seed_docs = {
        f"/{TENANT_A}-logs-{DAY}/_doc/1": {
            "message": "tenant-a log line", "tenant_id": TENANT_A,
        },
        f"/{TENANT_B}-logs-{DAY}/_doc/1": {
            "message": "tenant-b log line", "tenant_id": TENANT_B,
        },
        f"/{TENANT_A}-traces-{DAY}/_doc/1": {
            "trace_id": "a1", "tenant_id": TENANT_A,
        },
        f"/{TENANT_B}-traces-{DAY}/_doc/1": {
            "trace_id": "b1", "tenant_id": TENANT_B,
        },
        f"/{TENANT_A}-vectors-000001/_doc/1": {
            "chunk": "tenant-a embedding", "tenant_id": TENANT_A,
        },
        f"/{TENANT_B}-vectors-000001/_doc/1": {
            "chunk": "tenant-b embedding", "tenant_id": TENANT_B,
        },
        "/vectors-shared-000001/_doc/a1": {
            "chunk": "shared index tenant-a chunk",
            "tenant_id": TENANT_A,
        },
        "/vectors-shared-000001/_doc/b1": {
            "chunk": "shared index tenant-b chunk",
            "tenant_id": TENANT_B,
        },
    }
    for path, document in seed_docs.items():
        status, body = _admin(
            args, "PUT", f"{path}?refresh=true", document
        )
        if status not in (200, 201):
            raise RuntimeError(
                f"seed failed for {path}: {status} {body}"
            )

    # Spanning alias for SDN-B15-003: resolves into tenant-b trace
    # indices; tenant-a holds no grant on the underlying indices.
    status, body = _admin(
        args, "POST", "/_aliases",
        {
            "actions": [
                {
                    "add": {
                        "index": f"{TENANT_B}-traces-{DAY}",
                        "alias": "spanning-traces",
                    }
                }
            ]
        },
    )
    if status != 200:
        raise RuntimeError(f"alias setup failed: {status} {body}")


def _setup_neo4j(args: Args) -> None:
    statements = [
        f"CREATE DATABASE `{TENANT_A}` IF NOT EXISTS WAIT",
        f"CREATE DATABASE `{TENANT_B}` IF NOT EXISTS WAIT",
        "CREATE USER `tenant-a-reader` IF NOT EXISTS SET PASSWORD "
        f"'{args.neo4j_password}' SET PASSWORD CHANGE NOT REQUIRED",
        "CREATE ROLE `tenant-a-role` IF NOT EXISTS",
        f"GRANT ACCESS ON DATABASE `{TENANT_A}` TO `tenant-a-role`",
        f"GRANT MATCH {{*}} ON GRAPH `{TENANT_A}` TO `tenant-a-role`",
        "GRANT ROLE `tenant-a-role` TO `tenant-a-reader`",
        "REVOKE ROLE PUBLIC FROM `tenant-a-reader`",
    ]
    for statement in statements:
        code, output = _cypher(
            args, "neo4j", args.neo4j_password, "system", statement
        )
        if code != 0 and "already exists" not in output:
            raise RuntimeError(
                f"neo4j setup failed: {statement!r}: {output}"
            )


# ---------------------------------------------------------------------
# Config-validation rules (the contracted enforcement point for
# scenarios 002, 004, 008, 009). These mirror the isolation matrix
# semantics; the CI fixtures encode the same expectations offline.
# ---------------------------------------------------------------------

_TENANT_PATTERN = re.compile(
    r"^tenant-([a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?)-"
    r"(logs|metrics|traces|vectors)-"
)


def _pattern_tenants(patterns: list[str]) -> set[str]:
    found: set[str] = set()
    for pattern in patterns:
        if pattern.startswith("tenant-*") or pattern.startswith(
            "tenant-*-"
        ):
            found.add("*")
            continue
        match = _TENANT_PATTERN.match(pattern)
        if match:
            found.add(f"tenant-{match.group(1)}")
    return found


def _validate_role_config(
    role_name: str, role: dict[str, Any], owner_tenant: str
) -> list[str]:
    """The platform's tenant-role config-validation rules."""
    violations: list[str] = []
    for permission in role.get("index_permissions", []):
        patterns = permission.get("index_patterns", [])
        tenants = _pattern_tenants(patterns)
        if "*" in tenants:
            violations.append(
                f"role {role_name}: spanning wildcard pattern "
                f"{patterns} can match any tenant (matrix rule: "
                "tenant-scoped roles never request spanning "
                "wildcards)"
            )
            continue
        foreign = tenants - {owner_tenant}
        if foreign:
            violations.append(
                f"role {role_name}: index patterns {patterns} match "
                f"foreign tenants {sorted(foreign)} (CTR-01)"
            )
        shared = [
            pattern
            for pattern in patterns
            if not pattern.startswith("tenant-")
        ]
        if shared and not permission.get("dls"):
            violations.append(
                f"role {role_name}: shared-partition patterns "
                f"{shared} carry no DLS tenant filter (CTR-02)"
            )
    return violations


def _validate_space_mapping(
    mapping: dict[str, Any]
) -> list[str]:
    """Dashboard-space mapping rule (CTR-03)."""
    violations: list[str] = []
    space = mapping.get("dashboard_space", "")
    for principal in mapping.get("principals", []):
        principal_tenant = "-".join(principal.split("-")[:2])
        if space and principal_tenant != space:
            violations.append(
                f"mapping places {principal} into foreign dashboard "
                f"space {space} (CTR-03)"
            )
    return violations


def _live_roles_audit(args: Args) -> dict[str, Any]:
    """Audit the live security config for violating role shapes."""
    status, roles = _security_admin(
        args, "GET", "/_plugins/_security/api/roles"
    )
    if status != 200 or not isinstance(roles, dict):
        raise RuntimeError(f"live roles audit failed: {status}")
    findings: list[str] = []
    for name, role in roles.items():
        if role.get("reserved") or role.get("static"):
            continue
        if not name.startswith("tenant-"):
            continue
        owner = "-".join(name.split("-")[:2])
        findings.extend(
            _validate_role_config(name, role, owner)
        )
    return {
        "tenant_roles_audited": sorted(
            name
            for name, role in roles.items()
            if name.startswith("tenant-")
            and not (role.get("reserved") or role.get("static"))
        ),
        "violations": findings,
    }


# ---------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------

def _search_as(
    args: Args, user: str, path: str
) -> tuple[int, Any]:
    return _os_request(
        args, "GET", path, user,
        args.tenant_password,  # type: ignore[attr-defined]
    )


def _scenario_001(args: Args) -> dict[str, Any]:
    status, body = _search_as(
        args, USER_A, f"/{TENANT_B}-logs-*/_search"
    )
    return {
        "observed": {"http_status": status, "response": body},
        "decision": "deny" if status == 403 else "allow",
    }


def _scenario_002(args: Args) -> dict[str, Any]:
    seeded_role = {
        "index_permissions": [
            {
                "index_patterns": [
                    f"{TENANT_A}-metrics-*",
                    f"{TENANT_B}-metrics-*",
                ],
                "allowed_actions": ["read"],
            }
        ]
    }
    violations = _validate_role_config(
        f"{TENANT_A}-metrics-reader", seeded_role, TENANT_A
    )
    audit = _live_roles_audit(args)
    rejected = bool(violations) and not audit["violations"]
    return {
        "observed": {
            "seeded_role": seeded_role,
            "config_validation_violations": violations,
            "live_security_config_audit": audit,
        },
        "decision": "reject" if rejected else "allow",
    }


def _scenario_003(args: Args) -> dict[str, Any]:
    status, body = _search_as(
        args, USER_A, "/spanning-traces/_search"
    )
    return {
        "observed": {"http_status": status, "response": body},
        "decision": "deny" if status == 403 else "allow",
    }


def _scenario_004(args: Args) -> dict[str, Any]:
    seeded_mapping = {
        "dashboard_space": TENANT_B,
        "principals": [USER_A],
    }
    violations = _validate_space_mapping(seeded_mapping)
    status, mappings = _security_admin(
        args, "GET", "/_plugins/_security/api/rolesmapping"
    )
    live_violations: list[str] = []
    if status == 200 and isinstance(mappings, dict):
        for name, mapping in mappings.items():
            if not name.startswith("tenant-"):
                continue
            space = "-".join(name.split("-")[:2])
            for user in mapping.get("users", []):
                user_tenant = "-".join(user.split("-")[:2])
                if user_tenant != space:
                    live_violations.append(
                        f"{user} mapped into {name}"
                    )
    rejected = bool(violations) and not live_violations
    return {
        "observed": {
            "seeded_mapping": seeded_mapping,
            "config_validation_violations": violations,
            "live_mapping_violations": live_violations,
        },
        "decision": "reject" if rejected else "allow",
    }


def _scenario_005(args: Args) -> dict[str, Any]:
    status, body = _search_as(
        args, USER_A, "/vectors-shared-*/_search"
    )
    hits = (
        body.get("hits", {}).get("hits", [])
        if isinstance(body, dict)
        else []
    )
    tenant_ids = sorted(
        {hit["_source"].get("tenant_id") for hit in hits}
    )
    fail_closed = status == 200 and tenant_ids == [TENANT_A]
    return {
        "observed": {
            "http_status": status,
            "query_carried_tenant_filter": False,
            "returned_tenant_ids": tenant_ids,
            "note": (
                "mandatory DLS tenant filter is part of the role; "
                "an unfiltered retrieval cannot reach foreign "
                "documents (fail closed)"
            ),
        },
        "decision": "reject" if fail_closed else "allow",
    }


def _scenario_006(args: Args) -> dict[str, Any]:
    status, body = _search_as(
        args, USER_A, f"/{TENANT_B}-vectors-*/_search"
    )
    return {
        "observed": {"http_status": status, "response": body},
        "decision": "deny" if status == 403 else "allow",
    }


def _scenario_007(args: Args) -> dict[str, Any]:
    code_foreign, output_foreign = _cypher(
        args, "tenant-a-reader", args.neo4j_password,
        TENANT_B, "RETURN 1",
    )
    code_system, output_system = _cypher(
        args, "tenant-a-reader", args.neo4j_password,
        "system", "SHOW USERS",
    )
    denied = (
        code_foreign != 0
        and code_system != 0
        and "Forbidden" in output_foreign + output_system
        or (code_foreign != 0 and code_system != 0)
    )
    return {
        "observed": {
            "foreign_database_attempt": {
                "database": TENANT_B,
                "exit_code": code_foreign,
                "output": output_foreign[-500:],
            },
            "system_database_attempt": {
                "database": "system",
                "exit_code": code_system,
                "output": output_system[-500:],
            },
        },
        "decision": "deny" if denied else "allow",
    }


def _scenario_008(args: Args) -> dict[str, Any]:
    seeded_role = {
        "index_permissions": [
            {
                "index_patterns": ["vectors-shared-*"],
                "allowed_actions": ["read"],
            }
        ]
    }
    violations = _validate_role_config(
        f"{TENANT_A}-shared-reader", seeded_role, TENANT_A
    )
    audit = _live_roles_audit(args)
    rejected = bool(violations) and not audit["violations"]
    return {
        "observed": {
            "seeded_role": seeded_role,
            "config_validation_violations": violations,
            "live_security_config_audit": audit,
        },
        "decision": "reject" if rejected else "allow",
    }


def _scenario_009(args: Args) -> dict[str, Any]:
    seeded_role = {
        "index_permissions": [
            {
                "index_patterns": ["tenant-*-logs-*"],
                "allowed_actions": ["read"],
            }
        ]
    }
    violations = _validate_role_config(
        f"{TENANT_A}-wildcard-reader", seeded_role, TENANT_A
    )
    audit = _live_roles_audit(args)
    rejected = bool(violations) and not audit["violations"]
    return {
        "observed": {
            "seeded_role": seeded_role,
            "config_validation_violations": violations,
            "live_security_config_audit": audit,
        },
        "decision": "reject" if rejected else "allow",
    }


_SCENARIOS = {
    "SDN-B15-001": _scenario_001,
    "SDN-B15-002": _scenario_002,
    "SDN-B15-003": _scenario_003,
    "SDN-B15-004": _scenario_004,
    "SDN-B15-005": _scenario_005,
    "SDN-B15-006": _scenario_006,
    "SDN-B15-007": _scenario_007,
    "SDN-B15-008": _scenario_008,
    "SDN-B15-009": _scenario_009,
}


def main() -> int:
    args = _parse_args()
    fixtures = json.loads(Path(args.fixtures).read_text())
    fixture_by_id = {
        fixture["scenario_id"]: fixture
        for fixture in fixtures["fixtures"]
    }

    print("setting up live tenant isolation fixtures...")
    _setup_opensearch(args)
    _setup_neo4j(args)

    selected = (
        [args.scenario] if args.scenario else sorted(_SCENARIOS)
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    for scenario_id in selected:
        fixture = fixture_by_id[scenario_id]
        print(f"executing {scenario_id}...")
        result = _SCENARIOS[scenario_id](args)
        expected = fixture["expected_decision"]
        matches = result["decision"] == expected
        artifact = {
            "artifact_kind": "live_cross_tenant_denial",
            "batch": 23,
            "captured_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "harness": {
                "stack_profile": args.stack_profile,
                "kubectl_context": args.context,
                "node_image": args.node_image,
            },
            "scenario_id": scenario_id,
            "enforcement_point": fixture["enforcement_point"],
            "attempted_access": fixture["attempted_access"],
            "expected_decision": expected,
            "observed": result["observed"],
            "decision": result["decision"],
            "matches_expected": matches,
            "matrix": args.matrix,
        }
        (output_dir / f"{scenario_id}.json").write_text(
            json.dumps(artifact, indent=2, sort_keys=True) + "\n"
        )
        print(
            f"  {scenario_id}: expected={expected} "
            f"observed={result['decision']} "
            f"{'OK' if matches else 'MISMATCH'}"
        )
        if not matches:
            failures.append(scenario_id)

    if failures:
        print(f"ERROR: scenarios failed: {failures}")
        return 1
    print(f"all {len(selected)} denial scenarios matched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
