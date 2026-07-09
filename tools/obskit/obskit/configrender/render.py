"""The `obskit render` pipeline (Batch 19 Task 2, TR-20).

Executes the render stage of
contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml: the
schema-validated unified document plus its propagation bindings become
native configuration files at each binding's render_target, rendered
through the strategy the renderer architecture contract catalogs for
that (unified_key, system) pair. Planning is fully in-memory - every
target is read and patched before the first write - so a failing
render leaves the tree untouched, and --check is the same plan
compared against the tree without writing.

Determinism invariants (renderer architecture contract, outputs):
byte-identical output for identical document bytes, no timestamps,
hostnames, or random identifiers, stable ordering everywhere. The
render manifest (gitops/UNIFIED_CONFIG_RENDER_MANIFEST.json) is the
sibling marker carrier for comment-incapable formats and the drift
detection input surface; the prepared commit message carries the two
required trailers. The renderer never runs Git commands and never
writes under gitops/charts/.
"""

from __future__ import annotations

import hashlib
import sys
from argparse import Namespace
from pathlib import Path, PurePosixPath
from typing import Any

from obskit.configrender.document import (
    leaf_value,
    load_document,
    parse_bindings,
    validate_document,
    enforce_cross_file_rules,
)
from obskit.configrender.facts import (
    load_registry_facts,
    load_strategy_catalog,
)
from obskit.configrender.models import (
    Binding,
    ConfigRenderError,
    DEFAULT_MANIFEST_RELPATH,
    EXIT_CHECK_CHANGED,
    EXIT_ERROR,
    EXIT_OK,
    FORBIDDEN_WRITE_PREFIX,
    MANIFEST_SCHEMA_VERSION,
    MARKER,
    PlannedArtifact,
    RecordedFile,
    RegistryFacts,
    RenderPlan,
    SkippedTarget,
    StrategyEntry,
    STRATEGY_JSON_PATH_PATCH,
    STRATEGY_OWNED_ARTIFACT,
    STRATEGY_PRESENCE_GATED,
    STRATEGY_YAML_LINE_PATCH,
    TRAILER_DOCUMENT_DIGEST,
    TRAILER_SCHEMA_VERSION,
)
from obskit.configrender.patch import (
    apply_sync_policy,
    insert_marker,
    json_path_patch,
    set_top_level_scalar,
    set_yaml_scalar,
    yaml_scalar,
)
from obskit.emit import canonical_json

# Relative contract paths under --contracts-dir.
_SCHEMA_RELPATH = "management/UNIFIED_CONFIG_SCHEMA_V1.json"
_REGISTRY_RELPATH = "management/WRAPPED_SYSTEM_REGISTRY_V1.yaml"
_ARCHITECTURE_RELPATH = (
    "management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml"
)

# Owned-artifact filenames, keyed by the catalog's value_transform.
_OWNED_FILENAMES = {
    "channels-to-destination-catalog": "notification_destinations.json",
    "provisioning-state-catalog": "provisioning_state.json",
    "isolation-class-defaults": "default_isolation_class.json",
}


class _PlanState:
    """Mutable accumulator while bindings are rendered in memory."""

    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.texts: dict[str, str] = {}
        self.contributors: dict[
            str, list[tuple[Binding, StrategyEntry]]
        ] = {}
        self.skipped: list[SkippedTarget] = []
        self.recorded: dict[str, str] = {}

    def load(self, path: str, context: str) -> str:
        if path in self.texts:
            return self.texts[path]
        target = self.repo_root / path
        if not target.is_file():
            raise ConfigRenderError(
                f"{context}: render target {path} does not exist "
                "under the repository root"
            )
        return target.read_text(encoding="utf-8")

    def contribute(
        self,
        path: str,
        content: str,
        binding: Binding,
        entry: StrategyEntry,
    ) -> None:
        _assert_write_scope(path, self.repo_root)
        self.texts[path] = content
        self.contributors.setdefault(path, []).append(
            (binding, entry)
        )


def _has_dot_segments(path: str) -> bool:
    return any(
        part in (".", "..") for part in PurePosixPath(path).parts
    )


