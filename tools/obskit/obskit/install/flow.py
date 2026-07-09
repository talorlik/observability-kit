"""Guided install step engine (Batch 18 Task 2, TR-05/TR-14/TR-19).

Implements `obskit install`: an ordered dispatch over the seven step
ids fixed by contracts/install/INSTALL_FLOW_CONTRACT_V1.yaml, with an
install_state.json journal providing idempotency and resume (TR-19).

Contract-order enforcement: the flow contract is loaded at runtime
with a line-based stdlib parse (mirroring the pattern of
scripts/ci/validate_discovery_executor.sh - the core imports no YAML
library) and its step id sequence is asserted against
obskit.install.models.STEP_ORDER, so order drift between contract and
implementation fails loudly instead of shipping.

Step composition: preflight, grading, and mode-recommendation call
the Batch 17 executor modules (obskit.preflight, obskit.discovery,
obskit.evaluate) as library functions - one engine, one code path
(ADR-0002). render, argocd-bootstrap, and post-install-readiness
dispatch through lazy imports of obskit.install.render and
obskit.install.finalize, so the flow stays importable and testable
while those modules land in parallel tasks; a missing module surfaces
as a clean InstallFlowError, not a traceback.

Skip rule (idempotency + resume): a step is skipped when its journal
record is "completed", every recorded output exists, and the recorded
input digest matches the sha256 hex over the step's canonical inputs:

- preflight, grading, mode-recommendation: the snapshot file bytes
  (live mode has no snapshot bytes, so live steps never skip);
- contract-capture, render, argocd-bootstrap: the canonical JSON of
  the answers mapping;
- post-install-readiness: the concatenation of both.

Re-running a completed install changes no files and exits 0; a failed
run resumes from the first non-completed step.

Determinism: every JSON artifact goes through obskit.emit.write_report
(sorted keys, fixed indentation, trailing newline); the
install_state.json journal is the one deliberately mutable artifact
and is rewritten only when a step record actually changes.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sys
from argparse import Namespace
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from obskit.discovery import build_probes_report
from obskit.emit import canonical_json, write_report
from obskit.evaluate import (
    CAPABILITY_MATRIX_FILENAME,
    COMPATIBILITY_RESULT_FILENAME,
    MODE_RECOMMENDATION_FILENAME,
    REMEDIATION_LIST_FILENAME,
    EvaluationArtifacts,
    ModeFlags,
    evaluate_reports,
    load_contracts,
)
from obskit.install import contract as contract_module
from obskit.install import wizard
from obskit.install.models import (
    ANSWERS_FILENAME,
    INSTALL_STATE_FILENAME,
    RENDERED_DIRNAME,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STEP_ARGOCD_BOOTSTRAP,
    STEP_CONTRACT_CAPTURE,
    STEP_GRADING,
    STEP_MODE_RECOMMENDATION,
    STEP_ORDER,
    STEP_PREFLIGHT,
    STEP_READINESS,
    STEP_RENDER,
    InstallAnswers,
    InstallFlowError,
    InstallState,
)
from obskit.preflight import STATUS_FAIL, evaluate_preflight
from obskit.reader import ClusterReader, build_reader

PREFLIGHT_REPORT_FILENAME = "preflight_report.json"

# Flow contract location, relative to --contracts-dir.
FLOW_CONTRACT_RELATIVE = Path("install") / "INSTALL_FLOW_CONTRACT_V1.yaml"
INSTALL_SCHEMA_RELATIVE = Path("install") / "INSTALL_CONTRACT_SCHEMA.json"

GRADE_BLOCKED = "blocked"

# Steps digested over the snapshot bytes vs the answers mapping; the
# readiness step concatenates both (see module docstring).
_SNAPSHOT_DIGEST_STEPS = frozenset(
    {STEP_PREFLIGHT, STEP_GRADING, STEP_MODE_RECOMMENDATION}
)
_ANSWERS_DIGEST_STEPS = frozenset(
    {STEP_CONTRACT_CAPTURE, STEP_RENDER, STEP_ARGOCD_BOOTSTRAP}
)

# Expected operator errors: bad paths, malformed inputs, halted steps
# (InstallFlowError and EvaluationError are RuntimeError subclasses).
# These get one clean stderr line; genuine bugs still traceback.
_OPERATOR_ERRORS = (OSError, ValueError, KeyError, RuntimeError)

_ID_PATTERN = re.compile(r"^  - id: (\S+)\s*$")
_ORDER_PATTERN = re.compile(r"^    order: (\d+)\s*$")


def load_contract_step_ids(contract_path: Path) -> tuple[str, ...]:
    """Parse the flow contract's step ids, ordered by 'order:'.

    Line-based and stdlib-only by design: only '  - id: <step>' items
    under the top-level 'steps:' key and their '    order: <n>' values
    are read, mirroring scripts/ci/validate_discovery_executor.sh.
    """
    if not contract_path.is_file():
        raise InstallFlowError(
            f"install flow contract not found: {contract_path}"
        )
    in_steps = False
    current_id: str | None = None
    entries: list[tuple[int, str]] = []
    for line in contract_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            # A new top-level key ends (or begins) the steps block.
            in_steps = stripped == "steps:"
            continue
        if not in_steps:
            continue
        id_match = _ID_PATTERN.match(line)
        if id_match:
            current_id = id_match.group(1)
            continue
        order_match = _ORDER_PATTERN.match(line)
        if order_match and current_id is not None:
            entries.append((int(order_match.group(1)), current_id))
            current_id = None
    if not entries:
        raise InstallFlowError(
            f"install flow contract {contract_path} declares no "
            "parseable steps"
        )
    orders = [order for order, _ in entries]
    if orders != sorted(set(orders)):
        raise InstallFlowError(
            f"install flow contract {contract_path} step orders are "
            f"not strictly ascending: {orders}"
        )
    return tuple(step_id for _, step_id in entries)


def assert_contract_step_order(contract_path: Path) -> None:
    """Fail loudly when the contract's step sequence drifts."""
    contract_ids = load_contract_step_ids(contract_path)
    if contract_ids != STEP_ORDER:
        raise InstallFlowError(
            "install flow contract step order "
            f"{list(contract_ids)} does not match the implemented "
            f"order {list(STEP_ORDER)}"
        )


