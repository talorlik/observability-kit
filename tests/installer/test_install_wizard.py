#!/usr/bin/env python3
"""Offline tests for the `obskit install` guided flow (Batch 18, TR-19).

Covers the Task 2 completion contract:

- a valid answers file drives the exact contracted step order end to
  end (render/finalize stubbed via sys.modules - those modules belong
  to parallel tasks and only their interface is exercised here);
- every seeded invalid answers fixture is rejected with a non-zero
  return before any render or bootstrap output exists;
- interactive capture (monkeypatched builtins.input) produces an
  answers.json byte-identical to the equivalent --answers run;
- re-running a completed install changes no file bytes or mtimes and
  exits 0; a corrupted step digest re-executes exactly that step; a
  failed run resumes from the first non-completed step;
- a tampered flow-contract step order raises InstallFlowError;
- the stdlib schema validator fails loudly on keywords it does not
  implement.

Owned by scripts/ci/validate_guided_installer.sh (Batch 18 Task 5).
Run: PYTHONPATH=tools/obskit python3 tests/installer/test_install_wizard.py
"""

import builtins
import contextlib
import io
import json
import sys
import tempfile
import types
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "installer" / "fixtures"
EXECUTOR_FIXTURES = ROOT / "tests" / "executor" / "fixtures"
CONTRACTS = ROOT / "contracts"

sys.path.insert(0, str(ROOT / "tools" / "obskit"))

from obskit.cli import build_parser  # noqa: E402
from obskit.emit import write_report  # noqa: E402
from obskit.install import contract as contract_module  # noqa: E402
from obskit.install import flow  # noqa: E402
from obskit.install.models import (  # noqa: E402
    GENERATED_FILE_HEADER,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STEP_ORDER,
    STEP_READINESS,
    STEP_RENDER,
    InstallFlowError,
    RenderResult,
    StepResult,
)

INVALID_FIXTURES = (
    "answers_invalid_missing_field.json",
    "answers_invalid_bad_mode.json",
    "answers_invalid_attach_without_services.json",
)

RENDERED_OUTPUTS = (
    "rendered/overlays/dev/platform-core-values.yaml",
    "rendered/bootstrap/argocd/kustomization.yaml",
    "rendered/bootstrap/argocd/platform-core-application.yaml",
)


def _merged_snapshot(workdir: Path) -> Path:
    """A snapshot whose chain grades non-blocked.

    Base: the Batch 17 preflight-pass fixture. The discovery-facing
    sections come from the discovery reference fixture (nginx ingress
    workload, external-secrets CRDs) and the distribution becomes
    kubeadm, because "kind" deliberately grades blocked by contract
    and the guided flow halts on a blocked grade.
    """
    base = json.loads(
        (EXECUTOR_FIXTURES / "snapshot_preflight_pass.json").read_text()
    )
    reference = json.loads(
        (
            EXECUTOR_FIXTURES / "snapshot_discovery_reference.json"
        ).read_text()
    )
    for key in (
        "crds",
        "storage_classes",
        "ingress_classes",
        "namespaces",
        "workloads",
        "services",
    ):
        base[key] = reference[key]
    base["cluster"]["distribution"] = "kubeadm"
    path = workdir / "snapshot.json"
    path.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n")
    return path


def _install_args(
    snapshot: Path, output_dir: Path, answers: Path | None = None
) -> Namespace:
    argv = [
        "install",
        "--snapshot",
        str(snapshot),
        "--output-dir",
        str(output_dir),
        "--contracts-dir",
        str(CONTRACTS),
        "--profiles",
        str(EXECUTOR_FIXTURES / "profiles_reference.json"),
        "--repo-root",
        str(ROOT),
    ]
    if answers is not None:
        argv += ["--answers", str(answers)]
    return build_parser().parse_args(argv)