def _assert_contained(
    candidate: Path, repo_root: Path, label: str
) -> None:
    """Require a write destination to resolve inside the repo root.

    Defense in depth behind the cross-file rules: symlinks and any
    traversal the raw-segment check missed are caught after full
    filesystem resolution.
    """
    resolved = candidate.resolve()
    if not resolved.is_relative_to(repo_root.resolve()):
        raise ConfigRenderError(
            f"{label} {str(candidate)!r} resolves outside the "
            "repository root; refusing to write"
        )


def _assert_write_scope(path: str, repo_root: Path) -> None:
    # The gitops/-only bound is contract-fixed: the unified schema's
    # render_target pattern is ^gitops/... (UNIFIED_CONFIG_SCHEMA_V1
    # .json). Registry config surfaces may also cover contracts/, but
    # those are read-side (repo_path) surfaces, never write targets.
    if (
        not path.startswith("gitops/")
        or path.startswith(FORBIDDEN_WRITE_PREFIX)
        or _has_dot_segments(path)
    ):
        raise ConfigRenderError(
            f"render target {path!r} is outside the renderer's "
            "write scope (gitops/ excluding gitops/charts/, no "
            "'.'/'..' segments)"
        )
    _assert_contained(repo_root / path, repo_root, "render target")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _dir_target(binding: Binding, context: str) -> str:
    if not binding.render_target.endswith("/"):
        raise ConfigRenderError(
            f"{context}: strategy requires a directory render_target "
            f"(trailing '/'), got {binding.render_target!r}"
        )
    return binding.render_target


def _list_dir(
    repo_root: Path, rel_dir: str, context: str
) -> list[str]:
    """Repo-relative POSIX paths of every file under rel_dir,
    recursively, sorted."""
    root = repo_root / rel_dir
    if not root.is_dir():
        raise ConfigRenderError(
            f"{context}: render target directory {rel_dir} does not "
            "exist under the repository root"
        )
    found = [
        (rel_dir + entry.relative_to(root).as_posix())
        for entry in sorted(root.rglob("*"))
        if entry.is_file()
    ]
    return found


def _transform_days(value: Any, context: str) -> str:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigRenderError(
            f"{context}: days-to-opensearch-age requires an integer "
            f"day count, got {value!r}"
        )
    return f"{value}d"


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigRenderError(
            f"{context}: expected a boolean unified value, got "
            f"{value!r}"
        )
    return value


def _render_json_path_patch(
    state: _PlanState,
    binding: Binding,
    entry: StrategyEntry,
    value: Any,
    context: str,
) -> None:
    if entry.value_transform == "days-to-opensearch-age":
        patch_value: Any = _transform_days(value, context)
    elif entry.value_transform == "identity":
        patch_value = value
    else:
        raise ConfigRenderError(
            f"{context}: json-path-patch does not implement "
            f"value_transform {entry.value_transform!r}"
        )
    text = state.load(binding.render_target, context)
    patched = json_path_patch(
        text, binding.locator, patch_value, context
    )
    state.contribute(binding.render_target, patched, binding, entry)


def _render_yaml_line_patch(
    state: _PlanState,
    binding: Binding,
    entry: StrategyEntry,
    value: Any,
    context: str,
) -> None:
    # Dispatch on the catalog's value_transform wherever it is
    # distinctive, so the contract stays the single source of truth.
    if entry.value_transform == "sync-policy-block":
        enabled = _require_bool(value, context)
        target_dir = _dir_target(binding, context)
        applications = [
            path
            for path in _list_dir(
                state.repo_root, target_dir, context
            )
            if path.endswith(".yaml")
            and "/" not in path[len(target_dir) :]
        ]
        if not applications:
            raise ConfigRenderError(
                f"{context}: no Application manifests (*.yaml) under "
                f"{target_dir}"
            )
        for path in applications:
            text = state.load(path, context)
            patched = apply_sync_policy(
                text, enabled, f"{context} [{path}]"
            )
            state.contribute(path, patched, binding, entry)
        return
    if entry.value_transform == "top-level-isolation-class-key":
        text = state.load(binding.render_target, context)
        patched = set_top_level_scalar(
            text,
            "default_isolation_class",
            yaml_scalar(value, context),
            context,
        )
        state.contribute(
            binding.render_target, patched, binding, entry
        )
        return
    if entry.value_transform != "identity":
        raise ConfigRenderError(
            f"{context}: yaml-line-patch does not implement "
            f"value_transform {entry.value_transform!r}"
        )
    text = state.load(binding.render_target, context)
    adopted = insert_marker(text, context)
    patched = set_yaml_scalar(
        adopted,
        binding.locator,
        yaml_scalar(value, context),
        context,
    )
    state.contribute(binding.render_target, patched, binding, entry)