@dataclass
class _FlowContext:
    """Per-run state shared by the step executors."""

    args: Namespace
    output_dir: Path
    repo_root: Path
    contracts_dir: Path
    snapshot_bytes: bytes | None
    answers_mapping: dict[str, Any] | None = None
    executed: list[str] = field(default_factory=list)


def _sha256(*parts: bytes) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part)
    return digest.hexdigest()


def _resolve_answers_mapping(
    ctx: _FlowContext,
) -> dict[str, Any] | None:
    """The answers mapping, from cache, --answers, or answers.json.

    Returns None when no source exists yet (first interactive run
    before contract-capture) - the dependent steps then compute no
    skip digest and simply execute.
    """
    if ctx.answers_mapping is not None:
        return ctx.answers_mapping
    if ctx.args.answers:
        ctx.answers_mapping = contract_module.load_answers_file(
            ctx.args.answers
        )
        return ctx.answers_mapping
    recorded = ctx.output_dir / ANSWERS_FILENAME
    if recorded.is_file():
        ctx.answers_mapping = contract_module.load_answers_file(
            str(recorded)
        )
        return ctx.answers_mapping
    return None


def _step_input_digest(step_id: str, ctx: _FlowContext) -> str | None:
    """sha256 hex over the step's canonical inputs, None if unknown."""
    if step_id in _SNAPSHOT_DIGEST_STEPS:
        if ctx.snapshot_bytes is None:
            return None
        return _sha256(ctx.snapshot_bytes)
    answers = _resolve_answers_mapping(ctx)
    answers_bytes = (
        canonical_json(answers).encode("utf-8")
        if answers is not None
        else None
    )
    if step_id in _ANSWERS_DIGEST_STEPS:
        if answers_bytes is None:
            return None
        return _sha256(answers_bytes)
    if step_id == STEP_READINESS:
        if ctx.snapshot_bytes is None or answers_bytes is None:
            return None
        return _sha256(ctx.snapshot_bytes, answers_bytes)
    raise AssertionError(f"unhandled step id {step_id!r}")


def _build_flow_reader(args: Namespace) -> ClusterReader:
    return build_reader(
        args.snapshot,
        args.live,
        args.kubeconfig,
        args.context,
        args.cluster_name,
    )