@contextlib.contextmanager
def _stub_modules(render_calls=None, include_finalize=True):
    """Interface stubs for the render/finalize modules other tasks own.

    Injected into sys.modules so the flow's lazy imports resolve to
    the stubs whether or not the real modules exist yet. With
    include_finalize=False the finalize entry is a None sentinel,
    which forces the import to fail even once the real module lands.
    """
    render_mod = types.ModuleType("obskit.install.render")

    def render_overlay(answers, output_dir):
        rel = (
            "rendered/overlays/"
            f"{answers.environment}/platform-core-values.yaml"
        )
        target = output_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"# {GENERATED_FILE_HEADER}\n"
            f"# stub overlay for {answers.cluster_name}\n"
        )
        if render_calls is not None:
            render_calls.append("render_overlay")
        return RenderResult(files=(rel,))

    def render_bootstrap(answers, output_dir):
        rels = (
            "rendered/bootstrap/argocd/kustomization.yaml",
            "rendered/bootstrap/argocd/platform-core-application.yaml",
        )
        for rel in rels:
            target = output_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                f"# {GENERATED_FILE_HEADER}\n# stub bootstrap\n"
            )
        if render_calls is not None:
            render_calls.append("render_bootstrap")
        return RenderResult(files=rels)

    render_mod.render_overlay = render_overlay
    render_mod.render_bootstrap = render_bootstrap

    finalize_mod = types.ModuleType("obskit.install.finalize")

    def run_readiness(answers, output_dir, repo_root):
        write_report(
            {
                "cluster_name": answers.cluster_name,
                "summary": {"outcome": "pass"},
            },
            str(output_dir / "install_summary.json"),
        )
        return StepResult(
            step_id=STEP_READINESS,
            status=STATUS_COMPLETED,
            outputs=("install_summary.json",),
        )

    finalize_mod.run_readiness = run_readiness

    names = ("obskit.install.render", "obskit.install.finalize")
    saved = {name: sys.modules.get(name) for name in names}
    sys.modules["obskit.install.render"] = render_mod
    sys.modules["obskit.install.finalize"] = (
        finalize_mod if include_finalize else None
    )
    try:
        yield
    finally:
        for name in names:
            if saved[name] is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = saved[name]


@contextlib.contextmanager
def _record_execution(calls: list):
    """Wrap the step executors to record actual execution order."""
    original = dict(flow._EXECUTORS)

    def _wrap(step_id, fn):
        def wrapped(ctx):
            calls.append(step_id)
            return fn(ctx)

        return wrapped

    for step_id, fn in original.items():
        flow._EXECUTORS[step_id] = _wrap(step_id, fn)
    try:
        yield
    finally:
        flow._EXECUTORS.clear()
        flow._EXECUTORS.update(original)


