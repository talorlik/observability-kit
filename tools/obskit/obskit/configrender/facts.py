"""Line-based fact extraction from the management-plane contracts.

The renderer needs two fact sets the stdlib cannot YAML-parse: the
registered system ids and config-surface paths from
contracts/management/WRAPPED_SYSTEM_REGISTRY_V1.yaml, and the render
strategy catalog from
contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml. Both are
extracted with the line-based stdlib technique established by
obskit.install.flow.load_contract_step_ids: only the exact keys and
indentation shapes those contracts fix are read, and a contract that
yields no facts fails loudly (ADR-0003).
"""

from __future__ import annotations

import re
from pathlib import Path

from obskit.configrender.models import (
    ConfigRenderError,
    RegistryFacts,
    StrategyEntry,
)

# Registry shapes: systems are "  - system: <id>" items under the
# top-level "systems:" key; surface paths are "- gitops/..." or
# "- contracts/..." items inside a system's config_surface block.
_SYSTEM_ITEM = re.compile(r"^  - system: ([a-z0-9]([a-z0-9-]*[a-z0-9])?)\s*$")
_SURFACE_KEY = re.compile(r"^    config_surface:\s*$")
_ENTRY_FIELD = re.compile(r"^    \S")
_SURFACE_PATH_ITEM = re.compile(
    r"^\s+- ((?:gitops|contracts)/\S*)\s*$"
)

# Strategy catalog shapes under render_strategies.bindings.
_BINDING_ITEM = re.compile(r"^    - unified_key: (\S+)\s*$")
_BINDING_FIELD = re.compile(
    r"^      (system|strategy|value_transform): (\S+)\s*$"
)


def _read_contract(path: Path, description: str) -> list[str]:
    if not path.is_file():
        raise ConfigRenderError(f"{description} not found: {path}")
    return path.read_text(encoding="utf-8").splitlines()


def load_registry_facts(registry_path: Path) -> RegistryFacts:
    """Extract system ids and config-surface paths from the registry."""
    systems: list[str] = []
    surfaces: list[tuple[str, str]] = []
    in_systems = False
    in_surface = False
    current_system: str | None = None
    lines = _read_contract(
        registry_path, "wrapped-system registry contract"
    )
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            in_systems = stripped == "systems:"
            in_surface = False
            current_system = None
            continue
        if not in_systems:
            continue
        system_match = _SYSTEM_ITEM.match(line)
        if system_match:
            current_system = system_match.group(1)
            systems.append(current_system)
            in_surface = False
            continue
        if _SURFACE_KEY.match(line):
            in_surface = True
            continue
        if _ENTRY_FIELD.match(line):
            # Any other 4-indent entry field ends the surface block.
            in_surface = False
            continue
        if in_surface and current_system is not None:
            path_match = _SURFACE_PATH_ITEM.match(line)
            if path_match:
                surfaces.append((current_system, path_match.group(1)))
    if not systems or not surfaces:
        raise ConfigRenderError(
            "wrapped-system registry contract "
            f"{registry_path} yields no parseable systems or "
            "config-surface paths"
        )
    return RegistryFacts(
        systems=tuple(systems), config_surfaces=tuple(surfaces)
    )


def load_strategy_catalog(
    contract_path: Path,
) -> dict[tuple[str, str], StrategyEntry]:
    """Extract the render strategy catalog, keyed by binding pair."""
    lines = _read_contract(
        contract_path, "renderer architecture contract"
    )
    in_render_strategies = False
    in_bindings = False
    current: dict[str, str] | None = None
    entries: list[StrategyEntry] = []

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        missing = sorted(
            {"unified_key", "system", "strategy", "value_transform"}
            - set(current)
        )
        if missing:
            raise ConfigRenderError(
                "renderer architecture contract binding for "
                f"{current.get('unified_key')!r} is missing "
                f"field(s) {missing}"
            )
        entries.append(
            StrategyEntry(
                unified_key=current["unified_key"],
                system=current["system"],
                strategy=current["strategy"],
                value_transform=current["value_transform"],
            )
        )
        current = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            flush()
            in_render_strategies = stripped == "render_strategies:"
            in_bindings = False
            continue
        if not in_render_strategies:
            continue
        if re.match(r"^  \S", line):
            flush()
            in_bindings = stripped == "bindings:"
            continue
        if not in_bindings:
            continue
        item_match = _BINDING_ITEM.match(line)
        if item_match:
            flush()
            current = {"unified_key": item_match.group(1)}
            continue
        field_match = _BINDING_FIELD.match(line)
        if field_match and current is not None:
            current[field_match.group(1)] = field_match.group(2)
    flush()
    if not entries:
        raise ConfigRenderError(
            "renderer architecture contract "
            f"{contract_path} yields no parseable "
            "render_strategies.bindings entries"
        )
    catalog: dict[tuple[str, str], StrategyEntry] = {}
    for entry in entries:
        key = (entry.unified_key, entry.system)
        if key in catalog:
            raise ConfigRenderError(
                "renderer architecture contract declares duplicate "
                f"strategy binding for {key}"
            )
        catalog[key] = entry
    return catalog
