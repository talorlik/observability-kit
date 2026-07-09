"""`obskit rollback` - re-render from a prior revision (Batch 19 Task 4).

Rollback IS a re-render: the prior unified document revision travels
the identical render-and-commit pipeline (plan_render + execute_plan
from obskit.configrender.render) - never a separate apply channel,
per the propagation contract's rollback block (unified-document-revert
preferred) and the renderer architecture contract's rollback block
(separate_apply_channel: forbidden). No Git commands, no kubectl, no
API calls happen here; the rollback commit message with the required
trailers is emitted exactly as `obskit render` emits it.

Modes follow the scripts/ops drill conventions with dry-run as the
default: dry-run plans only and writes nothing; real executes the
plan and re-verifies that every target matches afterwards. The
deterministic proof (--expected-manifest) asserts that the planned
render manifest is byte-identical to the manifest previously committed
for that document revision - "revert plus re-render reproduces the
previously committed rendered bytes; the drill asserts digest
equality". A mismatch refuses to proceed in both modes. The
operational drill wrapper is scripts/ops/run_config_rollback_drill.sh.
"""

from __future__ import annotations

import hashlib
import sys
from argparse import Namespace
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from obskit.configrender.models import (
    ConfigRenderError,
    EXIT_ERROR,
    EXIT_OK,
    RenderPlan,
)

# _assert_contained is the render pipeline's own write-containment
# guard; rollback reuses it so --report-out mirrors the --manifest-out
# containment exactly (one rule, one implementation).
from obskit.configrender.render import (
    _assert_contained,
    changed_paths,
    execute_plan,
    plan_render,
)
from obskit.emit import canonical_json

MODE_DRY_RUN = "dry-run"
MODE_REAL = "real"

PROOF_VERIFIED = "verified"
PROOF_NOT_REQUESTED = "not-requested"

STATUS_PLANNED = "planned"
STATUS_ROLLED_BACK = "rolled-back"


@dataclass(frozen=True)
class RollbackResult:
    """Outcome of one rollback re-render (planned or executed).

    paths carries repository-relative POSIX paths: the targets that
    would change (dry-run) or the paths actually written (real).
    """

    mode: str
    schema_version: str
    document_digest: str
    paths: tuple[str, ...]
    deterministic_proof: str
    status: str

    def report(self) -> dict[str, object]:
        """Canonical rollback report payload (sorted keys downstream,
        no timestamps, hostnames, or random identifiers)."""
        paths_key = (
            "would_change" if self.mode == MODE_DRY_RUN else "changed"
        )
        return {
            "mode": self.mode,
            "schema_version": self.schema_version,
            "document_digest": self.document_digest,
            paths_key: list(self.paths),
            "deterministic_proof": self.deterministic_proof,
            "status": self.status,
        }


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _relative_paths(
    paths: Iterable[str], repo_root: Path
) -> tuple[str, ...]:
    """Sorted, de-duplicated paths, repo-relative where possible.

    plan/execute surfaces mix repo-relative artifact paths with
    absolute manifest and commit-message paths; the report stays
    deterministic by folding everything under the repo root back to
    its relative POSIX form.
    """
    root = repo_root.resolve()
    normalized: set[str] = set()
    for path in paths:
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if resolved.is_relative_to(root):
                normalized.add(resolved.relative_to(root).as_posix())
                continue
        normalized.add(str(path))
    return tuple(sorted(normalized))


def _assert_deterministic_proof(
    plan: RenderPlan, expected_manifest: Path
) -> None:
    """Digest-equality proof against a previously committed manifest.

    The planned manifest must be byte-identical to the manifest the
    prior document revision committed; anything else means the
    rollback would NOT reproduce the previously committed rendered
    bytes, so it refuses to proceed (both modes, nothing written).
    """
    if not expected_manifest.is_file():
        raise ConfigRenderError(
            f"expected manifest {expected_manifest} does not exist"
        )
    expected = expected_manifest.read_bytes()
    planned = plan.manifest_content.encode("utf-8")
    if planned != expected:
        raise ConfigRenderError(
            "deterministic rollback proof failed: planned manifest "
            f"digest sha256:{_sha256_hex(planned)} does not equal "
            f"expected manifest digest sha256:{_sha256_hex(expected)} "
            f"({expected_manifest}); refusing to roll back"
        )


