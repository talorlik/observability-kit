#!/usr/bin/env python3
"""Offline fixture-driven tests for `obskit preflight` (Batch 17, TR-18).

Covers the contracted check-class surface: all six check classes are
emitted in stable order, statuses match the recorded fixtures, summary
arithmetic is internally consistent, and the process exit code follows
the pass/warn=0, fail=1 contract. The CLI is exercised through
subprocess so the argparse wiring and stdout/file emission paths are
both under test.

Owned by scripts/ci/validate_discovery_executor.sh; run it via that
validator (PYTHONPATH=tools/obskit), not under pytest.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "executor" / "fixtures"

# Contracted emission order: connectivity gates the rest, then the five
# gated check classes in the order preflight.py declares them.
EXPECTED_CHECK_ORDER = [
    "cluster_connectivity",
    "required_permissions",
    "required_api_readiness",
    "required_crd_readiness",
    "storage_compatibility",
    "gitops_prerequisites",
]

# The fail fixture is frozen; its per-check statuses are part of the
# recorded expectation (connectivity holds, everything gated degrades).
EXPECTED_FAIL_STATUSES = {
    "cluster_connectivity": "pass",
    "required_permissions": "fail",
    "required_api_readiness": "fail",
    "required_crd_readiness": "fail",
    "storage_compatibility": "fail",
    "gitops_prerequisites": "warn",
}


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "tools" / "obskit")
    return env


def run_preflight(snapshot: Path) -> tuple[int, dict]:
    """Run `obskit preflight` on a snapshot; return (exit code, report)."""
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "preflight_report.json"
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "obskit.cli",
                "preflight",
                "--snapshot",
                str(snapshot),
                "--output",
                str(out_path),
            ],
            cwd=ROOT,
            env=_cli_env(),
            capture_output=True,
            text=True,
        )
        assert out_path.is_file(), (
            f"preflight wrote no report; stderr: {proc.stderr}"
        )
        return proc.returncode, json.loads(out_path.read_text())


def _assert_summary_arithmetic(report: dict) -> None:
    checks = report["checks"]
    summary = report["summary"]
    counted = {
        status: sum(1 for item in checks if item["status"] == status)
        for status in ("pass", "warn", "fail", "skip")
    }
    assert summary["total_checks"] == len(checks), summary
    for status, count in counted.items():
        assert summary[status] == count, (status, summary, counted)
    if counted["fail"] > 0:
        expected_outcome = "fail"
    elif counted["warn"] > 0:
        expected_outcome = "warn"
    else:
        expected_outcome = "pass"
    assert summary["outcome"] == expected_outcome, summary


def test_pass_fixture_all_checks_pass_exit_zero() -> None:
    code, report = run_preflight(FIXTURES / "snapshot_preflight_pass.json")
    assert code == 0, f"expected exit 0 on passing snapshot, got {code}"
    ids = [item["id"] for item in report["checks"]]
    assert ids == EXPECTED_CHECK_ORDER, ids
    statuses = {item["id"]: item["status"] for item in report["checks"]}
    assert all(status == "pass" for status in statuses.values()), statuses
    assert report["summary"]["outcome"] == "pass"
    _assert_summary_arithmetic(report)


def test_fail_fixture_statuses_and_exit_one() -> None:
    code, report = run_preflight(FIXTURES / "snapshot_preflight_fail.json")
    assert code == 1, f"expected exit 1 on failing snapshot, got {code}"
    ids = [item["id"] for item in report["checks"]]
    assert ids == EXPECTED_CHECK_ORDER, ids
    statuses = {item["id"]: item["status"] for item in report["checks"]}
    assert statuses == EXPECTED_FAIL_STATUSES, statuses
    assert report["summary"]["outcome"] == "fail"
    _assert_summary_arithmetic(report)


def test_default_output_is_stdout() -> None:
    proc = subprocess.run(
        [
            "python3",
            "-m",
            "obskit.cli",
            "preflight",
            "--snapshot",
            str(FIXTURES / "snapshot_preflight_pass.json"),
        ],
        cwd=ROOT,
        env=_cli_env(),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert [item["id"] for item in report["checks"]] == EXPECTED_CHECK_ORDER


def test_operator_errors_are_clean_not_tracebacks() -> None:
    """Expected input errors print one clean line and exit 1."""
    cases = [
        str(FIXTURES / "does_not_exist.json"),
    ]
    with tempfile.TemporaryDirectory() as tmp:
        malformed = Path(tmp) / "malformed.json"
        malformed.write_text("{not json")
        clusterless = Path(tmp) / "clusterless.json"
        clusterless.write_text("{}")
        cases.extend([str(malformed), str(clusterless)])
        for snapshot in cases:
            proc = subprocess.run(
                ["python3", "-m", "obskit.cli", "preflight",
                 "--snapshot", snapshot],
                cwd=ROOT,
                env=_cli_env(),
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 1, (snapshot, proc.returncode)
            assert "Traceback" not in proc.stderr, (snapshot, proc.stderr)
            assert "obskit preflight: error:" in proc.stderr, proc.stderr


def test_failing_reader_accessor_yields_report_not_crash() -> None:
    """A reader accessor raising mid-check (live-mode partial RBAC)
    still produces a schema-valid report with check_execution_error."""
    import sys

    sys.path.insert(0, str(ROOT / "tools" / "obskit"))
    from obskit.preflight import evaluate_preflight
    from obskit.reader import FixtureReader

    class _DenyingReader(FixtureReader):
        def crd_names(self) -> tuple[str, ...]:
            raise RuntimeError("simulated live API denial (403)")

    reader = _DenyingReader(FIXTURES / "snapshot_preflight_pass.json")
    report = evaluate_preflight(reader)
    by_id = {c["id"]: c for c in report["checks"]}
    crd = by_id["required_crd_readiness"]
    assert crd["status"] == "fail", crd
    assert crd["reason_code"] == "check_execution_error", crd
    assert report["summary"]["outcome"] == "fail"
    # Untouched checks still evaluate normally.
    assert by_id["required_permissions"]["status"] == "pass"


if __name__ == "__main__":
    test_pass_fixture_all_checks_pass_exit_zero()
    print("test_pass_fixture_all_checks_pass_exit_zero passed")
    test_fail_fixture_statuses_and_exit_one()
    print("test_fail_fixture_statuses_and_exit_one passed")
    test_default_output_is_stdout()
    print("test_default_output_is_stdout passed")
    test_operator_errors_are_clean_not_tracebacks()
    print("test_operator_errors_are_clean_not_tracebacks passed")
    test_failing_reader_accessor_yields_report_not_crash()
    print("test_failing_reader_accessor_yields_report_not_crash passed")
