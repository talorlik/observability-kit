"""Offline tests for the unified configuration renderer (Batch 19).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 19 validator - never under pytest. Every render
happens in a temp copy of tests/configrender/fixtures/repo/; the
repository's own gitops/ tree is never touched (ADR-0003: the repo is
not adopted by Batch 19).

Covers the Task 2 completion check: schema-validated input, outputs at
every binding's render_target, byte-identical re-renders, header
marker adoption, manifest correctness, required commit trailers,
--check idempotency proof, and rejection of cross-file rule violations
with nothing written.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parents[1]
FIXTURES = TESTS_DIR / "fixtures"
FIXTURE_REPO = FIXTURES / "repo"
DOCUMENT = FIXTURES / "document_valid.json"
CONTRACTS = REPO_ROOT / "contracts"
PKG_ROOT = REPO_ROOT / "tools" / "obskit"

sys.path.insert(0, str(PKG_ROOT))

from obskit.configrender.models import (  # noqa: E402
    ConfigRenderError,
    DEFAULT_MANIFEST_RELPATH,
    MARKER,
    MARKER_COMMENT,
)
from obskit.configrender.patch import set_yaml_scalar  # noqa: E402
from obskit.configrender.render import (  # noqa: E402
    changed_paths,
    execute_plan,
    plan_render,
)

MANIFEST_NAME = DEFAULT_MANIFEST_RELPATH

# Every canonical render target expected to be WRITTEN for the valid
# document (graph.enabled and graph.browser_access_enabled are false,
# so the two neo4j presence-gated targets are deliberate skips).
EXPECTED_WRITTEN = (
    "gitops/apps/ai-runtime-application.yaml",
    "gitops/apps/grafana-application.yaml",
    "gitops/apps/search-stack-application.yaml",
    "gitops/platform/observability/grafana/values/grafana-values.yaml",
    "gitops/platform/observability/values/graph-pipeline.yaml",
    "gitops/platform/observability/values/traces-pipeline.yaml",
    "gitops/platform/search/dashboards/alerts/"
    "notification_destinations.json",
    "gitops/platform/search/dashboards/saved-objects/"
    "provisioning_state.json",
    "gitops/platform/search/dashboards/spaces/team_env_spaces.yaml",
    "gitops/platform/search/opensearch/ilm/logs-ilm-policy.json",
    "gitops/platform/search/opensearch/ilm/metrics-ilm-policy.json",
    "gitops/platform/search/opensearch/ilm/traces-ilm-policy.json",
    "gitops/platform/search/opensearch/security/"
    "default_isolation_class.json",
)
EXPECTED_SKIPPED = (
    "gitops/platform/graph/neo4j/browser-access.yaml",
    "gitops/platform/graph/neo4j/neo4j_module.yaml",
)


def _fresh_repo(workdir: Path) -> Path:
    target = workdir / "repo"
    shutil.copytree(FIXTURE_REPO, target)
    return target


def _tree_digests(root: Path) -> dict[str, str]:
    return {
        entry.relative_to(root).as_posix(): hashlib.sha256(
            entry.read_bytes()
        ).hexdigest()
        for entry in sorted(root.rglob("*"))
        if entry.is_file()
    }


def _render(repo: Path, document: Path = DOCUMENT) -> None:
    plan = plan_render(document, CONTRACTS, repo)
    execute_plan(plan, repo, repo / "COMMIT_MSG.txt")


def _cli(
    argv: list[str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PKG_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "obskit", *argv],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_render_writes_targets_marker_manifest_and_trailers() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        repo = _fresh_repo(Path(workdir))
        plan = plan_render(DOCUMENT, CONTRACTS, repo)
        written = execute_plan(plan, repo, repo / "COMMIT_MSG.txt")

        assert plan.unique_artifact_paths() == EXPECTED_WRITTEN
        for path in EXPECTED_WRITTEN:
            assert (repo / path).is_file(), path
        assert (repo / MANIFEST_NAME).is_file()
        assert str(repo / MANIFEST_NAME) in written

        # Every written YAML target carries the marker as line one.
        for path in EXPECTED_WRITTEN:
            if path.endswith(".yaml"):
                first = (repo / path).read_text().split("\n", 1)[0]
                assert first == MARKER_COMMENT, path

        # Skipped presence-gated targets: not adopted, no marker.
        for path in EXPECTED_SKIPPED:
            text = (repo / path).read_text()
            fixture = (FIXTURE_REPO / path).read_text()
            assert text == fixture, path

        # Patched values landed.
        logs = json.loads(
            (
                repo
                / "gitops/platform/search/opensearch/ilm/"
                "logs-ilm-policy.json"
            ).read_text()
        )
        transition = logs["policy"]["states"][0]["transitions"][0]
        assert transition["conditions"]["min_index_age"] == "30d"
        traces = json.loads(
            (
                repo
                / "gitops/platform/search/opensearch/ilm/"
                "traces-ilm-policy.json"
            ).read_text()
        )
        transition = traces["policy"]["states"][0]["transitions"][0]
        assert transition["conditions"]["min_index_age"] == "14d"
        pipeline = (
            repo
            / "gitops/platform/observability/values/"
            "traces-pipeline.yaml"
        ).read_text()
        assert "      ratio: 0.1\n" in pipeline
        graph = (
            repo
            / "gitops/platform/observability/values/"
            "graph-pipeline.yaml"
        ).read_text()
        assert "  enabled: false\n" in graph
        spaces = (
            repo
            / "gitops/platform/search/dashboards/spaces/"
            "team_env_spaces.yaml"
        ).read_text()
        assert (
            spaces.split("\n")[1]
            == "default_isolation_class: dedicated-indices"
        )
        grafana = (
            repo
            / "gitops/platform/observability/grafana/values/"
            "grafana-values.yaml"
        ).read_text()
        assert "    cookie_secure: true\n" in grafana
        for app in (
            "search-stack-application.yaml",
            "grafana-application.yaml",
            "ai-runtime-application.yaml",
        ):
            text = (repo / "gitops/apps" / app).read_text()
            assert "    automated:\n" in text, app
            assert "      prune: true\n" in text, app
            assert "      selfHeal: true\n" in text, app

        # Owned artifacts are deterministic canonical JSON with the
        # marker field; pre-existing directory files are recorded.
        destinations = json.loads(
            (
                repo
                / "gitops/platform/search/dashboards/alerts/"
                "notification_destinations.json"
            ).read_text()
        )
        assert destinations["marker"] == MARKER
        assert [
            channel["name"] for channel in destinations["channels"]
        ] == ["oncall-escalation", "platform-ops"]
        provisioning = json.loads(
            (
                repo
                / "gitops/platform/search/dashboards/saved-objects/"
                "provisioning_state.json"
            ).read_text()
        )
        assert provisioning["enabled"] is True
        assert provisioning["bundles"], "bundle inventory is empty"
        assert all(
            bundle["name"].endswith(".ndjson")
            for bundle in provisioning["bundles"]
        )
        isolation = json.loads(
            (
                repo
                / "gitops/platform/search/opensearch/security/"
                "default_isolation_class.json"
            ).read_text()
        )
        assert (
            isolation["default_isolation_class"]
            == "dedicated-indices"
        )

        # Manifest correctness.
        manifest = json.loads((repo / MANIFEST_NAME).read_text())
        assert manifest["schema_version"] == "v1"
        assert manifest["marker"] == MARKER
        expected_digest = "sha256:" + hashlib.sha256(
            DOCUMENT.read_bytes()
        ).hexdigest()
        assert manifest["document_digest"] == expected_digest
        entry_keys = [
            (entry["path"], entry["unified_key"])
            for entry in manifest["artifacts"]
        ]
        assert entry_keys == sorted(entry_keys)
        assert {
            entry["path"] for entry in manifest["artifacts"]
        } == set(EXPECTED_WRITTEN)
        for entry in manifest["artifacts"]:
            content = (repo / entry["path"]).read_bytes()
            assert (
                entry["sha256"]
                == hashlib.sha256(content).hexdigest()
            ), entry["path"]
        assert {
            skip["path"] for skip in manifest["skipped"]
        } == set(EXPECTED_SKIPPED)
        assert all(
            skip["reason"] == "gate-false"
            for skip in manifest["skipped"]
        )
        recorded_paths = {
            record["path"] for record in manifest["recorded"]
        }
        assert (
            "gitops/platform/search/dashboards/alerts/"
            "platform_health_rules.ndjson" in recorded_paths
        )
        assert (
            "gitops/platform/search/opensearch/security/roles/"
            "team_env_isolation_roles.yaml" in recorded_paths
        )
        # Recorded files are never rewritten.
        for record in manifest["recorded"]:
            assert (
                (repo / record["path"]).read_bytes()
                == (FIXTURE_REPO / record["path"]).read_bytes()
            ), record["path"]

        # Prepared commit message: subject and required trailers.
        message = (repo / "COMMIT_MSG.txt").read_text()
        lines = message.splitlines()
        digest_hex = expected_digest.split(":", 1)[1]
        assert lines[0] == (
            "config(render): propagate unified configuration "
            + digest_hex[:12]
        )
        assert "Unified-Config-Schema-Version: v1" in lines
        assert (
            f"Unified-Config-Document-Digest: {expected_digest}"
            in lines
        )


def test_rerender_is_byte_identical_and_check_flags_diffs() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        repo = _fresh_repo(Path(workdir))
        # Fresh tree: --check must report changes (exit 3 analogue).
        plan = plan_render(DOCUMENT, CONTRACTS, repo)
        assert changed_paths(plan, repo)

        _render(repo)
        first = _tree_digests(repo)
        _render(repo)
        second = _tree_digests(repo)
        assert first == second, "re-render changed rendered bytes"

        # Rendered tree: --check finds nothing to change.
        plan = plan_render(DOCUMENT, CONTRACTS, repo)
        assert changed_paths(plan, repo) == ()


def test_determinism_across_directories() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo_a = base / "a" / "repo"
        repo_b = base / "b" / "repo"
        shutil.copytree(FIXTURE_REPO, repo_a)
        shutil.copytree(FIXTURE_REPO, repo_b)
        _render(repo_a)
        _render(repo_b)
        diff = subprocess.run(
            ["diff", "-r", str(repo_a), str(repo_b)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert diff.returncode == 0, diff.stdout + diff.stderr


def test_cli_render_matches_library_and_check_exit_codes() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo_cli = base / "cli" / "repo"
        repo_lib = base / "lib" / "repo"
        shutil.copytree(FIXTURE_REPO, repo_cli)
        shutil.copytree(FIXTURE_REPO, repo_lib)

        argv = [
            "render",
            "--document",
            str(DOCUMENT),
            "--contracts-dir",
            str(CONTRACTS),
            "--repo-root",
            str(repo_cli),
            "--commit-message-out",
            str(repo_cli / "COMMIT_MSG.txt"),
        ]
        fresh_check = _cli([*argv, "--check"], cwd=base)
        assert fresh_check.returncode == 3, fresh_check.stdout
        assert "would change:" in fresh_check.stdout

        rendered = _cli(argv, cwd=base)
        assert rendered.returncode == 0, rendered.stderr
        _render(repo_lib)
        assert _tree_digests(repo_cli) == _tree_digests(repo_lib)

        clean_check = _cli([*argv, "--check"], cwd=base)
        assert clean_check.returncode == 0, clean_check.stdout
        assert "no diff, no commit" in clean_check.stdout


def test_rejection_fixtures_fail_with_exit_2_and_no_writes() -> None:
    rejections = (
        "document_unbound_key.json",
        "document_unknown_system.json",
        "document_outside_surface.json",
        # render_target containment (TR-20 write scope): traversal
        # segments and targets outside the binding system's registered
        # config surface are rejected before any write.
        "document_traversal_render_target.json",
        "document_out_of_surface_render_target.json",
    )
    for name in rejections:
        with tempfile.TemporaryDirectory() as workdir:
            base = Path(workdir)
            repo = _fresh_repo(base)
            before = _tree_digests(repo)
            result = _cli(
                [
                    "render",
                    "--document",
                    str(FIXTURES / name),
                    "--contracts-dir",
                    str(CONTRACTS),
                    "--repo-root",
                    str(repo),
                    "--commit-message-out",
                    str(repo / "COMMIT_MSG.txt"),
                ],
                cwd=base,
            )
            assert result.returncode == 2, (name, result.stderr)
            assert "cross-file rule violation" in result.stderr, name
            if name == "document_traversal_render_target.json":
                assert "'.' or '..' path segments" in result.stderr
            if name == "document_out_of_surface_render_target.json":
                assert (
                    "render_target 'gitops/apps/rogue.yaml' is "
                    "outside every registered config_surface"
                    in result.stderr
                )
            assert _tree_digests(repo) == before, (
                f"{name} wrote into the tree"
            )


def test_yaml_document_is_rejected_with_conversion_hint() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        result = _cli(
            [
                "render",
                "--document",
                str(
                    CONTRACTS
                    / "management/samples/VALID_UNIFIED_CONFIG.yaml"
                ),
                "--contracts-dir",
                str(CONTRACTS),
                "--repo-root",
                str(repo),
            ],
            cwd=base,
        )
        assert result.returncode == 2
        assert "JSON" in result.stderr
        assert "VALID_UNIFIED_CONFIG.json" in result.stderr


def test_presence_gated_renders_when_graph_enabled() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        document = json.loads(DOCUMENT.read_text())
        document["config"]["graph"]["enabled"] = True
        document["config"]["graph"]["browser_access_enabled"] = True
        enabled_doc = base / "document_graph_enabled.json"
        enabled_doc.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _render(repo, enabled_doc)
        for path in EXPECTED_SKIPPED:
            text = (repo / path).read_text()
            assert text.split("\n", 1)[0] == MARKER_COMMENT, path
            # Adoption only: original content preserved below marker.
            assert (
                text.split("\n", 1)[1]
                == (FIXTURE_REPO / path).read_text()
            ), path
        manifest = json.loads((repo / MANIFEST_NAME).read_text())
        assert manifest["skipped"] == []
        graph = (
            repo
            / "gitops/platform/observability/values/"
            "graph-pipeline.yaml"
        ).read_text()
        assert "  enabled: true\n" in graph


def test_json_twin_sample_matches_yaml_semantics() -> None:
    twin = json.loads(
        (
            CONTRACTS
            / "management/samples/VALID_UNIFIED_CONFIG.json"
        ).read_text()
    )
    assert twin["schema_version"] == "v1"
    assert len(twin["bindings"]) == 14
    assert twin == json.loads(DOCUMENT.read_text())


def test_drift_and_rollback_require_document() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        for command in ("drift", "rollback"):
            result = _cli([command], cwd=base)
            assert result.returncode == 2, command
            assert "--document is required" in result.stderr


def test_bounded_patcher_fails_loudly_on_unsupported_yaml() -> None:
    # ADR-0003 / renderer architecture contract:
    # bounded_structural_subset is fail-loudly-on-unsupported-
    # structure. Each shape below must raise instead of being
    # silently corrupted by the line-based scalar patcher.
    unsupported = (
        # Block scalar: replacing the header would orphan the body.
        ("block scalar", "k: |\n  body line\n", "k"),
        ("folded scalar", "k: >-\n  body line\n", "k"),
        # Anchor with a live alias elsewhere: replacement would
        # silently delete the anchor and dangle the alias.
        ("anchor", "k: &anch hello\nm: *anch\n", "k"),
        # Alias value.
        ("alias", "k: &anch hello\nm: *anch\n", "m"),
        # Quoted scalar containing '#': line-based comment splitting
        # would corrupt the quoting.
        ("quoted with hash", 'k: "x#y"\n', "k"),
        ("single-quoted", "k: 'x'\n", "k"),
        # Flow collections.
        ("flow mapping", "k: {x: 1}\n", "k"),
        ("flow sequence", "k: [1, 2]\n", "k"),
        # Duplicate keys at one level: first-match patching would
        # guess which one the locator means.
        ("duplicate key", "k: 1\nk: 2\n", "k"),
        # CRLF line endings would end up mixed with LF.
        ("crlf", "k: 1\r\n", "k"),
    )
    for label, text, dotted in unsupported:
        try:
            set_yaml_scalar(text, dotted, "9", f"test[{label}]")
        except ConfigRenderError:
            continue
        raise AssertionError(
            f"{label}: bounded patcher silently accepted "
            "unsupported YAML structure"
        )
    # Control: a plain scalar with a trailing comment still patches.
    patched = set_yaml_scalar(
        "k: 1  # keep me\n", "k", "9", "test[plain]"
    )
    assert patched == "k: 9  # keep me\n"


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"{len(tests)} configrender test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
