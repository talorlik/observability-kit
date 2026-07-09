"""Offline tests for `obskit rollback` (Batch 19 Task 4).

Plain python3 script with test_* functions and bare asserts, invoked
directly by the Batch 19 validator - never under pytest. Every
rollback happens in a temp copy of tests/configrender/fixtures/repo/;
the repository's own gitops/ tree is never touched.

Covers the Task 4 completion check: rollback re-renders a prior
unified document revision through the identical render-and-commit
pipeline (same rendered bytes, same commit message with the required
trailers), never a separate apply channel; dry-run is the default
mode and writes nothing; the deterministic digest-equality proof
(--expected-manifest) refuses to proceed on mismatch; and the
mode-parameterized ops drill wrapper passes end to end in both modes.
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
DRILL = REPO_ROOT / "scripts" / "ops" / "run_config_rollback_drill.sh"

sys.path.insert(0, str(PKG_ROOT))

from obskit.configrender.models import (  # noqa: E402
    DEFAULT_MANIFEST_RELPATH,
)
from obskit.configrender.render import (  # noqa: E402
    execute_plan,
    plan_render,
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


def _modified_document(base: Path) -> Path:
    """The intervening revision rollback undoes: logs_days changed."""
    document = json.loads(DOCUMENT.read_text())
    document["config"]["retention"]["logs_days"] = 7
    target = base / "document_modified_retention.json"
    target.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


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


def _rollback_argv(repo: Path) -> list[str]:
    return [
        "rollback",
        "--document",
        str(DOCUMENT),
        "--contracts-dir",
        str(CONTRACTS),
        "--repo-root",
        str(repo),
    ]


def test_dry_run_is_default_plans_only_and_writes_nothing() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo, _modified_document(base))
        before = _tree_digests(repo)

        # No --mode flag: dry-run must be the default.
        result = _cli(_rollback_argv(repo), cwd=base)
        assert result.returncode == 0, result.stderr
        assert _tree_digests(repo) == before, (
            "dry-run rollback wrote into the tree"
        )

        report = json.loads(result.stdout)
        assert report["mode"] == "dry-run"
        assert report["status"] == "planned"
        assert report["deterministic_proof"] == "not-requested"
        assert report["schema_version"] == "v1"
        expected_digest = "sha256:" + hashlib.sha256(
            DOCUMENT.read_bytes()
        ).hexdigest()
        assert report["document_digest"] == expected_digest
        would_change = report["would_change"]
        assert would_change == sorted(would_change)
        # The intervening logs_days change must be planned back.
        assert (
            "gitops/platform/search/opensearch/ilm/"
            "logs-ilm-policy.json" in would_change
        )
        assert DEFAULT_MANIFEST_RELPATH in would_change


def test_real_mode_restores_original_bytes_same_pipeline() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        reference = base / "reference" / "repo"
        shutil.copytree(FIXTURE_REPO, reference)
        _render(reference)
        prior_manifest = base / "prior_manifest.json"
        shutil.copy(
            reference / DEFAULT_MANIFEST_RELPATH, prior_manifest
        )

        repo = _fresh_repo(base)
        _render(repo)
        _render(repo, _modified_document(base))
        assert _tree_digests(repo) != _tree_digests(reference)

        result = _cli(
            [
                *_rollback_argv(repo),
                "--mode",
                "real",
                "--expected-manifest",
                str(prior_manifest),
                "--commit-message-out",
                str(repo / "COMMIT_MSG.txt"),
            ],
            cwd=base,
        )
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["mode"] == "real"
        assert report["status"] == "rolled-back"
        assert report["deterministic_proof"] == "verified"
        assert report["changed"] == sorted(report["changed"])
        assert DEFAULT_MANIFEST_RELPATH in report["changed"]

        # Same pipeline, same bytes: the rolled-back tree (including
        # manifest and prepared commit message) equals the reference
        # render of the prior document, byte for byte.
        assert _tree_digests(repo) == _tree_digests(reference)
        diff = subprocess.run(
            ["diff", "-r", str(reference), str(repo)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert diff.returncode == 0, diff.stdout + diff.stderr


def test_expected_manifest_mismatch_refuses_both_modes() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        modified = _modified_document(base)
        _render(repo, modified)
        # Wrong revision on purpose: the manifest the MODIFIED
        # document committed can never prove a rollback to DOCUMENT.
        wrong_manifest = base / "wrong_manifest.json"
        shutil.copy(repo / DEFAULT_MANIFEST_RELPATH, wrong_manifest)
        before = _tree_digests(repo)

        for mode in ("dry-run", "real"):
            result = _cli(
                [
                    *_rollback_argv(repo),
                    "--mode",
                    mode,
                    "--expected-manifest",
                    str(wrong_manifest),
                ],
                cwd=base,
            )
            assert result.returncode == 2, (mode, result.stderr)
            assert (
                "deterministic rollback proof failed"
                in result.stderr
            ), (mode, result.stderr)
            assert result.stdout == "", mode
            assert _tree_digests(repo) == before, (
                f"{mode} mismatch wrote into the tree"
            )


def test_report_out_outside_repo_root_is_refused() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        before = _tree_digests(repo)
        escape = base / "escape_report.json"
        result = _cli(
            [
                *_rollback_argv(repo),
                "--mode",
                "real",
                "--report-out",
                str(escape),
            ],
            cwd=base,
        )
        assert result.returncode == 2, result.stderr
        assert "outside the repository root" in result.stderr
        assert not escape.exists()
        assert _tree_digests(repo) == before


def test_commit_message_carries_prior_document_trailers() -> None:
    with tempfile.TemporaryDirectory() as workdir:
        base = Path(workdir)
        repo = _fresh_repo(base)
        _render(repo, _modified_document(base))
        result = _cli(
            [
                *_rollback_argv(repo),
                "--mode",
                "real",
                "--commit-message-out",
                str(repo / "COMMIT_MSG.txt"),
            ],
            cwd=base,
        )
        assert result.returncode == 0, result.stderr
        lines = (repo / "COMMIT_MSG.txt").read_text().splitlines()
        prior_digest = "sha256:" + hashlib.sha256(
            DOCUMENT.read_bytes()
        ).hexdigest()
        assert "Unified-Config-Schema-Version: v1" in lines
        assert (
            f"Unified-Config-Document-Digest: {prior_digest}"
            in lines
        )


def test_drill_wrapper_passes_in_both_modes() -> None:
    env = dict(os.environ)
    env["ENVIRONMENT"] = "non-production"
    for argv, needle in (
        ([str(DRILL)], "dry-run passed"),
        ([str(DRILL), "real"], "drill passed"),
    ):
        result = subprocess.run(
            ["bash", *argv],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            argv,
            result.stdout,
            result.stderr,
        )
        assert needle in result.stdout, (argv, result.stdout)


def test_drill_refuses_real_mode_in_production() -> None:
    env = dict(os.environ)
    env["ENVIRONMENT"] = "production"
    result = subprocess.run(
        ["bash", str(DRILL), "real"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1, result.stdout
    assert "must not run in real mode in production" in result.stdout


def main() -> int:
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    for name, test in tests:
        test()
        print(f"PASS {name}")
    print(f"{len(tests)} rollback test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