def _record_directory(
    state: _PlanState,
    target_dir: str,
    owned_filename: str,
    context: str,
) -> None:
    owned_path = target_dir + owned_filename
    for path in _list_dir(state.repo_root, target_dir, context):
        if path == owned_path:
            continue
        digest = _sha256_hex(
            (state.repo_root / path).read_bytes()
        )
        state.recorded.setdefault(path, digest)


def _render_owned_artifact(
    state: _PlanState,
    binding: Binding,
    entry: StrategyEntry,
    value: Any,
    context: str,
) -> None:
    target_dir = _dir_target(binding, context)
    filename = _OWNED_FILENAMES.get(entry.value_transform)
    if filename is None:
        raise ConfigRenderError(
            f"{context}: owned-artifact does not implement "
            f"value_transform {entry.value_transform!r}"
        )
    if entry.value_transform == "channels-to-destination-catalog":
        if not isinstance(value, list):
            raise ConfigRenderError(
                f"{context}: expected a channel list, got {value!r}"
            )
        channels = sorted(
            (
                {
                    "kind": channel["kind"],
                    "name": channel["name"],
                }
                for channel in value
            ),
            key=lambda channel: channel["name"],
        )
        payload: dict[str, Any] = {"channels": channels}
    elif entry.value_transform == "provisioning-state-catalog":
        enabled = _require_bool(value, context)
        bundles = [
            {
                "name": path[len(target_dir) :],
                "sha256": _sha256_hex(
                    (state.repo_root / path).read_bytes()
                ),
            }
            for path in _list_dir(
                state.repo_root, target_dir, context
            )
            if path.endswith(".ndjson")
        ]
        payload = {"bundles": bundles, "enabled": enabled}
    else:  # isolation-class-defaults
        if not isinstance(value, str):
            raise ConfigRenderError(
                f"{context}: expected an isolation class string, "
                f"got {value!r}"
            )
        payload = {"default_isolation_class": value}
    payload["marker"] = MARKER
    payload["schema_version"] = MANIFEST_SCHEMA_VERSION
    content = canonical_json(payload)
    _record_directory(state, target_dir, filename, context)
    state.contribute(target_dir + filename, content, binding, entry)


def _render_presence_gated(
    state: _PlanState,
    binding: Binding,
    entry: StrategyEntry,
    value: Any,
    context: str,
) -> None:
    gate = _require_bool(value, context)
    if not gate:
        state.skipped.append(
            SkippedTarget(
                path=binding.render_target,
                unified_key=binding.unified_key,
                system=binding.system,
                strategy=entry.strategy,
                reason="gate-false",
            )
        )
        return
    text = state.load(binding.render_target, context)
    adopted = insert_marker(text, context)
    state.contribute(binding.render_target, adopted, binding, entry)


_STRATEGY_HANDLERS = {
    STRATEGY_JSON_PATH_PATCH: _render_json_path_patch,
    STRATEGY_YAML_LINE_PATCH: _render_yaml_line_patch,
    STRATEGY_OWNED_ARTIFACT: _render_owned_artifact,
    STRATEGY_PRESENCE_GATED: _render_presence_gated,
}


