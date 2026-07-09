"""obskit command-line interface.

Subcommands: preflight, discover, evaluate, install, render, drift,
rollback. The optional in-cluster
Job mode runs this same CLI in a container - one code path, so CLI and
Job reports are interchangeable (TR-18).

Subcommand handlers import their modules lazily: the parser stays
importable even while later-batch modules are still landing, and the
stdlib-only core never drags optional dependencies in.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence


def _add_reader_flags(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--snapshot",
        help="path to a recorded cluster snapshot (fixture mode)",
    )
    source.add_argument(
        "--live",
        action="store_true",
        help="read a live cluster via the Kubernetes API "
        "(requires the obskit[k8s] extra)",
    )
    parser.add_argument(
        "--kubeconfig",
        help="kubeconfig path for live mode (default: standard "
        "resolution order)",
    )
    parser.add_argument(
        "--context", help="kubeconfig context for live mode"
    )
    parser.add_argument(
        "--cluster-name",
        help="cluster name recorded in reports (live mode default: "
        "the kubeconfig context name)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="report destination file, or '-' for stdout (default)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obskit",
        description="Observability Kit discovery and preflight "
        "execution engine (read-only)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    preflight = subparsers.add_parser(
        "preflight",
        help="run every contracted preflight check class and emit a "
        "schema-conformant preflight report",
    )
    _add_reader_flags(preflight)

    discover = subparsers.add_parser(
        "discover",
        help="probe storage/ingress, GitOps/secrets integrations, and "
        "workload inventory; emit a schema-conformant probes report",
    )
    _add_reader_flags(discover)

    evaluate = subparsers.add_parser(
        "evaluate",
        help="derive capability matrix, compatibility grade, mode "
        "recommendation, and remediation list from one "
        "preflight-plus-discovery run",
    )
    evaluate.add_argument(
        "--preflight",
        required=True,
        help="path to a preflight report produced by "
        "'obskit preflight'",
    )
    evaluate.add_argument(
        "--discovery",
        required=True,
        help="path to a discovery probes report produced by "
        "'obskit discover'",
    )
    evaluate.add_argument(
        "--contracts-dir",
        default="contracts",
        help="repository contracts directory holding "
        "compatibility/GRADING_RULES.json, MODE_DECISION_TABLE.json, "
        "and REMEDIATION_CATALOG.json (default: ./contracts)",
    )
    evaluate.add_argument(
        "--output-dir",
        required=True,
        help="directory receiving capability_matrix.json, "
        "compatibility_result.json, mode_recommendation.json, and "
        "remediation_list.json",
    )
    evaluate.add_argument(
        "--profiles",
        help="optional JSON file supplying profiles discovery cannot "
        "observe (object_storage, identity); discovered profiles "
        "default from the capability matrix",
    )
    evaluate.add_argument(
        "--evaluation-only",
        action="store_true",
        help="mode input: this run evaluates the product rather than "
        "installing it",
    )
    evaluate.add_argument(
        "--allow-new-backend-components",
        choices=["true", "false"],
        default="true",
        help="mode input: new backend components may be deployed "
        "(default: true)",
    )
    evaluate.add_argument(
        "--require-in-cluster-collectors",
        choices=["true", "false"],
        default="true",
        help="mode input: collectors must run in-cluster "
        "(default: true)",
    )
    evaluate.add_argument(
        "--has-compatible-existing-services",
        choices=["auto", "true", "false"],
        default="auto",
        help="mode input: compatible existing services are present; "
        "'auto' derives it from the discovery probes report "
        "(default: auto)",
    )

    install = subparsers.add_parser(
        "install",
        help="run the guided install flow: preflight, grading, mode "
        "recommendation, contract capture, render, Argo CD bootstrap "
        "manifests, and post-install readiness (TR-19)",
    )
    _add_reader_flags(install)
    install.add_argument(
        "--answers",
        help="answers JSON file validated against "
        "contracts/install/INSTALL_CONTRACT_SCHEMA.json; omit to "
        "capture answers interactively (identical flow either way)",
    )
    install.add_argument(
        "--output-dir",
        required=True,
        help="directory receiving reports, the captured install "
        "contract, rendered manifests, and the install_state.json "
        "journal",
    )
    install.add_argument(
        "--contracts-dir",
        default="contracts",
        help="repository contracts directory holding the install "
        "flow contract, the install contract schema, and the "
        "compatibility contract files (default: ./contracts)",
    )
    install.add_argument(
        "--profiles",
        help="optional JSON file supplying profiles discovery cannot "
        "observe (object_storage, identity); discovered profiles "
        "default from the capability matrix",
    )
    install.add_argument(
        "--repo-root",
        default=".",
        help="repository root used by the post-install readiness "
        "step (default: .)",
    )
    # Mode inputs, mirroring `obskit evaluate` flag-for-flag so both
    # commands resolve the mode recommendation identically.
    install.add_argument(
        "--evaluation-only",
        action="store_true",
        help="mode input: this run evaluates the product rather than "
        "installing it",
    )
    install.add_argument(
        "--allow-new-backend-components",
        choices=["true", "false"],
        default="true",
        help="mode input: new backend components may be deployed "
        "(default: true)",
    )
    install.add_argument(
        "--require-in-cluster-collectors",
        choices=["true", "false"],
        default="true",
        help="mode input: collectors must run in-cluster "
        "(default: true)",
    )
    install.add_argument(
        "--has-compatible-existing-services",
        choices=["auto", "true", "false"],
        default="auto",
        help="mode input: compatible existing services are present; "
        "'auto' derives it from the discovery probes report "
        "(default: auto)",
    )

    render = subparsers.add_parser(
        "render",
        help="render the unified configuration document to native "
        "configs at each binding's render_target, plus the render "
        "manifest and prepared commit message (TR-20, GitOps-only)",
    )
    render.add_argument(
        "--document",
        required=True,
        help="unified configuration document as JSON, validated "
        "against contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json",
    )
    render.add_argument(
        "--contracts-dir",
        default="contracts",
        help="repository contracts directory holding the management "
        "plane contracts (default: ./contracts)",
    )
    render.add_argument(
        "--repo-root",
        default=".",
        help="repository root render targets are written under "
        "(default: .)",
    )
    render.add_argument(
        "--manifest-out",
        help="override path for the render manifest (default: "
        "<repo-root>/gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json)",
    )
    render.add_argument(
        "--commit-message-out",
        help="write the prepared propagation commit message (with "
        "the required trailers) to this path",
    )
    render.add_argument(
        "--check",
        action="store_true",
        help="plan only: exit 3 listing targets that would change, "
        "exit 0 when the tree already matches (no diff, no commit)",
    )

    drift = subparsers.add_parser(
        "drift",
        help="compare expected rendered bytes against a target tree "
        "and emit the rendered-versus-live diff surface consumed by "
        "the TR-12 drift alert path (read-only; exit 0 clean, 3 "
        "drift detected)",
    )
    drift.add_argument(
        "--document",
        help="unified configuration document as JSON, validated "
        "against contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json",
    )
    drift.add_argument(
        "--contracts-dir",
        default="contracts",
        help="repository contracts directory holding the management "
        "plane contracts (default: ./contracts)",
    )
    drift.add_argument(
        "--repo-root",
        default=".",
        help="target tree holding the live rendered state to diff "
        "against (default: .); never written to",
    )
    drift.add_argument(
        "--report-out",
        help="also write the drift report to this path (must resolve "
        "inside --repo-root); the report always goes to stdout",
    )

    rollback = subparsers.add_parser(
        "rollback",
        help="re-render a prior unified document revision through "
        "the identical render-and-commit pipeline (never a separate "
        "apply channel); dry-run by default",
    )
    rollback.add_argument(
        "--document",
        help="prior-revision unified configuration document as JSON",
    )
    rollback.add_argument(
        "--mode",
        choices=["dry-run", "real"],
        default="dry-run",
        help="dry-run (default): plan the rollback re-render and "
        "report without writing anything; real: execute the "
        "re-render and re-verify the tree afterwards",
    )
    rollback.add_argument(
        "--expected-manifest",
        help="render manifest previously committed for the prior "
        "document revision; the planned manifest must be "
        "byte-identical (deterministic rollback proof) or the "
        "rollback refuses to proceed in either mode",
    )
    rollback.add_argument(
        "--report-out",
        help="also write the rollback report JSON to this path "
        "(must resolve inside --repo-root); the report always goes "
        "to stdout",
    )
    rollback.add_argument(
        "--contracts-dir",
        default="contracts",
        help="repository contracts directory (default: ./contracts)",
    )
    rollback.add_argument(
        "--repo-root",
        default=".",
        help="repository root render targets are written under "
        "(default: .)",
    )
    rollback.add_argument(
        "--commit-message-out",
        help="write the prepared rollback commit message to this "
        "path",
    )

    return parser


# Expected operator errors: bad paths, malformed input documents,
# missing document keys, and misconfiguration (e.g. live mode without
# the [k8s] extra). These print one clean line instead of a traceback;
# genuine bugs still surface as tracebacks.
_OPERATOR_ERRORS = (OSError, ValueError, KeyError, RuntimeError)


def _describe_error(exc: BaseException) -> str:
    if isinstance(exc, KeyError):
        return f"missing key {exc.args[0]!r} in input document"
    return str(exc) or exc.__class__.__name__


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "preflight":
            from obskit.preflight import run as run_preflight

            return run_preflight(args)
        if args.command == "discover":
            from obskit.discovery import run as run_discover

            return run_discover(args)
        if args.command == "evaluate":
            from obskit.evaluate import run as run_evaluate

            return run_evaluate(args)
        if args.command == "install":
            from obskit.install.flow import run as run_install

            return run_install(args)
        if args.command == "render":
            from obskit.configrender.render import run as run_render

            return run_render(args)
        if args.command == "drift":
            from obskit.configrender.drift import run as run_drift

            return run_drift(args)
        if args.command == "rollback":
            from obskit.configrender.rollback import (
                run as run_rollback,
            )

            return run_rollback(args)
    except _OPERATOR_ERRORS as exc:
        sys.stderr.write(
            f"obskit {args.command}: error: {_describe_error(exc)}\n"
        )
        return 1
    raise AssertionError(f"unhandled command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
