"""`obskit drift` - rendered-versus-live diff surface (Batch 19 Task 3).

Implements the render-idempotency-check detection path of
contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml
(drift_detection): the unified document is re-planned through the
exact render pipeline (obskit.configrender.render.plan_render), and
every planned artifact's expected bytes - plus the render manifest,
the contract's drift-detection input surface - are compared against
the target tree's on-disk bytes. Divergences are emitted as the JSON
diff surface consumed by the TR-12 meta-monitoring alert path, using
the contract's required alert signal names:

- render-idempotency-violation: the live file exists, carries the
  generated-file header marker (or is the render manifest), and still
  differs - the rendered state was edited by hand or the renderer
  regressed on determinism.
- config-drift-detected-per-system: every other divergence - a file
  the renderer expects that is missing, or one that diverges without
  ever having carried the marker.

Determinism matches the renderer's invariants: canonical JSON (sorted
keys, two-space indent, trailing newline), stable path-sorted
ordering, no timestamps, hostnames, or random identifiers. Drift is
strictly read-only over the target tree - it never runs Git and never
writes a render target; the only optional write is the --report-out
copy of the report, contained inside the repository root exactly like
the renderer's --manifest-out.

Exit codes: 0 clean, 3 drift detected (EXIT_CHECK_CHANGED, mirroring
`obskit render --check`), 2 operator error.
"""

from __future__ import annotations

import hashlib
import sys
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

from obskit.configrender.models import (
    ConfigRenderError,
    EXIT_CHECK_CHANGED,
    EXIT_ERROR,
    EXIT_OK,
    MARKER,
    RenderPlan,
)
from obskit.configrender.render import (
    _assert_contained,
    plan_render,
)
from obskit.emit import canonical_json

# Report status values (top-level "status" key).
STATUS_CLEAN = "clean"
STATUS_DRIFT = "drift"

# Alert signal ids, exactly as fixed by the propagation contract's
# drift_detection.alerting.required_alert_signals. The third contract
# signal (reconcile-sync-failure) belongs to the GitOps controller's
# sync path, not to this rendered-versus-live comparison.
SIGNAL_IDEMPOTENCY_VIOLATION = "render-idempotency-violation"
SIGNAL_CONFIG_DRIFT = "config-drift-detected-per-system"

# actual_digest sentinel for a file the renderer expects but the
# target tree does not contain.
ABSENT = "absent"

# The render manifest is the renderer's own artifact, not a binding's;
# its drift entry carries these fixed attribution values.
MANIFEST_SYSTEM = "config-renderer"
MANIFEST_UNIFIED_KEY = "render-manifest"


@dataclass(frozen=True)
class DriftEntry:
    """One divergent path of the rendered-versus-live comparison."""

    path: str
    system: str
    unified_key: str
    expected_digest: str
    actual_digest: str
    signal: str


@dataclass(frozen=True)
class DriftReport:
    """The complete diff surface of one drift run.

    drifted is sorted by path; systems is the sorted unique set of
    system ids appearing in drifted (the per-system fan-out key of the
    config-drift-detected-per-system alert signal).
    """

    status: str
    document_digest: str
    schema_version: str
    drifted: tuple[DriftEntry, ...]
    systems: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "document_digest": self.document_digest,
            "schema_version": self.schema_version,
            "drifted": [
                {
                    "path": entry.path,
                    "system": entry.system,
                    "unified_key": entry.unified_key,
                    "expected_digest": entry.expected_digest,
                    "actual_digest": entry.actual_digest,
                    "signal": entry.signal,
                }
                for entry in self.drifted
            ],
            "systems": list(self.systems),
        }

    def to_json(self) -> str:
        return canonical_json(self.to_payload())


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_live(target: Path) -> bytes | None:
    """Bytes of the live file, or None when it does not exist."""
    if not target.is_file():
        return None
    return target.read_bytes()


