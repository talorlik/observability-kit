"""Finalization step of the guided installer (Batch 18 Task 4, TR-19).

Implements the contracted ``post-install-readiness`` step: invoke
scripts/validate/post_install_readiness.sh (evidence-based readiness,
per ADR-0002 - the one subprocess call the installer makes; it runs a
repository validation script, never a cluster mutation) and emit the
install summary listing readiness results and next steps. A failed
readiness check surfaces as a failed StepResult, which the flow engine
turns into a non-zero installer exit code.

The readiness sections listed in the summary come from the readiness
report the script validates. Today that is the declared scaffold
(contracts/discovery/READINESS_REPORT_SCAFFOLD.json); Batch 23
replaces declared fixtures with captured live evidence through this
same step.

Determinism: install_summary.json is emitted via
obskit.emit.write_report and derives only from the answers, the
readiness report, and fixed text - no timestamps, no raw subprocess
output in the artifact.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from obskit.emit import write_report
from obskit.install.models import (
    INSTALL_SUMMARY_FILENAME,
    RENDERED_DIRNAME,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STEP_READINESS,
    InstallAnswers,
    InstallFlowError,
    StepResult,
)
from obskit.models import REPORT_VERSION

READINESS_SCRIPT = "scripts/validate/post_install_readiness.sh"
READINESS_REPORT = "contracts/discovery/READINESS_REPORT_SCAFFOLD.json"

GENERATED_BY = "obskit"


def _load_readiness_sections(
    repo_root: Path,
) -> list[dict[str, str]]:
    """Load the readiness sections the readiness script validated.

    Returns one {id, description, status} entry per section, in the
    report's own order (the report is the ordering authority).
    """
    report_path = repo_root / READINESS_REPORT
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InstallFlowError(
            f"readiness report unreadable: {report_path}: {exc}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise InstallFlowError(
            f"readiness report malformed: {report_path}: {exc}"
        ) from exc
    sections = payload.get("readiness_sections")
    if not isinstance(sections, list):
        raise InstallFlowError(
            "readiness report missing readiness_sections: "
            f"{report_path}"
        )
    shaped: list[dict[str, str]] = []
    for section in sections:
        if not isinstance(section, dict):
            raise InstallFlowError(
                "readiness report section is not an object: "
                f"{report_path}"
            )
        shaped.append(
            {
                "id": str(section.get("id", "")),
                "description": str(section.get("description", "")),
                "status": str(section.get("status", "")),
            }
        )
    return shaped


def _next_steps(answers: InstallAnswers) -> list[str]:
    """Fixed, answer-derived next steps for the install summary."""
    return [
        (
            "Commit the contents of the rendered/ directory into "
            f"'{answers.gitops_path}/' of {answers.gitops_repo_url} "
            "and let the Argo CD controller reconcile it."
        ),
        (
            "Verify application health in the Argo CD UI and the "
            "platform dashboards for the "
            f"'{answers.environment}' environment."
        ),
        (
            "Onboard workloads per "
            "docs/runbooks/ONBOARDING_SUBSCRIPTION_OPERATOR_GUIDE.md."
        ),
        (
            "For day-2 operations see "
            "docs/runbooks/GUIDED_INSTALLATION_GUIDE.md."
        ),
    ]


def run_readiness(
    answers: InstallAnswers, output_dir: Path, repo_root: Path
) -> StepResult:
    """Run post-install readiness and emit the install summary.

    Invokes scripts/validate/post_install_readiness.sh from
    repo_root, shapes its outcome plus the validated readiness
    sections into install_summary.json, prints a human-readable
    summary, and returns a StepResult whose status reflects the
    readiness exit code (failed readiness -> failed StepResult -> the
    flow engine exits non-zero).
    """
    script_path = repo_root / READINESS_SCRIPT
    if not script_path.is_file():
        raise InstallFlowError(
            f"readiness script not found: {script_path}; pass "
            "--repo-root pointing at an Observability Kit checkout"
        )
    completed = subprocess.run(  # noqa: S603 - fixed repo script
        ["bash", READINESS_SCRIPT],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    passed = completed.returncode == 0
    sections = _load_readiness_sections(repo_root) if passed else []
    summary: dict[str, Any] = {
        "metadata": {
            "version": REPORT_VERSION,
            "generated_by": GENERATED_BY,
            "cluster_name": answers.cluster_name,
            "environment": answers.environment,
        },
        "readiness": {
            "passed": passed,
            "script": READINESS_SCRIPT,
            "exit_code": completed.returncode,
            "sections": sections,
        },
        "next_steps": _next_steps(answers),
        "rendered_output_dir": RENDERED_DIRNAME,
    }
    write_report(summary, str(output_dir / INSTALL_SUMMARY_FILENAME))
    _print_summary(summary)
    if not passed:
        detail = (
            f"{READINESS_SCRIPT} exited "
            f"{completed.returncode}: "
            + (completed.stderr.strip() or completed.stdout.strip())
        )
        return StepResult(
            step_id=STEP_READINESS,
            status=STATUS_FAILED,
            outputs=(INSTALL_SUMMARY_FILENAME,),
            detail=detail,
        )
    return StepResult(
        step_id=STEP_READINESS,
        status=STATUS_COMPLETED,
        outputs=(INSTALL_SUMMARY_FILENAME,),
        detail="post-install readiness passed",
    )


def _print_summary(summary: dict[str, Any]) -> None:
    """Print the human-readable install summary to stdout."""
    readiness = summary["readiness"]
    state = "PASSED" if readiness["passed"] else "FAILED"
    lines = [
        "install summary "
        f"({summary['metadata']['cluster_name']} / "
        f"{summary['metadata']['environment']}):",
        f"  readiness: {state} ({readiness['script']})",
    ]
    for section in readiness["sections"]:
        lines.append(
            f"    - {section['id']}: {section['status']}"
            + (
                f" ({section['description']})"
                if section["description"]
                else ""
            )
        )
    lines.append("  next steps:")
    for index, step in enumerate(summary["next_steps"], start=1):
        lines.append(f"    {index}. {step}")
    sys.stdout.write("\n".join(lines) + "\n")
