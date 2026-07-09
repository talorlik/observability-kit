"""Unified document loading, schema validation, and cross-file rules.

The unified configuration document is consumed as JSON (ADR-0003; the
stdlib cannot parse YAML) and validated against
contracts/management/UNIFIED_CONFIG_SCHEMA_V1.json with the extended
obskit.install.contract subset validator. The four cross-file rules
the schema cannot express (renderer architecture contract,
cross_file_rules_enforced_before_write) are enforced here, before any
file is written:

- every binding's system is registered in the wrapped-system registry
- every present config leaf key has at least one binding
- every binding's unified_key resolves to a present leaf key
- every binding's native_path.repo_path falls under a registered
  config_surface path of its system

Write-target containment is enforced here too, before any write:
render_target must fall under the same registered config_surface
paths as repo_path (propagation contract pre_commit_validation,
render_target_within_registered_config_surface; TR-20), must never
point under gitops/charts/ (the read-only path), and neither
render_target nor repo_path may carry '.' or '..' segments - a
schema-valid document must not be able to steer a write outside the
config surface or the repository root (renderer architecture
contract, fail_if_render_writes_outside_config_surface).
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

from obskit.configrender.models import (
    Binding,
    ConfigRenderError,
    FORBIDDEN_WRITE_PREFIX,
    RegistryFacts,
)
from obskit.install.contract import load_schema, validate_answers
from obskit.install.models import InstallFlowError


def load_document(path: Path) -> tuple[dict[str, Any], bytes]:
    """Load the unified document; return (mapping, exact raw bytes).

    The raw bytes feed the document digest, so they are read once and
    never re-serialized.
    """
    if path.suffix.lower() in (".yaml", ".yml"):
        raise ConfigRenderError(
            f"unified document {path} is YAML; the renderer consumes "
            "JSON only (ADR-0003). Convert it first - the canonical "
            "sample's JSON twin is "
            "contracts/management/samples/VALID_UNIFIED_CONFIG.json"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ConfigRenderError(
            f"cannot read unified document {path}: {exc}"
        ) from exc
    try:
        loaded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigRenderError(
            f"malformed JSON in unified document {path}: {exc}"
        ) from exc
    if not isinstance(loaded, dict):
        raise ConfigRenderError(
            f"unified document {path} must be a JSON object"
        )
    return loaded, raw


def validate_document(
    document: dict[str, Any], schema_path: Path
) -> None:
    """Validate the document against the unified config schema."""
    try:
        schema = load_schema(schema_path)
        errors = validate_answers(document, schema)
    except InstallFlowError as exc:
        raise ConfigRenderError(str(exc)) from exc
    if errors:
        raise ConfigRenderError(
            "unified document failed schema validation: "
            + "; ".join(errors)
        )


def parse_bindings(document: dict[str, Any]) -> tuple[Binding, ...]:
    """Extract the typed bindings from a schema-valid document."""
    bindings: list[Binding] = []
    for item in document["bindings"]:
        native = item["native_path"]
        bindings.append(
            Binding(
                unified_key=item["unified_key"],
                system=item["system"],
                repo_path=native["repo_path"],
                locator=native["locator"],
                render_target=item["render_target"],
            )
        )
    return tuple(bindings)


def config_leaf_keys(config: dict[str, Any]) -> tuple[str, ...]:
    """Dotted paths of every leaf key present under config.

    A leaf is any non-mapping value; arrays (for example
    alerting.notification_channels) are leaves.
    """
    leaves: list[str] = []

    def walk(node: dict[str, Any], prefix: str) -> None:
        for key, value in node.items():
            dotted = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                walk(value, dotted)
            else:
                leaves.append(dotted)

    walk(config, "")
    return tuple(sorted(leaves))


def leaf_value(config: dict[str, Any], dotted: str) -> Any:
    """Resolve a dotted unified key to its config value."""
    node: Any = config
    for segment in dotted.split("."):
        if not isinstance(node, dict) or segment not in node:
            raise ConfigRenderError(
                f"unified key {dotted!r} does not resolve to a "
                "present config leaf"
            )
        node = node[segment]
    if isinstance(node, dict):
        raise ConfigRenderError(
            f"unified key {dotted!r} resolves to a mapping, not a "
            "leaf value"
        )
    return node


def _within_surface(repo_path: str, surface: str) -> bool:
    if surface.endswith("/"):
        return repo_path.startswith(surface)
    return repo_path == surface


def _has_dot_segments(path: str) -> bool:
    """True when any POSIX path segment is '.' or '..'.

    Checked on the raw segments, before any normalization, so a
    traversal attempt is rejected as written instead of being
    resolved away.
    """
    return any(
        part in (".", "..") for part in PurePosixPath(path).parts
    )


def _check_binding_path(
    label: str,
    field: str,
    path: str,
    surfaces: tuple[str, ...],
    system: str,
    violations: list[str],
) -> None:
    """Containment checks shared by repo_path and render_target."""
    if _has_dot_segments(path):
        violations.append(
            f"{label}: {field} {path!r} contains '.' or '..' path "
            "segments"
        )
        return
    if path.startswith(FORBIDDEN_WRITE_PREFIX):
        violations.append(
            f"{label}: {field} {path!r} points under the read-only "
            f"{FORBIDDEN_WRITE_PREFIX} tree"
        )
        return
    if not any(
        _within_surface(path, surface) for surface in surfaces
    ):
        violations.append(
            f"{label}: {field} {path!r} is outside every registered "
            f"config_surface path of system {system!r}"
        )


def enforce_cross_file_rules(
    document: dict[str, Any],
    bindings: tuple[Binding, ...],
    facts: RegistryFacts,
) -> None:
    """Enforce the four cross-file rules; raise with every violation."""
    violations: list[str] = []
    registered = set(facts.systems)
    config = document["config"]
    leaves = set(config_leaf_keys(config))
    bound_keys = {binding.unified_key for binding in bindings}

    for binding in bindings:
        label = f"binding {binding.unified_key} -> {binding.system}"
        if binding.system not in registered:
            violations.append(
                f"{label}: system {binding.system!r} is not "
                "registered in the wrapped-system registry"
            )
            continue
        if binding.unified_key not in leaves:
            violations.append(
                f"{label}: unified_key does not resolve to a leaf "
                "key present under config"
            )
        surfaces = facts.surfaces_for(binding.system)
        _check_binding_path(
            label,
            "native_path.repo_path",
            binding.repo_path,
            surfaces,
            binding.system,
            violations,
        )
        _check_binding_path(
            label,
            "render_target",
            binding.render_target,
            surfaces,
            binding.system,
            violations,
        )

    for leaf in sorted(leaves - bound_keys):
        violations.append(
            f"config leaf {leaf!r} has no propagation binding"
        )

    if violations:
        raise ConfigRenderError(
            "cross-file rule violation(s): " + "; ".join(violations)
        )