def _run_preflight(ctx: _FlowContext) -> tuple[str, ...]:
    report = evaluate_preflight(_build_flow_reader(ctx.args))
    write_report(
        report, str(ctx.output_dir / PREFLIGHT_REPORT_FILENAME)
    )
    summary = report["summary"]
    assert isinstance(summary, dict)
    if summary["outcome"] == STATUS_FAIL:
        checks = report["checks"]
        assert isinstance(checks, list)
        failing = ", ".join(
            f"{check['id']} ({check.get('reason_code', 'unknown')})"
            for check in checks
            if check["status"] == STATUS_FAIL
        )
        raise InstallFlowError(
            f"preflight failed: {failing}; see "
            f"{PREFLIGHT_REPORT_FILENAME} for remediation guidance"
        )
    return (PREFLIGHT_REPORT_FILENAME,)


def _evaluate_artifacts(ctx: _FlowContext) -> EvaluationArtifacts:
    """Grading inputs -> the four evaluation artifact payloads.

    Composes the Batch 17 engine: the preflight report emitted by the
    preflight step plus a discovery probes report built in-memory from
    the same cluster source, evaluated against the Batch 2 contract
    files. Pure and deterministic for identical inputs, so grading
    and mode-recommendation can each recompute it independently
    (resume never needs cross-step in-memory state).
    """
    preflight_path = ctx.output_dir / PREFLIGHT_REPORT_FILENAME
    try:
        preflight_report = json.loads(
            preflight_path.read_text(encoding="utf-8")
        )
    except OSError as exc:
        raise InstallFlowError(
            f"cannot read {PREFLIGHT_REPORT_FILENAME} (did the "
            f"preflight step run?): {exc}"
        ) from exc
    discovery_report = build_probes_report(_build_flow_reader(ctx.args))
    contracts = load_contracts(str(ctx.contracts_dir))
    profile_overrides: dict[str, str] = {}
    if ctx.args.profiles:
        loaded = json.loads(
            Path(ctx.args.profiles).read_text(encoding="utf-8")
        )
        if not isinstance(loaded, dict):
            raise InstallFlowError(
                f"profiles file {ctx.args.profiles} must contain a "
                "JSON object"
            )
        profile_overrides = loaded
    tri_state = ctx.args.has_compatible_existing_services
    mode_flags = ModeFlags(
        evaluation_only=bool(ctx.args.evaluation_only),
        allow_new_backend_components=(
            ctx.args.allow_new_backend_components == "true"
        ),
        require_in_cluster_collectors=(
            ctx.args.require_in_cluster_collectors == "true"
        ),
        has_compatible_existing_services=(
            None if tri_state == "auto" else tri_state == "true"
        ),
    )
    # input_refs record inputs as passed (the evaluate CLI precedent);
    # sibling artifacts are referenced relative to the output dir so
    # payloads stay identical across --output-dir values.
    input_refs = {
        "preflight_report": PREFLIGHT_REPORT_FILENAME,
        "discovery_probes": ctx.args.snapshot or "live",
        "capability_matrix": CAPABILITY_MATRIX_FILENAME,
    }
    return evaluate_reports(
        preflight_report=preflight_report,
        discovery_report=discovery_report,
        contracts=contracts,
        profile_overrides=profile_overrides,
        mode_flags=mode_flags,
        input_refs=input_refs,
    )


def _run_grading(ctx: _FlowContext) -> tuple[str, ...]:
    artifacts = _evaluate_artifacts(ctx)
    outputs = (
        CAPABILITY_MATRIX_FILENAME,
        COMPATIBILITY_RESULT_FILENAME,
        REMEDIATION_LIST_FILENAME,
    )
    for filename, payload in (
        (CAPABILITY_MATRIX_FILENAME, artifacts.capability_matrix),
        (
            COMPATIBILITY_RESULT_FILENAME,
            artifacts.compatibility_result,
        ),
        (REMEDIATION_LIST_FILENAME, artifacts.remediation_list),
    ):
        write_report(payload, str(ctx.output_dir / filename))
    result = artifacts.compatibility_result["compatibility_result"]
    if result["grade"] == GRADE_BLOCKED:
        for entry in artifacts.remediation_list["remediations"]:
            sys.stderr.write(
                f"remediation [{entry['severity']}] "
                f"{entry['reason']}:\n"
            )
            for action in entry["actions"]:
                sys.stderr.write(f"  - {action}\n")
        raise InstallFlowError(
            "compatibility grade is 'blocked'; apply the remediation "
            f"entries above (also in {REMEDIATION_LIST_FILENAME}) "
            "and re-run"
        )
    return outputs