def _tree_state(root: Path) -> dict:
    return {
        str(path.relative_to(root)): (
            path.stat().st_mtime_ns,
            path.read_bytes(),
        )
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_valid_answers_flow_executes_contracted_step_order() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        snapshot = _merged_snapshot(workdir)
        output_dir = workdir / "install"
        calls: list = []
        with _stub_modules(), _record_execution(calls):
            rc = flow.run(
                _install_args(
                    snapshot,
                    output_dir,
                    FIXTURES / "answers_valid.json",
                )
            )
        assert rc == 0
        assert calls == list(STEP_ORDER), calls

        for rel in (
            "preflight_report.json",
            "capability_matrix.json",
            "compatibility_result.json",
            "remediation_list.json",
            "mode_recommendation.json",
            "answers.json",
            "install_contract.json",
            *RENDERED_OUTPUTS,
            "install_summary.json",
            "install_state.json",
        ):
            assert (output_dir / rel).is_file(), f"missing {rel}"

        state = json.loads(
            (output_dir / "install_state.json").read_text()
        )
        assert set(state["steps"]) == set(STEP_ORDER)
        for step_id, record in state["steps"].items():
            assert record["status"] == STATUS_COMPLETED, step_id
            assert record["input_digest"], step_id
            assert record["outputs"], step_id

        fixture = json.loads(
            (FIXTURES / "answers_valid.json").read_text()
        )
        assert (
            json.loads((output_dir / "answers.json").read_text())
            == fixture
        )
        # The captured contract is the same canonical mapping.
        assert (output_dir / "install_contract.json").read_bytes() == (
            output_dir / "answers.json"
        ).read_bytes()


def test_invalid_answers_rejected_before_render() -> None:
    for fixture_name in INVALID_FIXTURES:
        with tempfile.TemporaryDirectory() as tmp:
            workdir = Path(tmp)
            snapshot = _merged_snapshot(workdir)
            output_dir = workdir / "install"
            render_calls: list = []
            stderr = io.StringIO()
            with _stub_modules(render_calls=render_calls):
                with contextlib.redirect_stderr(stderr):
                    rc = flow.run(
                        _install_args(
                            snapshot,
                            output_dir,
                            FIXTURES / fixture_name,
                        )
                    )
            assert rc != 0, fixture_name
            assert "obskit install: error:" in stderr.getvalue(), (
                fixture_name
            )
            # Nothing rendered, no contract captured.
            assert render_calls == [], fixture_name
            assert not (output_dir / "rendered").exists(), fixture_name
            assert not (output_dir / "answers.json").exists(), (
                fixture_name
            )
            assert not (
                output_dir / "install_contract.json"
            ).exists(), fixture_name
            state = json.loads(
                (output_dir / "install_state.json").read_text()
            )
            capture = state["steps"]["contract-capture"]
            assert capture["status"] == STATUS_FAILED, fixture_name


def test_interactive_wizard_parity_with_answers_file() -> None:
    fixture = json.loads((FIXTURES / "answers_valid.json").read_text())
    attached = fixture["attached_services"]
    scripted = [
        fixture["cluster_name"],
        fixture["environment"],
        "",  # deployment_mode: take the recommended default (hybrid)
        fixture["gitops_repo_url"],
        fixture["gitops_path"],
        fixture["base_domain"],
        fixture["storage_profile"],
        fixture["object_storage_profile"],
        fixture["identity_profile"],
        fixture["secret_profile"],
        fixture["ingress_profile"],
        attached["opensearch_endpoint"],
        attached["dashboards_endpoint"],
        attached["otlp_endpoint"],
    ]
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        snapshot = _merged_snapshot(workdir)
        interactive_dir = workdir / "interactive"
        answers_dir = workdir / "non-interactive"

        feed = iter(scripted)
        original_input = builtins.input
        builtins.input = lambda prompt="": next(feed)
        try:
            with _stub_modules():
                rc = flow.run(_install_args(snapshot, interactive_dir))
        finally:
            builtins.input = original_input
        assert rc == 0
        # The empty deployment_mode input must have taken the
        # recommendation, which is hybrid for this snapshot.
        recommendation = json.loads(
            (interactive_dir / "mode_recommendation.json").read_text()
        )
        assert (
            recommendation["decision"]["recommended_mode"] == "hybrid"
        )

        with _stub_modules():
            rc = flow.run(
                _install_args(
                    snapshot,
                    answers_dir,
                    FIXTURES / "answers_valid.json",
                )
            )
        assert rc == 0

        interactive_answers = (
            interactive_dir / "answers.json"
        ).read_bytes()
        file_answers = (answers_dir / "answers.json").read_bytes()
        assert interactive_answers == file_answers


def test_completed_install_rerun_changes_nothing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        snapshot = _merged_snapshot(workdir)
        output_dir = workdir / "install"
        args = _install_args(
            snapshot, output_dir, FIXTURES / "answers_valid.json"
        )
        with _stub_modules():
            assert flow.run(args) == 0
        before = _tree_state(output_dir)

        calls: list = []
        with _stub_modules(), _record_execution(calls):
            rc = flow.run(args)
        assert rc == 0
        assert calls == [], calls
        assert _tree_state(output_dir) == before


def test_corrupted_digest_forces_step_reexecution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        snapshot = _merged_snapshot(workdir)
        output_dir = workdir / "install"
        args = _install_args(
            snapshot, output_dir, FIXTURES / "answers_valid.json"
        )
        with _stub_modules():
            assert flow.run(args) == 0

        state_path = output_dir / "install_state.json"
        state = json.loads(state_path.read_text())
        state["steps"][STEP_RENDER]["input_digest"] = "0" * 64
        state_path.write_text(json.dumps(state))

        calls: list = []
        with _stub_modules(), _record_execution(calls):
            rc = flow.run(args)
        assert rc == 0
        assert calls == [STEP_RENDER], calls
        # The journal record is healed back to the real digest.
        healed = json.loads(state_path.read_text())
        assert (
            healed["steps"][STEP_RENDER]["input_digest"] != "0" * 64
        )


def test_failed_run_resumes_from_first_incomplete_step() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        snapshot = _merged_snapshot(workdir)
        output_dir = workdir / "install"
        args = _install_args(
            snapshot, output_dir, FIXTURES / "answers_valid.json"
        )
        stderr = io.StringIO()
        with _stub_modules(include_finalize=False):
            with contextlib.redirect_stderr(stderr):
                rc = flow.run(args)
        assert rc != 0
        assert "obskit install: error:" in stderr.getvalue()
        state = json.loads(
            (output_dir / "install_state.json").read_text()
        )
        assert (
            state["steps"][STEP_READINESS]["status"] == STATUS_FAILED
        )
        for step_id in STEP_ORDER[:-1]:
            assert (
                state["steps"][step_id]["status"] == STATUS_COMPLETED
            ), step_id

        calls: list = []
        with _stub_modules(), _record_execution(calls):
            rc = flow.run(args)
        assert rc == 0
        assert calls == [STEP_READINESS], calls
        assert (output_dir / "install_summary.json").is_file()


def test_tampered_contract_step_order_raises() -> None:
    original = (
        CONTRACTS / "install" / "INSTALL_FLOW_CONTRACT_V1.yaml"
    ).read_text()
    tampered = (
        original.replace("  - id: preflight", "  - id: __swap__")
        .replace("  - id: grading", "  - id: preflight")
        .replace("  - id: __swap__", "  - id: grading")
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "INSTALL_FLOW_CONTRACT_V1.yaml"
        path.write_text(tampered)
        try:
            flow.assert_contract_step_order(path)
        except InstallFlowError as exc:
            assert "step order" in str(exc)
        else:
            raise AssertionError(
                "tampered contract order was not rejected"
            )
        # The untampered contract passes and matches STEP_ORDER.
        path.write_text(original)
        assert flow.load_contract_step_ids(path) == STEP_ORDER
        flow.assert_contract_step_order(path)


def test_validator_rejects_unimplemented_keywords() -> None:
    schema = contract_module.load_schema(
        CONTRACTS / "install" / "INSTALL_CONTRACT_SCHEMA.json"
    )
    valid = json.loads((FIXTURES / "answers_valid.json").read_text())
    assert contract_module.validate_answers(valid, schema) == []

    drifted = json.loads(json.dumps(schema))
    drifted["properties"]["cluster_name"]["maxLength"] = 63
    try:
        contract_module.validate_answers(valid, drifted)
    except InstallFlowError as exc:
        assert "maxLength" in str(exc)
    else:
        raise AssertionError(
            "unimplemented schema keyword was not rejected"
        )


if __name__ == "__main__":
    test_valid_answers_flow_executes_contracted_step_order()
    print("test_valid_answers_flow_executes_contracted_step_order passed")
    test_invalid_answers_rejected_before_render()
    print("test_invalid_answers_rejected_before_render passed")
    test_interactive_wizard_parity_with_answers_file()
    print("test_interactive_wizard_parity_with_answers_file passed")
    test_completed_install_rerun_changes_nothing()
    print("test_completed_install_rerun_changes_nothing passed")
    test_corrupted_digest_forces_step_reexecution()
    print("test_corrupted_digest_forces_step_reexecution passed")
    test_failed_run_resumes_from_first_incomplete_step()
    print("test_failed_run_resumes_from_first_incomplete_step passed")
    test_tampered_contract_step_order_raises()
    print("test_tampered_contract_step_order_raises passed")
    test_validator_rejects_unimplemented_keywords()
    print("test_validator_rejects_unimplemented_keywords passed")
