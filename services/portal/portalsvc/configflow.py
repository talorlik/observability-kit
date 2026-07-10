"""Unified configuration read/edit through the Batch 19 renderer.

Implements the portal contract's config view (write_path
gitops-renderer-commit) on top of the obskit.configrender library
(ADR-0003/ADR-0005): a submitted document is validated by
plan_render (which validates against UNIFIED_CONFIG_SCHEMA_V1.json
and every cross-file rule internally, raising ConfigRenderError with
messages), dry-run diffed with changed_paths, and materialized only
through execute_plan - rendered files plus a prepared commit
reference. Edits become Git commit material; the portal never writes
a live config endpoint and never executes a git command
(fail_if_live_config_write).

Paths (repo_root, document_path, contracts_dir) are constructor
parameters supplied by the deployment; nothing here defaults to a
real host or environment value.

obskit is a logical dependency resolved in-repo: when the package is
not installed, tools/obskit is added to sys.path relative to this
file's position in the monorepo (services/portal/portalsvc/), the
same pattern tenantctl.renders and the repo's offline tests use (see
services/portal/pyproject.toml).
"""

from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any


def _ensure_obskit_importable() -> None:
    try:
        import obskit  # noqa: F401
        return
    except ModuleNotFoundError:
        pkg_root = (
            Path(__file__).resolve().parents[3] / "tools" / "obskit"
        )
        if not (pkg_root / "obskit" / "__init__.py").is_file():
            raise ModuleNotFoundError(
                "the obskit package is not installed and tools/obskit "
                "was not found relative to services/portal; install "
                "obskit or run from the repository checkout"
            ) from None
        sys.path.insert(0, str(pkg_root))


_ensure_obskit_importable()

from obskit.configrender.models import (  # noqa: E402
    ConfigRenderError,
    RenderPlan,
)
from obskit.configrender.render import (  # noqa: E402
    changed_paths,
    execute_plan,
    plan_render,
)

from portalsvc.models import (  # noqa: E402
    CommitResult,
    ConfigDocumentMissing,
    ConfigEditRejected,
    ConfigPlanResult,
)


def _commit_ref_for(plan: RenderPlan) -> str:
    """Opaque prepared-commit reference for an executed edit.

    Deterministic: derived from the document digest, mirroring
    tenantctl.renders.commit_ref_for and the Batch 19 commit
    trailers that bind a propagation commit to its document
    revision. No git command runs here.
    """
    return f"prepared:{plan.document_digest}"


class ConfigFlow:
    """Read and edit the unified configuration document.

    repo_root is the GitOps working tree the renderer writes into;
    document_path is the unified document's repository path (absolute
    or repo-root-relative, always contained in repo_root);
    contracts_dir is the contracts/ directory carrying
    management/UNIFIED_CONFIG_SCHEMA_V1.json and its sibling
    contracts, read-only.
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        document_path: Path,
        contracts_dir: Path,
    ) -> None:
        self._repo_root = repo_root
        self._contracts_dir = contracts_dir
        resolved = (
            document_path
            if document_path.is_absolute()
            else repo_root / document_path
        ).resolve()
        # Containment guard mirroring the renderer's write-scope
        # checks: the document is committed alongside its renders, so
        # it must live inside the repository root.
        if not resolved.is_relative_to(repo_root.resolve()):
            raise ValueError(
                f"document path {document_path} escapes the "
                "repository root; refusing to operate on it"
            )
        self._document_path = resolved
        # commit_edit is a read-modify-write over shared repo state
        # (persist document, re-plan, execute); the lock serializes
        # it within this process. Cross-process safety is a
        # deployment rule: one config writer per repo_root (see the
        # portal runbook; same posture as ADR-0004's single-writer
        # store note).
        self._commit_lock = threading.Lock()

    @property
    def document_path(self) -> Path:
        return self._document_path

    def get_document(self) -> dict[str, Any]:
        """Read and parse the unified configuration document."""
        if not self._document_path.is_file():
            raise ConfigDocumentMissing(
                "unified configuration document not found at its "
                "repository path"
            )
        try:
            document = json.loads(
                self._document_path.read_bytes()
            )
        except json.JSONDecodeError as error:
            raise ConfigEditRejected(
                f"unified configuration document is not valid JSON: "
                f"{error}"
            ) from error
        if not isinstance(document, dict):
            raise ConfigEditRejected(
                "unified configuration document must be a JSON object"
            )
        return document

    def _plan_submitted(self, submitted: bytes) -> RenderPlan:
        """Validate and plan a submitted document without writing.

        The submitted bytes go to a temp file first (plan_render
        reads a path); the temp file carries the real document name
        so plan output is byte-for-byte what the commit plan yields.
        """
        with tempfile.TemporaryDirectory(
            prefix="portal-config-plan-"
        ) as workdir:
            candidate = Path(workdir) / self._document_path.name
            candidate.write_bytes(submitted)
            return plan_render(
                candidate, self._contracts_dir, self._repo_root
            )

    def plan_edit(self, submitted: bytes) -> ConfigPlanResult:
        """Dry-run a submitted edit: validate, plan, diff.

        Nothing is written in any outcome; an invalid document is
        reported with the renderer's own error messages.
        """
        try:
            plan = self._plan_submitted(submitted)
        except ConfigRenderError as error:
            return ConfigPlanResult(
                valid=False,
                changed_paths=(),
                errors=(str(error),),
            )
        return ConfigPlanResult(
            valid=True,
            changed_paths=changed_paths(plan, self._repo_root),
            errors=(),
        )

    def commit_edit(
        self,
        submitted: bytes,
        commit_message_out: Path | None = None,
    ) -> CommitResult:
        """Materialize a validated edit as Git commit material.

        Validates first (an invalid document raises and writes
        nothing), then persists the edited document at its repository
        path and executes the plan through the Batch 19 renderer:
        rendered files at each binding's render_target, the render
        manifest, optionally the commit message file, and the
        prepared commit reference in the result. The GitOps
        controller reconciles; the portal never applies.
        """
        try:
            self._plan_submitted(submitted)
        except ConfigRenderError as error:
            raise ConfigEditRejected(
                "submitted unified configuration document failed "
                "validation; nothing was written",
                details={"errors": [str(error)]},
            ) from error
        with self._commit_lock:
            self._document_path.parent.mkdir(
                parents=True, exist_ok=True
            )
            self._document_path.write_bytes(submitted)
            # Re-plan from the persisted path: deterministic
            # renderer, identical bytes, so the plan (and its digest)
            # match the validation pass while the commit message
            # names the real document file.
            plan = plan_render(
                self._document_path,
                self._contracts_dir,
                self._repo_root,
            )
            written = execute_plan(
                plan, self._repo_root, commit_message_out
            )
        document_relpath = self._document_path.relative_to(
            self._repo_root.resolve()
        ).as_posix()
        return CommitResult(
            commit_reference=_commit_ref_for(plan),
            commit_message=plan.commit_message,
            written_paths=(
                document_relpath,
                *(self._relative(path) for path in written),
            ),
        )

    def _relative(self, path: str) -> str:
        """Normalize an execute_plan path to repo-relative.

        execute_plan reports artifact paths repo-relative but the
        manifest (and any commit_message_out) as given, which may be
        absolute; the portal reports one consistent shape, matching
        changed_paths.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            return path
        resolved = candidate.resolve()
        root = self._repo_root.resolve()
        if resolved.is_relative_to(root):
            return resolved.relative_to(root).as_posix()
        return path
