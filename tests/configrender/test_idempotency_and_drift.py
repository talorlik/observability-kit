"""Offline tests for render idempotency and drift detection (Batch 19
Task 3).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 19 validator - never under pytest. Every run
happens in a temp copy of tests/configrender/fixtures/repo/; the
repository's own gitops/ tree is never touched.

Covers the Task 3 completion check:

- render-idempotency check: `obskit render --check` on an unchanged
  document proves a no-diff, no-commit result (exit 0), and a
  re-render changes zero bytes;
- `obskit drift` emits the rendered-versus-live diff surface consumed
  by the TR-12 drift alert path, with the propagation contract's
  signal names (render-idempotency-violation for hand-edited rendered
  state and the manifest, config-drift-detected-per-system for every
  other divergence), byte-deterministically, read-only over the
  target tree, exit 0 clean / 3 drift / 2 operator error.
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

from obskit.configrender.drift import (  # noqa: E402
    ABSENT,
    DriftReport,
    SIGNAL_CONFIG_DRIFT,
    SIGNAL_IDEMPOTENCY_VIOLATION,
    STATUS_CLEAN,
    STATUS_DRIFT,
    compute_drift,
)
from obskit.configrender.models import (  # noqa: E402
    DEFAULT_MANIFEST_RELPATH,
)
from obskit.configrender.render import (  # noqa: E402
    execute_plan,
    plan_render,
)

# The exact top-level key set of the drift report JSON; the Task 5
# validator consumes this surface.
REPORT_TOP_LEVEL_KEYS = {
    "status",
    "document_digest",
    "schema_version",
    "drifted",
    "systems",
}
ENTRY_KEYS = {
    "path",
    "system",
    "unified_key",
    "expected_digest",
    "actual_digest",
    "signal",
}

GRAFANA_VALUES = (
    "gitops/platform/observability/grafana/values/"
    "grafana-values.yaml"
)
OWNED_DESTINATIONS = (
    "gitops/platform/search/dashboards/alerts/"
    "notification_destinations.json"
)
ILM_LOGS_POLICY = (
    "gitops/platform/search/opensearch/ilm/logs-ilm-policy.json"
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
    execute_plan(plan, repo)


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


def _drift_argv(repo: Path) -> list[str]:
    return [
        "drift",
        "--document",
        str(DOCUMENT),
        "--contracts-dir",
        str(CONTRACTS),
        "--repo-root",
        str(repo),
    ]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_render_check_proves_no_diff_no_commit() -> None:
    """Completion check, idempotency clause: re-rendering an unchanged
    document is a no-diff, no-commit result."""
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        argv = [
            "render",
            "--document",
            str(DOCUMENT),
            "--contracts-dir",
            str(CONTRACTS),
            "--repo-root",
            str(repo),
        ]
        rendered = _cli(argv, cwd=base)
        assert rendered.returncode == 0, rendered.stderr

        check = _cli([*argv, "--check"], cwd=base)
        assert check.returncode == 0, check.stdout + check.stderr
        assert "no diff, no commit" in check.stdout

        # The re-render itself changes zero bytes in the tree.
        before = _tree_digests(repo)
        rerendered = _cli(argv, cwd=base)
        assert rerendered.returncode == 0, rerendered.stderr
        assert _tree_digests(repo) == before, (
            "re-render of an unchanged document changed bytes"
        )


def test_drift_clean_after_render() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo)

        report = compute_drift(DOCUMENT, CONTRACTS, repo)
        assert isinstance(report, DriftReport)
        assert report.status == STATUS_CLEAN
        assert report.drifted == ()
        assert report.systems == ()

        result = _cli(_drift_argv(repo), cwd=base)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert set(payload) == REPORT_TOP_LEVEL_KEYS
        assert payload["status"] == STATUS_CLEAN
        assert payload["drifted"] == []
        assert payload["systems"] == []
        assert payload["schema_version"] == "v1"
        expected_digest = "sha256:" + hashlib.sha256(
            DOCUMENT.read_bytes()
        ).hexdigest()
        assert payload["document_digest"] == expected_digest


def test_drift_hand_edit_is_idempotency_violation() -> None:
    """A rendered target edited by hand (marker intact) surfaces as
    render-idempotency-violation with correct digests."""
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo)
        target = repo / GRAFANA_VALUES
        expected_digest = _sha256_file(target)
        original = target.read_text(encoding="utf-8")
        assert "    cookie_secure: true\n" in original
        edited = original.replace(
            "    cookie_secure: true\n",
            "    cookie_secure: false\n",
        )
        target.write_text(edited, encoding="utf-8")
        before = _tree_digests(repo)

        result = _cli(_drift_argv(repo), cwd=base)
        assert result.returncode == 3, result.stdout + result.stderr
        # Drift is read-only: the tree is untouched.
        assert _tree_digests(repo) == before

        payload = json.loads(result.stdout)
        assert payload["status"] == STATUS_DRIFT
        assert len(payload["drifted"]) == 1
        entry = payload["drifted"][0]
        assert set(entry) == ENTRY_KEYS
        assert entry["path"] == GRAFANA_VALUES
        assert entry["signal"] == SIGNAL_IDEMPOTENCY_VIOLATION
        assert entry["system"] == "grafana"
        assert entry["expected_digest"] == expected_digest
        assert entry["actual_digest"] == _sha256_file(target)
        assert payload["systems"] == ["grafana"]


def test_drift_missing_owned_artifact_reports_absent() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo)
        (repo / OWNED_DESTINATIONS).unlink()

        result = _cli(_drift_argv(repo), cwd=base)
        assert result.returncode == 3, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == STATUS_DRIFT
        entries = {
            entry["path"]: entry for entry in payload["drifted"]
        }
        assert OWNED_DESTINATIONS in entries
        entry = entries[OWNED_DESTINATIONS]
        assert entry["actual_digest"] == ABSENT
        assert entry["signal"] == SIGNAL_CONFIG_DRIFT


def test_drift_never_rendered_tree_is_config_drift_per_system() -> (
    None
):
    """Files that exist without ever carrying the marker (and files
    the renderer expects but are absent) are per-system config drift,
    not idempotency violations."""
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)  # deliberately NOT rendered

        result = _cli(_drift_argv(repo), cwd=base)
        assert result.returncode == 3, result.stdout + result.stderr
        payload = json.loads(result.stdout)
        assert payload["status"] == STATUS_DRIFT
        entries = {
            entry["path"]: entry for entry in payload["drifted"]
        }
        assert ILM_LOGS_POLICY in entries
        assert (
            entries[ILM_LOGS_POLICY]["signal"] == SIGNAL_CONFIG_DRIFT
        )
        assert entries[ILM_LOGS_POLICY]["system"] == "opensearch"
        # No fixture file carries the marker, so nothing on this tree
        # can be an idempotency violation.
        assert all(
            entry["signal"] == SIGNAL_CONFIG_DRIFT
            for entry in payload["drifted"]
        )
        # The absent manifest is itself part of the drift surface.
        assert DEFAULT_MANIFEST_RELPATH in entries
        assert entries[DEFAULT_MANIFEST_RELPATH][
            "actual_digest"
        ] == ABSENT
        # The drifted list is path-sorted and the systems summary is
        # the sorted unique system set.
        paths = [entry["path"] for entry in payload["drifted"]]
        assert paths == sorted(paths)
        assert payload["systems"] == sorted(
            {entry["system"] for entry in payload["drifted"]}
        )
        assert "opensearch" in payload["systems"]


def test_drift_report_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)  # never-rendered: non-trivial report
        first = _cli(_drift_argv(repo), cwd=base)
        second = _cli(_drift_argv(repo), cwd=base)
        assert first.returncode == second.returncode == 3
        assert first.stdout == second.stdout, (
            "two drift runs over the same tree differ"
        )
        # Library and CLI agree byte-for-byte.
        report = compute_drift(DOCUMENT, CONTRACTS, repo)
        assert report.to_json() == first.stdout


def test_cli_drift_report_out_writes_contained_copy() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo)
        report_path = repo / "reports" / "drift_report.json"
        result = _cli(
            [
                *_drift_argv(repo),
                "--report-out",
                str(report_path),
            ],
            cwd=base,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert report_path.is_file()
        content = report_path.read_text(encoding="utf-8")
        assert content == result.stdout
        assert content.endswith("\n")

        # Containment mirrors render --manifest-out: a report path
        # resolving outside the target tree is refused (exit 2) and
        # nothing is written.
        escape = base / "escape" / "drift_report.json"
        refused = _cli(
            [
                *_drift_argv(repo),
                "--report-out",
                str(escape),
            ],
            cwd=base,
        )
        assert refused.returncode == 2, refused.stdout
        assert "resolves outside" in refused.stderr
        assert not escape.exists()


def test_drift_operator_errors_exit_2() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        # Missing --document is an operator error.
        result = _cli(["drift", "--repo-root", str(repo)], cwd=base)
        assert result.returncode == 2, result.stdout
        assert "--document is required" in result.stderr
        # An invalid document fails exactly as `obskit render` would,
        # with nothing written.
        before = _tree_digests(repo)
        result = _cli(
            [
                "drift",
                "--document",
                str(FIXTURES / "document_unknown_system.json"),
                "--contracts-dir",
                str(CONTRACTS),
                "--repo-root",
                str(repo),
            ],
            cwd=base,
        )
        assert result.returncode == 2, result.stdout
        assert "obskit drift: error:" in result.stderr
        assert _tree_digests(repo) == before


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"{len(tests)} idempotency/drift test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