def _signal_for(actual: bytes | None, is_manifest: bool) -> str:
    """Classify a divergence per the propagation contract.

    render-idempotency-violation requires the live file to exist AND
    to be renderer-owned state (it carries the generated-file header
    marker, or it is the render manifest itself); everything else -
    including a missing file - is per-system config drift.
    """
    if actual is None:
        return SIGNAL_CONFIG_DRIFT
    if is_manifest:
        return SIGNAL_IDEMPOTENCY_VIOLATION
    # YAML targets carry the marker as a comment line; owned JSON
    # artifacts carry it as their "marker" field. Both surface as the
    # marker substring in the live bytes.
    if MARKER in actual.decode("utf-8", errors="replace"):
        return SIGNAL_IDEMPOTENCY_VIOLATION
    return SIGNAL_CONFIG_DRIFT


def _entry(
    path: str,
    system: str,
    unified_key: str,
    expected: bytes,
    actual: bytes | None,
    is_manifest: bool,
) -> DriftEntry:
    return DriftEntry(
        path=path,
        system=system,
        unified_key=unified_key,
        expected_digest=_sha256_hex(expected),
        actual_digest=(
            ABSENT if actual is None else _sha256_hex(actual)
        ),
        signal=_signal_for(actual, is_manifest),
    )


def _manifest_report_path(plan: RenderPlan, repo_root: Path) -> str:
    """Repo-relative POSIX path of the manifest when it lands under
    the repository root (the default), else its literal path - so the
    drifted list stays uniformly path-sorted."""
    manifest = Path(plan.manifest_path).resolve()
    root = repo_root.resolve()
    if manifest.is_relative_to(root):
        return manifest.relative_to(root).as_posix()
    return plan.manifest_path


def compute_drift(
    document_path: Path,
    contracts_dir: Path,
    repo_root: Path,
) -> DriftReport:
    """Plan the render in memory and diff it against the target tree.

    Read-only over repo_root: plan_render never writes, and the
    comparison only reads. Raises ConfigRenderError when the document
    or its bindings are invalid (exactly as `obskit render` would).

    A path patched by several bindings has one expected byte content;
    its drift entry is attributed to the first contributor in the
    plan's stable (path, unified_key, system) order.
    """
    plan = plan_render(document_path, contracts_dir, repo_root)
    entries: list[DriftEntry] = []
    seen: set[str] = set()
    for artifact in plan.artifacts:
        if artifact.path in seen:
            continue
        seen.add(artifact.path)
        expected = artifact.content.encode("utf-8")
        actual = _read_live(repo_root / artifact.path)
        if actual == expected:
            continue
        entries.append(
            _entry(
                artifact.path,
                artifact.system,
                artifact.unified_key,
                expected,
                actual,
                is_manifest=False,
            )
        )
    expected = plan.manifest_content.encode("utf-8")
    actual = _read_live(Path(plan.manifest_path))
    if actual != expected:
        entries.append(
            _entry(
                _manifest_report_path(plan, repo_root),
                MANIFEST_SYSTEM,
                MANIFEST_UNIFIED_KEY,
                expected,
                actual,
                is_manifest=True,
            )
        )
    drifted = tuple(sorted(entries, key=lambda entry: entry.path))
    systems = tuple(
        sorted({entry.system for entry in drifted})
    )
    return DriftReport(
        status=STATUS_DRIFT if drifted else STATUS_CLEAN,
        document_digest=plan.document_digest,
        schema_version=plan.schema_version,
        drifted=drifted,
        systems=systems,
    )


def run(args: Namespace) -> int:
    """CLI entry point for `obskit drift`."""
    if not args.document:
        # No document-discovery default exists; the unified document
        # must be named explicitly.
        sys.stderr.write(
            "obskit drift: error: --document is required\n"
        )
        return EXIT_ERROR
    repo_root = Path(args.repo_root)
    try:
        report = compute_drift(
            Path(args.document),
            Path(args.contracts_dir),
            repo_root,
        )
        text = report.to_json()
        if args.report_out:
            # The report copy is a write like the renderer's
            # --manifest-out: it must land inside the repository root.
            report_out = Path(args.report_out)
            _assert_contained(
                report_out, repo_root, "drift report path"
            )
            report_out.parent.mkdir(parents=True, exist_ok=True)
            report_out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
    except ConfigRenderError as exc:
        sys.stderr.write(f"obskit drift: error: {exc}\n")
        return EXIT_ERROR
    except OSError as exc:
        sys.stderr.write(f"obskit drift: error: {exc}\n")
        return EXIT_ERROR
    if report.status == STATUS_CLEAN:
        return EXIT_OK
    return EXIT_CHECK_CHANGED