def _build_manifest(
    document_digest: str,
    artifacts: tuple[PlannedArtifact, ...],
    skipped: tuple[SkippedTarget, ...],
    recorded: tuple[RecordedFile, ...],
) -> str:
    return canonical_json(
        {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "document_digest": document_digest,
            "marker": MARKER,
            "artifacts": [
                {
                    "path": artifact.path,
                    "sha256": _sha256_hex(
                        artifact.content.encode("utf-8")
                    ),
                    "strategy": artifact.strategy,
                    "system": artifact.system,
                    "unified_key": artifact.unified_key,
                }
                for artifact in artifacts
            ],
            "skipped": [
                {
                    "path": skip.path,
                    "reason": skip.reason,
                    "strategy": skip.strategy,
                    "system": skip.system,
                    "unified_key": skip.unified_key,
                }
                for skip in skipped
            ],
            "recorded": [
                {"path": record.path, "sha256": record.sha256}
                for record in recorded
            ],
        }
    )


def _build_commit_message(
    document_name: str,
    schema_version: str,
    digest_hex: str,
    artifact_count: int,
) -> str:
    subject = (
        "config(render): propagate unified configuration "
        f"{digest_hex[:12]}"
    )
    body = f"document {document_name}; artifacts {artifact_count}"
    return (
        f"{subject}\n"
        "\n"
        f"{body}\n"
        "\n"
        f"{TRAILER_SCHEMA_VERSION}: {schema_version}\n"
        f"{TRAILER_DOCUMENT_DIGEST}: sha256:{digest_hex}\n"
    )


def plan_render(
    document_path: Path,
    contracts_dir: Path,
    repo_root: Path,
    manifest_out: Path | None = None,
) -> RenderPlan:
    """Validate, enforce cross-file rules, and render fully in memory.

    Raises ConfigRenderError on any violation; nothing is written.
    The returned plan feeds execute_plan (write) or changed_paths
    (--check), which is also the interface `obskit drift` and
    `obskit rollback` (Tasks 3-4) build on.
    """
    document, raw = load_document(document_path)
    validate_document(document, contracts_dir / _SCHEMA_RELPATH)
    facts: RegistryFacts = load_registry_facts(
        contracts_dir / _REGISTRY_RELPATH
    )
    catalog = load_strategy_catalog(
        contracts_dir / _ARCHITECTURE_RELPATH
    )
    bindings = parse_bindings(document)
    enforce_cross_file_rules(document, bindings, facts)

    state = _PlanState(repo_root)
    ordered = sorted(
        bindings,
        key=lambda binding: (
            binding.render_target,
            binding.unified_key,
            binding.system,
        ),
    )
    for binding in ordered:
        pair = (binding.unified_key, binding.system)
        entry = catalog.get(pair)
        if entry is None:
            raise ConfigRenderError(
                f"binding {pair} has no entry in the render strategy "
                "catalog "
                "(RENDERER_ARCHITECTURE_CONTRACT_V1.yaml); an "
                "uncataloged binding fails the render"
            )
        handler = _STRATEGY_HANDLERS.get(entry.strategy)
        if handler is None:
            raise ConfigRenderError(
                f"binding {pair} declares unimplemented strategy "
                f"{entry.strategy!r}"
            )
        context = (
            f"render {binding.unified_key} -> {binding.system}"
        )
        value = leaf_value(document["config"], binding.unified_key)
        handler(state, binding, entry, value, context)

    artifacts = tuple(
        sorted(
            (
                PlannedArtifact(
                    path=path,
                    content=state.texts[path],
                    strategy=entry.strategy,
                    unified_key=binding.unified_key,
                    system=binding.system,
                )
                for path, contributions in state.contributors.items()
                for binding, entry in contributions
            ),
            key=lambda artifact: (
                artifact.path,
                artifact.unified_key,
                artifact.system,
            ),
        )
    )
    skipped = tuple(
        sorted(
            state.skipped,
            key=lambda skip: (skip.path, skip.unified_key),
        )
    )
    recorded = tuple(
        RecordedFile(path=path, sha256=digest)
        for path, digest in sorted(state.recorded.items())
    )
    digest_hex = _sha256_hex(raw)
    document_digest = f"sha256:{digest_hex}"
    manifest_content = _build_manifest(
        document_digest, artifacts, skipped, recorded
    )
    manifest_path = (
        manifest_out
        if manifest_out is not None
        else repo_root / DEFAULT_MANIFEST_RELPATH
    )
    # The manifest is a write like any other: it must land inside the
    # repository root even when --manifest-out overrides its location.
    _assert_contained(manifest_path, repo_root, "manifest path")
    schema_version = document["schema_version"]
    unique_paths: dict[str, None] = {}
    for artifact in artifacts:
        unique_paths.setdefault(artifact.path, None)
    commit_message = _build_commit_message(
        document_path.name,
        schema_version,
        digest_hex,
        len(unique_paths),
    )
    return RenderPlan(
        schema_version=schema_version,
        document_digest=document_digest,
        artifacts=artifacts,
        skipped=skipped,
        recorded=recorded,
        manifest_path=str(manifest_path),
        manifest_content=manifest_content,
        commit_message=commit_message,
    )


