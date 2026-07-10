"""Offline tests for the isolation provisioning renders (Batch 20
Task 3).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 20 validator - never under pytest. Every run
uses temp directories for the render target repo root (and, for the
end-to-end test, the control-plane store); the repository's own
gitops/ tree is never touched.

Covers the Task 3 completion check against
contracts/tenancy/TENANT_ISOLATION_MATRIX_V1.yaml:

- each isolation class plans exactly the matrix-defined artifact set:
  per-tenant OpenSearch roles and role mappings, dashboard space,
  vector index with the mandatory retrieval filter, and the graph
  artifact (per-tenant Neo4j database naming in every class, gated to
  graph-enabled mode);
- shared-partition roles carry the tenant_id document-level security
  filter on the Batch 8 shared patterns; dedicated classes scope
  tenant-<id>-<signal>-* patterns with reader and writer roles;
- regeneration is byte-identical, every artifact carries the
  generated-file header marker, and no environment value leaks into
  generated output;
- execution goes through the Batch 19 renderer and writes only under
  the tenant-scoped directories;
- the lifecycle service provision transition materializes the
  artifacts end to end.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
LIFECYCLE_CONTRACT = (
    REPO_ROOT
    / "contracts"
    / "tenancy"
    / "TENANT_LIFECYCLE_CONTRACT_V1.yaml"
)

sys.path.insert(0, str(REPO_ROOT / "services" / "tenancy"))
sys.path.insert(0, str(REPO_ROOT / "tools" / "obskit"))

from tenantctl.isolation import (  # noqa: E402
    DASHBOARD_SPACE_FILENAME,
    GRAPH_ACCESS_FILENAME,
    GRAPH_DATABASE_FILENAME,
    GRAPH_PROFILE_GATE,
    ISOLATION_MANIFEST_FILENAME,
    ROLE_MAPPINGS_FILENAME,
    ROLES_FILENAME,
    SHARED_ISOLATION_ROOT,
    VECTOR_INDEX_FILENAME,
    IsolationRenderArtifact,
    execute_isolation_renders,
    isolation_dir,
    plan_isolation_renders,
)
from tenantctl.renders import (  # noqa: E402
    OVERLAY_MARKER,
    OVERLAY_MARKER_COMMENT,
    overlay_dir,
)
from tenantctl.service import TenantControlPlaneService  # noqa: E402
from tenantctl.store import ControlPlaneStore  # noqa: E402

ALL_CLASSES = (
    "shared-partition",
    "dedicated-indices",
    "dedicated-stack",
)
SIGNALS = ("logs", "metrics", "traces")


def tenant_document(
    tenant_id: str, isolation_class: str
) -> dict[str, Any]:
    pool = (
        "dedicated" if isolation_class == "dedicated-stack"
        else "shared"
    )
    return {
        "tenant_id": tenant_id,
        "display_name": "Acme Corp",
        "tier": "enterprise",
        "isolation_class": isolation_class,
        "residency": {
            "region": "region-a",
            "data_residency_required": True,
            "pool": pool,
            "allowed_regions": ["region-a"],
        },
        "lifecycle_state": "provisioning",
        "owner": {
            "name": "Platform Team",
            "email": "owner@example.com",
        },
        "contacts": [
            {"role": "technical", "email": "tech@example.com"},
        ],
        "quotas": {
            "ingest": {
                "max_gb_per_day": 50,
                "max_events_per_second": 1000,
            },
            "retention": {
                "logs_days": 30,
                "metrics_days": 90,
                "traces_days": 14,
            },
        },
        "created_at": "2026-07-01T00:00:00Z",
    }


def plan_for(
    isolation_class: str, tenant_id: str = "acme"
) -> tuple[IsolationRenderArtifact, ...]:
    return plan_isolation_renders(
        tenant_document(tenant_id, isolation_class), "provision"
    )


def artifact_by_name(
    artifacts: tuple[IsolationRenderArtifact, ...], filename: str
) -> IsolationRenderArtifact:
    matches = [
        artifact
        for artifact in artifacts
        if artifact.path.endswith(f"/{filename}")
    ]
    assert len(matches) == 1, (
        f"expected exactly one {filename}, got "
        f"{[a.path for a in artifacts]}"
    )
    return matches[0]


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(
                path.relative_to(root).as_posix().encode("utf-8")
            )
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_plan_artifact_set_per_isolation_class() -> None:
    for isolation_class in ALL_CLASSES:
        artifacts = plan_for(isolation_class)
        directory = isolation_dir("acme", isolation_class)
        graph_filename = (
            GRAPH_ACCESS_FILENAME
            if isolation_class == "shared-partition"
            else GRAPH_DATABASE_FILENAME
        )
        expected = {
            f"{directory}{ROLES_FILENAME}",
            f"{directory}{ROLE_MAPPINGS_FILENAME}",
            f"{directory}{DASHBOARD_SPACE_FILENAME}",
            f"{directory}{VECTOR_INDEX_FILENAME}",
            f"{directory}{graph_filename}",
        }
        assert {a.path for a in artifacts} == expected, (
            isolation_class
        )
        assert len(artifacts) == 5


def test_isolation_directories_per_class() -> None:
    # dedicated-stack artifacts live inside the tenant overlay; the
    # shared classes use the additive tenant-scoped platform path and
    # never touch the overlay root (the lifecycle service renders no
    # overlay for them).
    assert isolation_dir("acme", "dedicated-stack") == (
        f"{overlay_dir('acme')}isolation/"
    )
    for isolation_class in ("shared-partition", "dedicated-indices"):
        assert isolation_dir("acme", isolation_class) == (
            f"{SHARED_ISOLATION_ROOT}acme/isolation/"
        )
        for artifact in plan_for(isolation_class):
            assert not artifact.path.startswith(
                "gitops/overlays/"
            ), artifact.path


def test_shared_partition_roles_content() -> None:
    roles = artifact_by_name(
        plan_for("shared-partition"), ROLES_FILENAME
    ).content
    dls = '{"term": {"tenant_id": "acme"}}'
    for signal in SIGNALS:
        # Reader constrained to the Batch 8 shared patterns with the
        # tenant DLS filter (CTR-02); env/team stay placeholders.
        assert f"tenant-acme-{signal}-reader:" in roles
        assert f"- {signal}-<env>-<team>-*" in roles
        # Tenant principals never write telemetry (writer: null).
        assert f"tenant-acme-{signal}-writer:" not in roles
    assert f"document_level_security: '{dls}'" in roles
    # Vector floor rule: per-tenant vector index even in this class.
    assert "tenant-acme-vectors-reader:" in roles
    assert "tenant-acme-vectors-writer:" in roles
    assert "- tenant-acme-vectors-*" in roles
    # No spanning wildcards (CTR-01) and no unresolved tenant slot.
    assert "- tenant-*" not in roles
    assert "- logs-*" not in roles
    assert "<tenant_id>" not in roles


def test_dedicated_roles_content() -> None:
    for isolation_class in ("dedicated-indices", "dedicated-stack"):
        roles = artifact_by_name(
            plan_for(isolation_class), ROLES_FILENAME
        ).content
        for signal in SIGNALS:
            assert f"tenant-acme-{signal}-reader:" in roles
            assert f"tenant-acme-{signal}-writer:" in roles
            assert f"- tenant-acme-{signal}-*" in roles
            # Batch 8 shared patterns do not appear in dedicated
            # classes; the namespace prefix is the boundary.
            assert f"- {signal}-<env>-<team>-*" not in roles
        assert "document_level_security" not in roles
        assert "tenant-acme-vectors-reader:" in roles
        assert "tenant-acme-vectors-writer:" in roles


def test_role_mappings_content() -> None:
    for isolation_class in ALL_CLASSES:
        mappings = artifact_by_name(
            plan_for(isolation_class), ROLE_MAPPINGS_FILENAME
        ).content
        shared = isolation_class == "shared-partition"
        for signal in SIGNALS + ("vectors",):
            assert f"tenant-acme-{signal}-mapping:" in mappings
        # Backend role names come from the identity backend adapter
        # (Batch 13); no identity-provider group id is hardcoded.
        assert "backend_roles_source: identity-backend-adapter" in (
            mappings
        )
        assert (
            "writer_binding: embedding-pipeline-service-identity"
            in mappings
        )
        telemetry_writer = (
            "writer_binding: "
            "tenant-collector-pipeline-service-identity"
        )
        if shared:
            assert telemetry_writer not in mappings
            assert "tenant-acme-logs-writer" not in mappings
        else:
            assert telemetry_writer in mappings
            assert "- tenant-acme-logs-writer" in mappings


def test_dashboard_space_content() -> None:
    for isolation_class in ALL_CLASSES:
        space = artifact_by_name(
            plan_for(isolation_class), DASHBOARD_SPACE_FILENAME
        ).content
        assert "name: tenant-acme" in space
        for signal in SIGNALS + ("vectors",):
            assert f"- tenant-acme-{signal}-reader" in space
        assert "cross_tenant_access: deny" in space


def test_vector_index_mandatory_filter_all_classes() -> None:
    for isolation_class in ALL_CLASSES:
        vector = artifact_by_name(
            plan_for(isolation_class), VECTOR_INDEX_FILENAME
        ).content
        assert "store: opensearch-knn" in vector
        assert "index_pattern: tenant-acme-vectors-*" in vector
        assert "required: true" in vector
        assert (
            "filter: '{\"term\": {\"tenant_id\": \"acme\"}}'"
            in vector
        )
        assert "on_missing_filter: reject" in vector
        assert "on_tenant_mismatch: deny" in vector


def test_graph_artifact_per_class_and_gate() -> None:
    for isolation_class in ALL_CLASSES:
        artifacts = plan_for(isolation_class)
        shared = isolation_class == "shared-partition"
        graph_filename = (
            GRAPH_ACCESS_FILENAME if shared
            else GRAPH_DATABASE_FILENAME
        )
        graph = artifact_by_name(artifacts, graph_filename).content
        # Present only in graph-enabled mode: the artifact is gated
        # declaratively by the graph profile marker (the tenant
        # contract has no graph field and generation may use tenant
        # descriptor fields only), so with graph-disabled it is never
        # deployed - same mechanism as the graph module's own GitOps
        # artifacts.
        assert GRAPH_PROFILE_GATE in graph
        assert "graph-enabled" in graph
        # Matrix graph rows: one Neo4j database per tenant, identical
        # naming in every class, tenant-scoped access rules, system
        # database denied.
        assert "store: neo4j" in graph
        assert "database: tenant-acme" in graph
        assert "session_scope: pinned-to-tenant-database" in graph
        assert "system_database: denied" in graph
        assert "dashboard_space: tenant-acme" in graph
        # The alternate graph filename never appears alongside.
        other = (
            GRAPH_DATABASE_FILENAME if shared
            else GRAPH_ACCESS_FILENAME
        )
        assert not any(
            artifact.path.endswith(f"/{other}")
            for artifact in artifacts
        )


def test_header_marker_and_no_environment_values() -> None:
    forbidden = (
        "region-a",  # residency region never leaks into isolation
        "repoURL",
        "targetRevision",
        "http://",
        "https://",
        "example.com",
        "<tenant_id>",
    )
    for isolation_class in ALL_CLASSES:
        for artifact in plan_for(isolation_class):
            first_line = artifact.content.splitlines()[0]
            assert first_line == OVERLAY_MARKER_COMMENT, (
                artifact.path
            )
            for needle in forbidden:
                assert needle not in artifact.content, (
                    f"{needle!r} in {artifact.path}"
                )
            assert artifact.content.endswith("\n")
            assert artifact.description


def test_regeneration_byte_identical() -> None:
    for isolation_class in ALL_CLASSES:
        assert plan_for(isolation_class) == plan_for(
            isolation_class
        )
    tmp = Path(tempfile.mkdtemp(prefix="isolation-test-"))
    try:
        repo_root = tmp / "repo"
        repo_root.mkdir()
        artifacts = plan_for("dedicated-stack")
        execute_isolation_renders(
            artifacts, repo_root=str(repo_root), tenant_id="acme"
        )
        before = tree_digest(repo_root)
        execute_isolation_renders(
            artifacts, repo_root=str(repo_root), tenant_id="acme"
        )
        assert tree_digest(repo_root) == before
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_execute_writes_only_tenant_scoped_paths() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="isolation-test-"))
    try:
        repo_root = tmp / "repo"
        repo_root.mkdir()
        for isolation_class, prefix in (
            ("shared-partition", f"{SHARED_ISOLATION_ROOT}acme/"),
            ("dedicated-indices", f"{SHARED_ISOLATION_ROOT}acme/"),
            ("dedicated-stack", overlay_dir("acme")),
        ):
            class_root = tmp / isolation_class.replace("-", "_")
            class_root.mkdir()
            artifacts = plan_for(isolation_class)
            execute_isolation_renders(
                artifacts,
                repo_root=str(class_root),
                tenant_id="acme",
            )
            written = [
                path
                for path in class_root.rglob("*")
                if path.is_file()
            ]
            assert written, isolation_class
            for path in written:
                relative = path.relative_to(class_root).as_posix()
                assert relative.startswith(prefix), relative
            # The render manifest lands beside the artifacts and
            # carries the generated-file marker plus one entry per
            # artifact.
            manifest_path = (
                class_root
                / isolation_dir("acme", isolation_class)
                / ISOLATION_MANIFEST_FILENAME
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            assert manifest["marker"] == OVERLAY_MARKER
            assert len(manifest["artifacts"]) == len(artifacts)
        # A plan that escapes the tenant-scoped directories is
        # refused outright - nothing is written.
        foreign = (
            IsolationRenderArtifact(
                path="gitops/charts/platform-core/values.yaml",
                content="# nope\n",
                description="escapes tenant scope",
            ),
        )
        try:
            execute_isolation_renders(
                foreign, repo_root=str(repo_root), tenant_id="acme"
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "expected ValueError for out-of-scope artifact path"
            )
        other_tenant = (
            IsolationRenderArtifact(
                path=f"{SHARED_ISOLATION_ROOT}mallory/isolation/x.yaml",
                content="# nope\n",
                description="another tenant's directory",
            ),
        )
        try:
            execute_isolation_renders(
                other_tenant,
                repo_root=str(repo_root),
                tenant_id="acme",
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                "expected ValueError for cross-tenant artifact path"
            )
        assert not list(repo_root.rglob("*"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_unimplemented_mode_plans_nothing() -> None:
    document = tenant_document("acme", "dedicated-stack")
    for mode in ("suspend", "resume", "offboard", "purge", "other"):
        assert plan_isolation_renders(document, mode) == ()
    # Executing an empty plan is a no-op, not an error.
    tmp = Path(tempfile.mkdtemp(prefix="isolation-test-"))
    try:
        execute_isolation_renders(
            (), repo_root=str(tmp), tenant_id="acme"
        )
        assert not list(tmp.rglob("*"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_service_provision_materializes_isolation_artifacts() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="isolation-test-"))
    try:
        repo_root = tmp / "repo"
        repo_root.mkdir()
        service = TenantControlPlaneService(
            store=ControlPlaneStore(tmp / "store"),
            repo_root=repo_root,
            lifecycle_contract_path=LIFECYCLE_CONTRACT,
        )
        # dedicated-stack: isolation artifacts live inside the tenant
        # overlay, next to the contract's two overlay files.
        service.create_tenant(tenant_document("acme", "dedicated-stack"))
        service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        stack_dir = repo_root / isolation_dir("acme", "dedicated-stack")
        stack_files = sorted(
            path.name
            for path in stack_dir.iterdir()
            if path.is_file()
        )
        assert stack_files == sorted(
            [
                DASHBOARD_SPACE_FILENAME,
                GRAPH_DATABASE_FILENAME,
                ISOLATION_MANIFEST_FILENAME,
                ROLE_MAPPINGS_FILENAME,
                ROLES_FILENAME,
                VECTOR_INDEX_FILENAME,
            ]
        )
        overlay_top = sorted(
            path.name
            for path in (repo_root / overlay_dir("acme")).iterdir()
            if path.is_file()
        )
        assert overlay_top == [
            "applicationset-element.yaml",
            "tenant-values.yaml",
        ]
        # shared-partition: artifacts land under the tenant-scoped
        # platform path; no overlay directory is created.
        service.create_tenant(
            tenant_document("shared1", "shared-partition")
        )
        service.transition(
            "provision", "shared1", {"actor": "op@example.com"}
        )
        shared_dir = repo_root / isolation_dir(
            "shared1", "shared-partition"
        )
        shared_files = sorted(
            path.name
            for path in shared_dir.iterdir()
            if path.is_file()
        )
        assert shared_files == sorted(
            [
                DASHBOARD_SPACE_FILENAME,
                GRAPH_ACCESS_FILENAME,
                ISOLATION_MANIFEST_FILENAME,
                ROLE_MAPPINGS_FILENAME,
                ROLES_FILENAME,
                VECTOR_INDEX_FILENAME,
            ]
        )
        assert not (repo_root / overlay_dir("shared1")).exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_provision_replay_converges_isolation_artifacts() -> None:
    """A provision replay restores deleted/drifted isolation
    artifacts in every isolation class (create-if-absent,
    converge-if-drifted) and is still an audited replay; a no-drift
    replay stays replayed-no-diff."""
    tmp = Path(tempfile.mkdtemp(prefix="isolation-test-"))
    try:
        repo_root = tmp / "repo"
        repo_root.mkdir()
        service = TenantControlPlaneService(
            store=ControlPlaneStore(tmp / "store"),
            repo_root=repo_root,
            lifecycle_contract_path=LIFECYCLE_CONTRACT,
        )
        # dedicated-stack: isolation lives inside the overlay.
        service.create_tenant(tenant_document("acme", "dedicated-stack"))
        service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        roles = (
            repo_root
            / isolation_dir("acme", "dedicated-stack")
            / ROLES_FILENAME
        )
        original = roles.read_bytes()
        roles.unlink()
        result = service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert result.replay is True
        assert roles.is_file()
        assert roles.read_bytes() == original
        # Drift was converged: reflected exactly like overlay drift.
        assert result.gitops_render.render_action == "rendered"
        assert result.gitops_render.overlay_path == overlay_dir("acme")
        # No drift left: the next replay is a no-diff replay.
        result = service.transition(
            "provision", "acme", {"actor": "op@example.com"}
        )
        assert result.replay is True
        assert result.gitops_render.render_action == (
            "replayed-no-diff"
        )
        # shared-partition: no overlay exists, but the isolation
        # artifacts under the tenant-scoped platform path converge
        # the same way.
        service.create_tenant(
            tenant_document("shared1", "shared-partition")
        )
        service.transition(
            "provision", "shared1", {"actor": "op@example.com"}
        )
        vector = (
            repo_root
            / isolation_dir("shared1", "shared-partition")
            / VECTOR_INDEX_FILENAME
        )
        vector.unlink()
        result = service.transition(
            "provision", "shared1", {"actor": "op@example.com"}
        )
        assert result.replay is True
        assert vector.is_file()
        assert result.gitops_render.render_action == "rendered"
        assert result.gitops_render.overlay_path is None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