def rollback_render(
    document_path: Path,
    contracts_dir: Path,
    repo_root: Path,
    mode: str = MODE_DRY_RUN,
    expected_manifest: Path | None = None,
    commit_message_out: Path | None = None,
) -> RollbackResult:
    """Roll back by re-rendering the prior document revision.

    Raises ConfigRenderError on any violation; in dry-run mode (the
    default) nothing is ever written, and in real mode the proof and
    plan both complete before the first write.
    """
    if mode not in (MODE_DRY_RUN, MODE_REAL):
        raise ConfigRenderError(
            f"unknown rollback mode {mode!r} (expected "
            f"{MODE_DRY_RUN!r} or {MODE_REAL!r})"
        )
    # The identical pipeline: the same in-memory planner `obskit
    # render` uses, fed the prior document revision.
    plan = plan_render(document_path, contracts_dir, repo_root)
    proof = PROOF_NOT_REQUESTED
    if expected_manifest is not None:
        _assert_deterministic_proof(plan, expected_manifest)
        proof = PROOF_VERIFIED
    if mode == MODE_DRY_RUN:
        pending = _relative_paths(
            changed_paths(plan, repo_root), repo_root
        )
        return RollbackResult(
            mode=MODE_DRY_RUN,
            schema_version=plan.schema_version,
            document_digest=plan.document_digest,
            paths=pending,
            deterministic_proof=proof,
            status=STATUS_PLANNED,
        )
    written = execute_plan(plan, repo_root, commit_message_out)
    residual = changed_paths(plan, repo_root)
    if residual:
        raise ConfigRenderError(
            "post-rollback verification failed: targets still differ "
            "from the rolled-back plan after writing: "
            + ", ".join(_relative_paths(residual, repo_root))
        )
    return RollbackResult(
        mode=MODE_REAL,
        schema_version=plan.schema_version,
        document_digest=plan.document_digest,
        paths=_relative_paths(written, repo_root),
        deterministic_proof=proof,
        status=STATUS_ROLLED_BACK,
    )


def run(args: Namespace) -> int:
    """CLI entry point for `obskit rollback`."""
    if not args.document:
        # Mirrors `obskit drift`: resolving the prior revision from
        # Git history would require running Git, which this runtime
        # never does - the operator supplies the prior document.
        sys.stderr.write(
            "obskit rollback: error: --document is required\n"
        )
        return EXIT_ERROR
    repo_root = Path(args.repo_root)
    contracts_dir = Path(args.contracts_dir)
    expected_manifest = (
        Path(args.expected_manifest)
        if args.expected_manifest
        else None
    )
    commit_message_out = (
        Path(args.commit_message_out)
        if args.commit_message_out
        else None
    )
    report_out = Path(args.report_out) if args.report_out else None
    try:
        if report_out is not None:
            # Same containment rule as `obskit render --manifest-out`:
            # the report is a write like any other and must land
            # inside the repository root.
            _assert_contained(
                report_out, repo_root, "rollback report path"
            )
        result = rollback_render(
            Path(args.document),
            contracts_dir,
            repo_root,
            mode=args.mode,
            expected_manifest=expected_manifest,
            commit_message_out=commit_message_out,
        )
    except ConfigRenderError as exc:
        sys.stderr.write(f"obskit rollback: error: {exc}\n")
        return EXIT_ERROR
    text = canonical_json(result.report())
    sys.stdout.write(text)
    if report_out is not None:
        try:
            report_out.parent.mkdir(parents=True, exist_ok=True)
            report_out.write_text(text, encoding="utf-8")
        except OSError as exc:
            sys.stderr.write(f"obskit rollback: error: {exc}\n")
            return EXIT_ERROR
    return EXIT_OK