def _run_mode_recommendation(ctx: _FlowContext) -> tuple[str, ...]:
    # A mode-decision-table gap raises EvaluationError inside
    # resolve_mode, which halts the flow as an operator error.
    artifacts = _evaluate_artifacts(ctx)
    write_report(
        artifacts.mode_recommendation,
        str(ctx.output_dir / MODE_RECOMMENDATION_FILENAME),
    )
    return (MODE_RECOMMENDATION_FILENAME,)


def _recommended_mode(ctx: _FlowContext) -> str | None:
    path = ctx.output_dir / MODE_RECOMMENDATION_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    decision = payload.get("decision", {})
    if not isinstance(decision, dict):
        return None
    mode = decision.get("recommended_mode")
    return mode if isinstance(mode, str) else None


def _run_contract_capture(ctx: _FlowContext) -> tuple[str, ...]:
    schema_path = ctx.contracts_dir / INSTALL_SCHEMA_RELATIVE
    if ctx.args.answers:
        mapping = contract_module.load_answers_file(ctx.args.answers)
    else:
        recorded = ctx.output_dir / ANSWERS_FILENAME
        if recorded.is_file():
            # A previous run already captured answers; reuse them so
            # interactive installs resume without re-prompting. To
            # change answers, pass --answers or start a fresh
            # --output-dir.
            mapping = contract_module.load_answers_file(str(recorded))
        else:
            schema = contract_module.load_schema(schema_path)
            mapping = wizard.capture_answers(
                schema, _recommended_mode(ctx)
            )
    outputs = contract_module.capture_contract(
        mapping, schema_path, ctx.output_dir
    )
    ctx.answers_mapping = mapping
    return outputs


def _lazy_step_module(name: str, step_id: str) -> ModuleType:
    # ImportError (not just ModuleNotFoundError): a module that is
    # absent, half-installed, or blocked must halt the step with a
    # clean operator error, never a traceback.
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise InstallFlowError(
            f"step '{step_id}' requires module {name}, which is not "
            f"available in this build ({exc})"
        ) from exc


def _validated_answers(ctx: _FlowContext) -> InstallAnswers:
    mapping = _resolve_answers_mapping(ctx)
    if mapping is None:
        raise InstallFlowError(
            "no captured answers available; the contract-capture "
            "step must complete first"
        )
    return InstallAnswers.from_mapping(mapping)


def _run_render(ctx: _FlowContext) -> tuple[str, ...]:
    render = _lazy_step_module("obskit.install.render", STEP_RENDER)
    result = render.render_overlay(
        _validated_answers(ctx), ctx.output_dir
    )
    return tuple(result.files)


def _run_argocd_bootstrap(ctx: _FlowContext) -> tuple[str, ...]:
    render = _lazy_step_module(
        "obskit.install.render", STEP_ARGOCD_BOOTSTRAP
    )
    answers = _validated_answers(ctx)
    result = render.render_bootstrap(answers, ctx.output_dir)
    _print_bootstrap_instruction(answers, ctx.output_dir)
    return tuple(result.files)


def _print_bootstrap_instruction(
    answers: InstallAnswers, output_dir: Path
) -> None:
    """Print the operator apply instruction the flow contract requires.

    The installer never applies manifests itself (GitOps-only
    propagation): committing the rendered output and bootstrapping
    the Argo CD controller are operator actions, spelled out here.
    """
    rendered_dir = output_dir / RENDERED_DIRNAME
    print(
        "argocd-bootstrap: manifests rendered; the installer applies"
        " nothing itself. Operator actions:\n"
        f"  1. Commit the CONTENTS of {rendered_dir}/ into"
        f" '{answers.gitops_path}/' of {answers.gitops_repo_url}"
        " (the repository must carry the kit's gitops/ tree: chart"
        " and base overlay).\n"
        "  2. Bootstrap the Argo CD controller from that commit:\n"
        f"       kubectl apply -k"
        f" {answers.gitops_path}/bootstrap/argocd/\n"
        "  3. The flow now runs post-install readiness and emits the"
        " install summary; after the cluster reconciles, re-run"
        " 'obskit install' with the same --output-dir to re-verify."
    )


