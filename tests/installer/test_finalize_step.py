"""Tests for the guided installer finalization step (Batch 18 Task 4).

Plain python3, no pytest, invoked by
scripts/ci/validate_guided_installer.sh with PYTHONPATH=tools/obskit.
Offline: readiness runs the repository validation script against the
declared scaffold; the failure path uses a stubbed script in a temp
repo root.
"""

from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

from obskit.install.finalize import READINESS_SCRIPT, run_readiness
from obskit.install.models import (
    INSTALL_SUMMARY_FILENAME,
    STATUS_COMPLETED,
    STATUS_FAILED,
    InstallAnswers,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _answers() -> InstallAnswers:
    payload = json.loads(
        (FIXTURES / "render_answers_standalone.json").read_text(
            encoding="utf-8"
        )
    )
    return InstallAnswers.from_mapping(payload)


def _failing_repo_root(tmp: Path) -> Path:
    """A minimal repo root whose readiness script always fails."""
    script = tmp / READINESS_SCRIPT
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "echo 'seeded readiness failure' >&2\n"
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return tmp


def test_readiness_pass_emits_summary_and_completed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        output_dir = Path(tmp)
        result = run_readiness(_answers(), output_dir, REPO_ROOT)
        assert result.status == STATUS_COMPLETED
        assert result.outputs == (INSTALL_SUMMARY_FILENAME,)
        summary = json.loads(
            (output_dir / INSTALL_SUMMARY_FILENAME).read_text(
                encoding="utf-8"
            )
        )
        assert summary["readiness"]["passed"] is True
        assert summary["readiness"]["exit_code"] == 0
        # The summary lists the validated readiness sections.
        sections = summary["readiness"]["sections"]
        assert len(sections) >= 3
        for section in sections:
            assert section["id"]
            assert section["status"] in {"pending", "pass", "fail"}
        # Next steps are present and answer-derived.
        steps = summary["next_steps"]
        assert steps, "summary must list next steps"
        joined = "\n".join(steps)
        answers = _answers()
        assert answers.gitops_path in joined
        assert answers.gitops_repo_url in joined


def test_readiness_failure_returns_failed_result() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = _failing_repo_root(Path(tmp) / "repo")
        output_dir = Path(tmp) / "out"
        output_dir.mkdir()
        result = run_readiness(_answers(), output_dir, root)
        assert result.status == STATUS_FAILED
        assert "seeded readiness failure" in result.detail
        # The summary is still emitted for debugging, marked failed.
        summary = json.loads(
            (output_dir / INSTALL_SUMMARY_FILENAME).read_text(
                encoding="utf-8"
            )
        )
        assert summary["readiness"]["passed"] is False
        assert summary["readiness"]["exit_code"] == 1


def test_summary_emission_is_deterministic() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        first_dir = Path(tmp) / "first"
        second_dir = Path(tmp) / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        run_readiness(_answers(), first_dir, REPO_ROOT)
        run_readiness(_answers(), second_dir, REPO_ROOT)
        first = (first_dir / INSTALL_SUMMARY_FILENAME).read_bytes()
        second = (second_dir / INSTALL_SUMMARY_FILENAME).read_bytes()
        assert first == second


def test_missing_readiness_script_raises_clean_error() -> None:
    from obskit.install.models import InstallFlowError

    with tempfile.TemporaryDirectory() as tmp:
        try:
            run_readiness(_answers(), Path(tmp), Path(tmp) / "nowhere")
        except InstallFlowError as exc:
            assert "readiness script not found" in str(exc)
        else:
            raise AssertionError(
                "missing readiness script must raise InstallFlowError"
            )


def main() -> None:
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            function()
            print(f"{name} passed")


if __name__ == "__main__":
    main()
