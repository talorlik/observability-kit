"""Per-tenant isolation provisioning renders (Batch 20 Task 3).

Renders, per isolation class, exactly the per-store artifacts fixed by
contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml as GitOps files:
per-tenant OpenSearch security roles and role mappings, the per-tenant
dashboard space, the per-tenant vector index with its mandatory
retrieval filter, and the tenant's graph artifact (Neo4j
multi-database naming plus tenant-scoped access rules). Isolation uses
only native mechanisms of the wrapped systems - OpenSearch security
roles, document-level security, Dashboards tenant spaces, Neo4j
multi-database - applied through provisioning APIs, never forks
(TR-16).

Placement:

- dedicated-stack: inside the tenant's generated overlay directory
  (gitops/overlays/tenants/<tenant_id>/isolation/), so the isolation
  artifacts ship with the overlay and are removed with it at purge.
- shared-partition and dedicated-indices: the tenant-scoped additive
  directory gitops/platform/tenants/<tenant_id>/isolation/. No overlay
  exists for these classes (overlay generation contract), and core
  charts or shared base files are never modified per tenant.

Graph-enabled gating: the tenant contract schema carries no graph
field and the overlay generation contract allows parameterization by
tenant-descriptor fields ONLY, while graph activation is a platform
profile (contracts/graph/GRAPH_MODULE_PROFILE_VALIDATION.json,
*-graph-enabled profiles) - an environment property this renderer must
not consume. The graph artifact is therefore gated declaratively with
the observability-kit.io/profile: graph-enabled marker, the exact
mechanism gitops/platform/graph/neo4j/browser-access.yaml uses: the
file is committed always, deployed only in graph-enabled mode, and
inert otherwise (isolation matrix graph applies_when). Per the matrix
graph rows the database naming (tenant-<tenant_id>) is identical in
every class; shared classes get tenant-scoped access rules against the
shared Neo4j instance (one database per tenant, the floor rule), the
dedicated-stack class gets the per-tenant instance's database.

Batch 8 layering: shared-partition telemetry roles keep the Batch 8
index patterns (<signal>-<env>-<team>-*) with <env>/<team> left as
placeholders bound by the environment overlay at apply time (matrix
naming.placeholders; environment values are forbidden in generated
output). The tenant boundary is the mandatory tenant_id
document-level security filter layered on top (CTR-02).

Every artifact is a deterministic pure function of the validated
tenant document (byte-identical regeneration) and is written
exclusively through the Batch 19 renderer (obskit.configrender
execute_plan) - never via direct store or cluster APIs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

# Importing tenantctl.renders also bootstraps tools/obskit onto
# sys.path when the obskit package is not installed (its module-level
# _ensure_obskit_importable call), so the obskit imports below resolve
# in-repo exactly as they do for the Task 2 overlay renderer.
from tenantctl.renders import (
    OVERLAY_MARKER,
    OVERLAY_MARKER_COMMENT,
    overlay_dir,
)

from obskit.configrender.models import (  # noqa: E402
    PlannedArtifact,
    RenderPlan,
    STRATEGY_OWNED_ARTIFACT,
)
from obskit.configrender.render import (  # noqa: E402
    changed_paths,
    execute_plan,
)
from obskit.emit import canonical_json  # noqa: E402

ISOLATION_SHARED_PARTITION = "shared-partition"
ISOLATION_DEDICATED_INDICES = "dedicated-indices"
ISOLATION_DEDICATED_STACK = "dedicated-stack"
_ISOLATION_CLASSES = (
    ISOLATION_SHARED_PARTITION,
    ISOLATION_DEDICATED_INDICES,
    ISOLATION_DEDICATED_STACK,
)

# The only transition the planner currently renders for; other modes
# return an empty plan rather than raising (interface contract).
MODE_PROVISION = "provision"

# Tenant-scoped isolation root for the shared classes. Additive per
# tenant: nothing under gitops/charts/ or the shared platform base
# files is ever touched.
SHARED_ISOLATION_ROOT = "gitops/platform/tenants/"
ISOLATION_SUBDIR = "isolation/"

TELEMETRY_SIGNALS = ("logs", "metrics", "traces")

ROLES_FILENAME = "opensearch-roles.yaml"
ROLE_MAPPINGS_FILENAME = "opensearch-role-mappings.yaml"
DASHBOARD_SPACE_FILENAME = "dashboard-space.yaml"
VECTOR_INDEX_FILENAME = "vector-index.yaml"
GRAPH_ACCESS_FILENAME = "graph-access.yaml"
GRAPH_DATABASE_FILENAME = "graph-database.yaml"
ISOLATION_MANIFEST_FILENAME = "render-manifest.json"

ISOLATION_MANIFEST_SCHEMA_VERSION = "v1"

# Declarative graph-enabled gate, verbatim from the graph module's
# GitOps artifacts (gitops/platform/graph/neo4j/browser-access.yaml).
GRAPH_PROFILE_GATE = "observability-kit.io/profile: graph-enabled"

_SYSTEM = "tenant-isolation"
_MATRIX_CONTRACT = "contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml"


@dataclass(frozen=True)
class IsolationRenderArtifact:
    """One planned isolation render artifact.

    path is repository-relative; content is the full rendered text.
    """

    path: str
    content: str
    description: str


def isolation_dir(tenant_id: str, isolation_class: str) -> str:
    """Repo-relative isolation directory (trailing slash) per class."""
    if isolation_class == ISOLATION_DEDICATED_STACK:
        return f"{overlay_dir(tenant_id)}{ISOLATION_SUBDIR}"
    return f"{SHARED_ISOLATION_ROOT}{tenant_id}/{ISOLATION_SUBDIR}"


def _tenant_filter(tenant_id: str) -> str:
    # Matches the matrix filter string byte-for-byte once <tenant_id>
    # is resolved: json.dumps' default separators render
    # {"term": {"tenant_id": "<id>"}} with the same spacing.
    return json.dumps({"term": {"tenant_id": tenant_id}})


def _header(
    tenant_id: str, isolation_class: str, purpose: str
) -> list[str]:
    return [
        OVERLAY_MARKER_COMMENT,
        f"# {purpose} for tenant {tenant_id}, rendered from the",
        f"# {isolation_class} rows of {_MATRIX_CONTRACT}.",
    ]


def _role_lines(
    name: str,
    index_patterns: tuple[str, ...],
    allowed_actions: tuple[str, ...],
    dls_filter: str | None,
) -> list[str]:
    # Shape imitates the Batch 8 precedent
    # gitops/platform/search/opensearch/security/roles/
    # team_env_isolation_roles.yaml.
    lines = [
        f"  {name}:",
        "    cluster_permissions: []",
        "    index_permissions:",
        "      - index_patterns:",
    ]
    lines.extend(
        f"          - {pattern}" for pattern in index_patterns
    )
    lines.append("        allowed_actions:")
    lines.extend(
        f"          - {action}" for action in allowed_actions
    )
    if dls_filter is not None:
        lines.append(
            f"        document_level_security: '{dls_filter}'"
        )
    return lines


def build_opensearch_roles(tenant: Mapping[str, Any]) -> str:
    """Per-tenant OpenSearch security roles (all signals + vectors)."""
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    shared = isolation_class == ISOLATION_SHARED_PARTITION
    lines = _header(
        tenant_id, isolation_class, "Per-tenant OpenSearch roles"
    )
    lines.extend(
        [
            "# Applied through the OpenSearch security provisioning",
            "# API (wrap; the wrapped store is never forked, TR-16).",
        ]
    )
    if shared:
        lines.extend(
            [
                "# <env>/<team> are Batch 8 placeholders bound by the",
                "# environment overlay at apply time - never hardcoded",
                "# here. The tenant boundary is the mandatory tenant_id",
                "# document-level security filter (CTR-02). Tenant",
                "# principals never write telemetry: shared-partition",
                "# writes flow only through the platform collector",
                "# service identity, which stamps tenant_id (CTR-06).",
            ]
        )
    else:
        lines.extend(
            [
                "# The tenant namespace prefix is the isolation",
                "# boundary (CTR-01); tenant_id is still stamped at",
                "# ingest for audit and purge evidence. Writer roles",
                "# bind only to the per-tenant collector pipeline",
                "# service identity, never to tenant user principals",
                "# (CTR-06).",
            ]
        )
    lines.append("roles:")
    dls = _tenant_filter(tenant_id) if shared else None
    for signal in TELEMETRY_SIGNALS:
        if shared:
            pattern = f"{signal}-<env>-<team>-*"
            lines.extend(
                _role_lines(
                    f"tenant-{tenant_id}-{signal}-reader",
                    (pattern,),
                    ("read",),
                    dls,
                )
            )
        else:
            pattern = f"tenant-{tenant_id}-{signal}-*"
            lines.extend(
                _role_lines(
                    f"tenant-{tenant_id}-{signal}-reader",
                    (pattern,),
                    ("read",),
                    None,
                )
            )
            lines.extend(
                _role_lines(
                    f"tenant-{tenant_id}-{signal}-writer",
                    (pattern,),
                    ("write",),
                    None,
                )
            )
    # Vector tier floor rule: per-tenant vector index in every class,
    # never a shared vector index (matrix vectors rows).
    vector_pattern = f"tenant-{tenant_id}-vectors-*"
    lines.extend(
        _role_lines(
            f"tenant-{tenant_id}-vectors-reader",
            (vector_pattern,),
            ("read",),
            None,
        )
    )
    lines.extend(
        _role_lines(
            f"tenant-{tenant_id}-vectors-writer",
            (vector_pattern,),
            ("write",),
            None,
        )
    )
    return "\n".join(lines) + "\n"


def build_role_mappings(tenant: Mapping[str, Any]) -> str:
    """Per-tenant role mappings, one per signal (matrix role_mapping).

    Backend role names are resolved by the active identity backend
    adapter (Batch 13); no identity-provider group id is hardcoded.
    """
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    shared = isolation_class == ISOLATION_SHARED_PARTITION
    lines = _header(
        tenant_id, isolation_class, "Per-tenant role mappings"
    )
    lines.append("role_mappings:")
    for signal in TELEMETRY_SIGNALS:
        lines.append(f"  tenant-{tenant_id}-{signal}-mapping:")
        lines.append("    roles:")
        lines.append(f"      - tenant-{tenant_id}-{signal}-reader")
        if not shared:
            lines.append(
                f"      - tenant-{tenant_id}-{signal}-writer"
            )
        lines.append(
            "    backend_roles_source: identity-backend-adapter"
        )
        if not shared:
            lines.append(
                "    writer_binding: "
                "tenant-collector-pipeline-service-identity"
            )
    lines.append(f"  tenant-{tenant_id}-vectors-mapping:")
    lines.append("    roles:")
    lines.append(f"      - tenant-{tenant_id}-vectors-reader")
    lines.append(f"      - tenant-{tenant_id}-vectors-writer")
    lines.append(
        "    backend_roles_source: identity-backend-adapter"
    )
    lines.append(
        "    writer_binding: embedding-pipeline-service-identity"
    )
    return "\n".join(lines) + "\n"


def build_dashboard_space(tenant: Mapping[str, Any]) -> str:
    """Per-tenant dashboard space bound to the tenant reader roles."""
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    lines = _header(
        tenant_id, isolation_class, "Per-tenant dashboard space"
    )
    lines.extend(
        [
            "# Dashboard spaces are per tenant; no role mapping may",
            "# place a tenant principal in another tenant's space and",
            "# no saved object may reference index patterns outside",
            "# this tenant's namespace (CTR-03).",
            "dashboard_space:",
            f"  name: tenant-{tenant_id}",
            "  bound_roles:",
        ]
    )
    for signal in TELEMETRY_SIGNALS + ("vectors",):
        lines.append(f"    - tenant-{tenant_id}-{signal}-reader")
    lines.append("  cross_tenant_access: deny")
    return "\n".join(lines) + "\n"


def build_vector_index(tenant: Mapping[str, Any]) -> str:
    """Per-tenant vector index with the mandatory retrieval filter."""
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    lines = _header(
        tenant_id, isolation_class, "Per-tenant vector index"
    )
    lines.extend(
        [
            "# Floor rule (matrix vectors rows): never a shared",
            "# vector index; every retrieval carries the tenant",
            "# filter as defense in depth and fails closed (CTR-04).",
            "vector_index:",
            "  store: opensearch-knn",
            f"  index_pattern: tenant-{tenant_id}-vectors-*",
            "  mandatory_retrieval_filter:",
            "    required: true",
            f"    filter: '{_tenant_filter(tenant_id)}'",
            "    on_missing_filter: reject",
            "    on_tenant_mismatch: deny",
        ]
    )
    return "\n".join(lines) + "\n"


def build_graph_artifact(tenant: Mapping[str, Any]) -> str:
    """Tenant graph isolation artifact (graph-enabled mode only)."""
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    dedicated_stack = (
        isolation_class == ISOLATION_DEDICATED_STACK
    )
    purpose = (
        "Per-tenant Neo4j database"
        if isolation_class != ISOLATION_SHARED_PARTITION
        else "Tenant-scoped graph access rules"
    )
    lines = _header(tenant_id, isolation_class, purpose)
    lines.extend(
        [
            "# Applies only in graph-enabled mode: gated by the",
            "# profile marker below, exactly like",
            "# gitops/platform/graph/neo4j/browser-access.yaml; with",
            "# graph-disabled this artifact is never deployed",
            "# (isolation matrix graph applies_when).",
        ]
    )
    if dedicated_stack:
        lines.extend(
            [
                "# Database in the per-tenant Neo4j instance rendered",
                "# from the tenant overlay; naming unchanged so graph",
                "# tooling is uniform across classes.",
            ]
        )
    else:
        lines.extend(
            [
                "# One Neo4j database per tenant in the shared Neo4j",
                "# instance (floor rule: never property-partitioned",
                "# shared graphs).",
            ]
        )
    lines.extend(
        [
            "labels:",
            f"  {GRAPH_PROFILE_GATE}",
            "graph:",
            "  store: neo4j",
            f"  database: tenant-{tenant_id}",
            "  access:",
            "    reader_principals: tenant-database-only",
            "    writer_principals: "
            "graph-sync-jobs-tenant-database-only",
            "    session_scope: pinned-to-tenant-database",
            "    system_database: denied",
            f"  dashboard_space: tenant-{tenant_id}",
        ]
    )
    return "\n".join(lines) + "\n"


def plan_isolation_renders(
    tenant: Mapping[str, Any], mode: str
) -> tuple[IsolationRenderArtifact, ...]:
    """Plan isolation render artifacts for a tenant.

    mode names the calling transition; only "provision" renders
    isolation artifacts today, every other mode plans nothing (the
    lifecycle contract keeps partitions unchanged on suspend/resume/
    offboard, and purge is evidence-driven removal, not a render).
    """
    if mode != MODE_PROVISION:
        return ()
    tenant_id: str = tenant["tenant_id"]
    isolation_class: str = tenant["isolation_class"]
    if isolation_class not in _ISOLATION_CLASSES:
        raise ValueError(
            f"unknown isolation_class {isolation_class!r}; expected "
            f"one of {_ISOLATION_CLASSES}"
        )
    directory = isolation_dir(tenant_id, isolation_class)
    graph_filename = (
        GRAPH_ACCESS_FILENAME
        if isolation_class == ISOLATION_SHARED_PARTITION
        else GRAPH_DATABASE_FILENAME
    )
    graph_description = (
        "Tenant-scoped graph access rules (graph-enabled mode)"
        if isolation_class == ISOLATION_SHARED_PARTITION
        else "Per-tenant Neo4j database (graph-enabled mode)"
    )
    return (
        IsolationRenderArtifact(
            path=f"{directory}{ROLES_FILENAME}",
            content=build_opensearch_roles(tenant),
            description=(
                "Per-tenant OpenSearch security roles "
                f"({isolation_class})"
            ),
        ),
        IsolationRenderArtifact(
            path=f"{directory}{ROLE_MAPPINGS_FILENAME}",
            content=build_role_mappings(tenant),
            description=(
                "Per-tenant OpenSearch role mappings "
                f"({isolation_class})"
            ),
        ),
        IsolationRenderArtifact(
            path=f"{directory}{DASHBOARD_SPACE_FILENAME}",
            content=build_dashboard_space(tenant),
            description=(
                f"Per-tenant dashboard space ({isolation_class})"
            ),
        ),
        IsolationRenderArtifact(
            path=f"{directory}{VECTOR_INDEX_FILENAME}",
            content=build_vector_index(tenant),
            description=(
                "Per-tenant vector index with mandatory retrieval "
                f"filter ({isolation_class})"
            ),
        ),
        IsolationRenderArtifact(
            path=f"{directory}{graph_filename}",
            content=build_graph_artifact(tenant),
            description=f"{graph_description} ({isolation_class})",
        ),
    )


def _unified_key(path: str) -> str:
    stem = PurePosixPath(path).stem.replace("-", "_")
    return f"tenancy.isolation.{stem}"


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _validate_artifact_paths(
    artifacts: tuple[IsolationRenderArtifact, ...], tenant_id: str
) -> None:
    # Write-scope guard mirroring the renderer's containment checks:
    # isolation renders may only land inside this tenant's overlay
    # directory or its shared-class isolation directory.
    allowed_prefixes = (
        overlay_dir(tenant_id),
        f"{SHARED_ISOLATION_ROOT}{tenant_id}/",
    )
    for artifact in artifacts:
        parts = PurePosixPath(artifact.path).parts
        if artifact.path.startswith("/") or ".." in parts:
            raise ValueError(
                f"isolation artifact path {artifact.path!r} is not a "
                "clean repo-relative path"
            )
        if not artifact.path.startswith(allowed_prefixes):
            raise ValueError(
                f"isolation artifact path {artifact.path!r} escapes "
                f"the tenant-scoped directories for {tenant_id!r}"
            )


def _build_render_plan(
    artifacts: tuple[IsolationRenderArtifact, ...], tenant_id: str
) -> RenderPlan:
    planned = tuple(
        PlannedArtifact(
            path=artifact.path,
            content=artifact.content,
            strategy=STRATEGY_OWNED_ARTIFACT,
            unified_key=_unified_key(artifact.path),
            system=_SYSTEM,
        )
        for artifact in artifacts
    )
    entries = [
        {
            "path": artifact.path,
            "sha256": _sha256_hex(artifact.content.encode("utf-8")),
            "strategy": artifact.strategy,
            "system": artifact.system,
            "unified_key": artifact.unified_key,
        }
        for artifact in planned
    ]
    digest_source = canonical_json(
        [
            {"path": entry["path"], "sha256": entry["sha256"]}
            for entry in entries
        ]
    ).encode("utf-8")
    document_digest = f"sha256:{_sha256_hex(digest_source)}"
    directory = artifacts[0].path.rsplit("/", 1)[0]
    manifest_path = f"{directory}/{ISOLATION_MANIFEST_FILENAME}"
    manifest_content = canonical_json(
        {
            "schema_version": ISOLATION_MANIFEST_SCHEMA_VERSION,
            "document_digest": document_digest,
            "marker": OVERLAY_MARKER,
            "artifacts": entries,
            "skipped": [],
            "recorded": [],
        }
    )
    digest_hex = document_digest.removeprefix("sha256:")
    commit_message = (
        f"tenancy({tenant_id}): render isolation artifacts "
        f"{digest_hex[:12]}\n"
        "\n"
        f"isolation {directory}/; files {len(planned)}\n"
        "\n"
        f"Isolation-Artifacts-Digest: {document_digest}\n"
        f"Tenant-Isolation-Contract: {_MATRIX_CONTRACT}\n"
    )
    return RenderPlan(
        schema_version=ISOLATION_MANIFEST_SCHEMA_VERSION,
        document_digest=document_digest,
        artifacts=planned,
        skipped=(),
        recorded=(),
        manifest_path=manifest_path,
        manifest_content=manifest_content,
        commit_message=commit_message,
    )


def execute_isolation_renders(
    artifacts: tuple[IsolationRenderArtifact, ...],
    *,
    repo_root: Path | str,
    tenant_id: str,
) -> tuple[str, ...]:
    """Materialize planned isolation artifacts as GitOps renders.

    Writes go exclusively through the Batch 19 renderer
    (obskit.configrender.render.execute_plan) so isolation artifacts
    get the renderer's determinism and idempotency semantics; no
    store or cluster API is ever called here. The render manifest
    lands next to the artifacts (render-manifest.json), itself a
    deterministic function of the artifact set.

    Returns the paths whose on-disk bytes differed from the plan
    before execution (the renderer's changed_paths diff surface): an
    empty tuple means the render was a byte-identical no-op, so
    provision replays can distinguish drift convergence from a
    no-diff replay.
    """
    if not artifacts:
        return ()
    root = Path(repo_root)
    _validate_artifact_paths(artifacts, tenant_id)
    plan = _build_render_plan(artifacts, tenant_id)
    # RenderPlan.manifest_path is normally absolute; here it is kept
    # repo-relative and anchored to the repo root at execution time so
    # planning stays independent of any filesystem location.
    anchored = RenderPlan(
        schema_version=plan.schema_version,
        document_digest=plan.document_digest,
        artifacts=plan.artifacts,
        skipped=plan.skipped,
        recorded=plan.recorded,
        manifest_path=str(root / plan.manifest_path),
        manifest_content=plan.manifest_content,
        commit_message=plan.commit_message,
    )
    changed = changed_paths(anchored, root)
    execute_plan(anchored, root)
    return changed