def changed_paths(
    plan: RenderPlan, repo_root: Path
) -> tuple[str, ...]:
    """Targets whose current bytes differ from the planned bytes."""
    changed: list[str] = []
    seen: set[str] = set()
    for artifact in plan.artifacts:
        if artifact.path in seen:
            continue
        seen.add(artifact.path)
        target = repo_root / artifact.path
        expected = artifact.content.encode("utf-8")
        if not target.is_file() or target.read_bytes() != expected:
            changed.append(artifact.path)
    manifest = Path(plan.manifest_path)
    expected = plan.manifest_content.encode("utf-8")
    if not manifest.is_file() or manifest.read_bytes() != expected:
        # Report the manifest repo-relative like every artifact path
        # (mirrors rollback._relative_paths) so `obskit render
        # --check` output is consistent regardless of how --repo-root
        # was spelled.
        resolved = manifest.resolve()
        root = repo_root.resolve()
        changed.append(
            resolved.relative_to(root).as_posix()
            if resolved.is_relative_to(root)
            else plan.manifest_path
        )
    return tuple(changed)


def execute_plan(
    plan: RenderPlan,
    repo_root: Path,
    commit_message_out: Path | None = None,
) -> tuple[str, ...]:
    """Write the planned artifacts, manifest, and commit message."""
    if commit_message_out is not None:
        _assert_contained(
            commit_message_out, repo_root, "commit message path"
        )
    written: list[str] = []
    seen: set[str] = set()
    for artifact in plan.artifacts:
        if artifact.path in seen:
            continue
        seen.add(artifact.path)
        target = repo_root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(artifact.content.encode("utf-8"))
        written.append(artifact.path)
    manifest = Path(plan.manifest_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(plan.manifest_content.encode("utf-8"))
    written.append(plan.manifest_path)
    if commit_message_out is not None:
        commit_message_out.parent.mkdir(parents=True, exist_ok=True)
        commit_message_out.write_bytes(
            plan.commit_message.encode("utf-8")
        )
        written.append(str(commit_message_out))
    return tuple(written)


def run(args: Namespace) -> int:
    """CLI entry point for `obskit render`."""
    repo_root = Path(args.repo_root)
    contracts_dir = Path(args.contracts_dir)
    manifest_out = (
        Path(args.manifest_out) if args.manifest_out else None
    )
    commit_message_out = (
        Path(args.commit_message_out)
        if args.commit_message_out
        else None
    )
    try:
        plan = plan_render(
            Path(args.document), contracts_dir, repo_root, manifest_out
        )
        if args.check:
            changed = changed_paths(plan, repo_root)
            if changed:
                for path in changed:
                    sys.stdout.write(f"would change: {path}\n")
                return EXIT_CHECK_CHANGED
            sys.stdout.write(
                "no diff, no commit: rendered targets already match "
                "the unified document\n"
            )
            return EXIT_OK
        execute_plan(plan, repo_root, commit_message_out)
    except ConfigRenderError as exc:
        sys.stderr.write(f"obskit render: error: {exc}\n")
        return EXIT_ERROR
    sys.stdout.write(
        f"rendered {len(plan.unique_artifact_paths())} artifact(s), "
        f"{len(plan.skipped)} skipped; manifest "
        f"{plan.manifest_path}\n"
    )
    return EXIT_OK