def _run_readiness(ctx: _FlowContext) -> tuple[str, ...]:
    finalize = _lazy_step_module(
        "obskit.install.finalize", STEP_READINESS
    )
    result = finalize.run_readiness(
        _validated_answers(ctx), ctx.output_dir, ctx.repo_root
    )
    if result.status != STATUS_COMPLETED:
        raise InstallFlowError(
            "post-install readiness failed: "
            + (result.detail or result.status)
        )
    return tuple(result.outputs)


# Step executors keyed by contracted step id; the engine dispatches
# through this mapping in STEP_ORDER sequence. Looked up at call time
# so tests can instrument execution order.
_EXECUTORS: dict[str, Callable[[_FlowContext], tuple[str, ...]]] = {
    STEP_PREFLIGHT: _run_preflight,
    STEP_GRADING: _run_grading,
    STEP_MODE_RECOMMENDATION: _run_mode_recommendation,
    STEP_CONTRACT_CAPTURE: _run_contract_capture,
    STEP_RENDER: _run_render,
    STEP_ARGOCD_BOOTSTRAP: _run_argocd_bootstrap,
    STEP_READINESS: _run_readiness,
}


def _load_state(state_path: Path) -> InstallState:
    if not state_path.is_file():
        return InstallState()
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InstallFlowError(
            f"corrupt install state journal {state_path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise InstallFlowError(
            f"install state journal {state_path} must be a JSON object"
        )
    return InstallState.from_mapping(payload)


def _outputs_exist(
    output_dir: Path, outputs: Sequence[str]
) -> bool:
    return all(
        (output_dir / relative).exists() for relative in outputs
    )


def _record_step(
    state: InstallState,
    state_path: Path,
    step_id: str,
    status: str,
    input_digest: str | None,
    outputs: Sequence[str],
) -> None:
    """Update one journal record, rewriting the file only on change."""
    entry: dict[str, Any] = {
        "status": status,
        "input_digest": input_digest,
        "outputs": list(outputs),
    }
    if state.steps.get(step_id) != entry:
        state.steps[step_id] = entry
        write_report(state.to_mapping(), str(state_path))


def _execute_flow(args: Namespace) -> int:
    contracts_dir = Path(args.contracts_dir)
    assert_contract_step_order(contracts_dir / FLOW_CONTRACT_RELATIVE)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ctx = _FlowContext(
        args=args,
        output_dir=output_dir,
        repo_root=Path(args.repo_root),
        contracts_dir=contracts_dir,
        snapshot_bytes=(
            Path(args.snapshot).read_bytes() if args.snapshot else None
        ),
    )

    state_path = output_dir / INSTALL_STATE_FILENAME
    state = _load_state(state_path)
    for step_id in STEP_ORDER:
        digest = _step_input_digest(step_id, ctx)
        record = state.steps.get(step_id)
        if (
            record is not None
            and record.get("status") == STATUS_COMPLETED
            and digest is not None
            and record.get("input_digest") == digest
            and _outputs_exist(output_dir, record.get("outputs", []))
        ):
            continue
        try:
            outputs = _EXECUTORS[step_id](ctx)
        except _OPERATOR_ERRORS:
            _record_step(
                state, state_path, step_id, STATUS_FAILED, digest, ()
            )
            raise
        # Recompute: interactive contract-capture only knows its
        # answers digest after the wizard ran.
        _record_step(
            state,
            state_path,
            step_id,
            STATUS_COMPLETED,
            _step_input_digest(step_id, ctx),
            outputs,
        )
        ctx.executed.append(step_id)
    return 0


def _describe_error(exc: BaseException) -> str:
    if isinstance(exc, KeyError):
        return f"missing key {exc.args[0]!r} in input document"
    return str(exc) or exc.__class__.__name__


def run(args: Namespace) -> int:
    """CLI entry for `obskit install` (routed from obskit.cli).

    Returns 0 when every contracted step is completed (or skipped as
    already complete); expected operator errors - halted steps,
    invalid answers, bad paths - print one clean line to stderr and
    return 1. Genuine bugs still traceback.
    """
    try:
        return _execute_flow(args)
    except _OPERATOR_ERRORS as exc:
        sys.stderr.write(
            f"obskit install: error: {_describe_error(exc)}\n"
        )
        return 1
