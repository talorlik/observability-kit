"""Target-preserving patch primitives for the config renderer.

Implements the byte-level halves of the json-path-patch and
yaml-line-patch strategies from
contracts/management/RENDERER_ARCHITECTURE_CONTRACT_V1.yaml:

- JSON targets are stdlib-parsed, the locator path is set, and the
  file is re-emitted canonically through obskit.emit.canonical_json
  (sorted keys, two-space indent, trailing newline).
- YAML targets are patched line-based: indentation-aware scalar
  replacement at a dotted locator path, block insertion or removal
  only for the contract-fixed spec.syncPolicy.automated block, and
  header-marker adoption as a leading comment. Every other byte,
  including comments, is preserved. The patcher handles the bounded
  structural subset the repo-owned values files use (plain block
  mappings with unique keys per level) and fails loudly on anything
  else (ADR-0003 trade-off analysis).

Mapping keys may themselves contain dots (grafana.ini), so dotted
locators are resolved by longest-prefix matching against the keys
actually present at each level, never by naive splitting.
"""

from __future__ import annotations

import json
import re
from typing import Any

from obskit.configrender.models import ConfigRenderError, MARKER_COMMENT
from obskit.emit import canonical_json

# A block-mapping key line: indentation, the key token, a colon
# followed by end-of-line or whitespace. Key tokens cover the
# repo-owned values files (letters, digits, dot, underscore, hyphen,
# slash).
_KEY_LINE = re.compile(r"^(\s*)([A-Za-z0-9_./-]+):(?=\s|$)")

# The scalar remainder after "key:": mandatory value, optional
# trailing comment.
_SCALAR_REST = re.compile(r"^(\s+)(\S[^#]*?)?(\s*#.*)?$")

# Bare YAML scalars that need no quoting and cannot be misread as a
# different type. Reserved words stay forbidden so a rendered string
# never silently becomes a boolean or null.
_BARE_STRING = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_./-]*$")
_RESERVED_WORDS = frozenset(
    {"true", "false", "yes", "no", "on", "off", "null", "~"}
)

# Locator segments for JSON targets: a field name with optional [n]
# index suffixes (policy.states[0].conditions...).
_JSON_SEGMENT = re.compile(r"^([A-Za-z0-9_]+)((?:\[\d+\])*)$")
_JSON_INDEX = re.compile(r"\[(\d+)\]")

# Existing values the scalar patcher may replace. YAML indicator
# characters that open a block scalar (| >), an anchor or alias
# (& *), a quoted scalar (" '), or a flow collection ({ [) mean the
# value is not a plain scalar: replacing it line-based would orphan a
# block body, delete an anchor with live aliases, or corrupt quoting,
# so the patcher fails loudly instead (ADR-0003,
# bounded_structural_subset: fail-loudly-on-unsupported-structure).
_FORBIDDEN_VALUE_LEADS = frozenset("|>&*\"'{[")
_PLAIN_EXISTING_VALUE = re.compile(r"^[A-Za-z0-9._/:@+-]+$")


def yaml_scalar(value: Any, context: str) -> str:
    """Render a unified value as a deterministic bare YAML scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # repr is the shortest round-trip form: deterministic for
        # identical document bytes, locale-independent.
        return repr(value)
    if isinstance(value, str):
        if (
            _BARE_STRING.match(value)
            and value.lower() not in _RESERVED_WORDS
        ):
            return value
        raise ConfigRenderError(
            f"{context}: string value {value!r} is not a safe bare "
            "YAML scalar; the bounded patcher refuses to guess a "
            "quoting form"
        )
    raise ConfigRenderError(
        f"{context}: value of type {type(value).__name__} cannot be "
        "rendered as a YAML scalar"
    )


def _split_lines(text: str, context: str) -> list[str]:
    if "\r" in text:
        raise ConfigRenderError(
            f"{context}: file contains carriage returns; the bounded "
            "patcher only handles LF line endings"
        )
    if not text.endswith("\n"):
        raise ConfigRenderError(
            f"{context}: file does not end with a newline; the "
            "bounded patcher only handles newline-terminated YAML"
        )
    return text.split("\n")


def insert_marker(text: str, context: str) -> str:
    """Adopt a YAML file: ensure the header marker is line one."""
    lines = _split_lines(text, context)
    if lines and lines[0] == MARKER_COMMENT:
        return text
    return MARKER_COMMENT + "\n" + text


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _is_content(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and not stripped.startswith("#")


def _children(
    lines: list[str], lo: int, hi: int, context: str
) -> tuple[int, list[tuple[int, str]]]:
    """Mapping keys of the block spanning lines[lo:hi].

    Returns (child indent, [(line index, key), ...]). The child
    indent is fixed by the first content line; deeper lines belong to
    child blocks and are skipped. A content line at the child indent
    that is not a mapping key (for example a sequence item) is a
    structure the bounded patcher does not understand.
    """
    child_indent = -1
    entries: list[tuple[int, str]] = []
    for index in range(lo, hi):
        line = lines[index]
        if not _is_content(line):
            continue
        indent = _indent_of(line)
        if child_indent < 0:
            child_indent = indent
        if indent < child_indent:
            break
        if indent > child_indent:
            continue
        key_match = _KEY_LINE.match(line)
        if not key_match:
            raise ConfigRenderError(
                f"{context}: line {index + 1} is not a block-mapping "
                "key; the bounded YAML patcher cannot descend this "
                "structure"
            )
        entries.append((index, key_match.group(2)))
    # Per-level key uniqueness: silently patching the first of two
    # duplicate keys would guess which one the locator means.
    keys_seen: set[str] = set()
    for _, key in entries:
        if key in keys_seen:
            raise ConfigRenderError(
                f"{context}: duplicate mapping key {key!r} at one "
                "level; the bounded YAML patcher refuses ambiguous "
                "structure"
            )
        keys_seen.add(key)
    return child_indent, entries


def _block_end(
    lines: list[str], entry_index: int, indent: int, hi: int
) -> int:
    """End (exclusive) of the block owned by the key at entry_index."""
    for index in range(entry_index + 1, hi):
        line = lines[index]
        if _is_content(line) and _indent_of(line) <= indent:
            return index
    return hi


def _locate(
    lines: list[str],
    lo: int,
    hi: int,
    dotted: str,
    context: str,
) -> int:
    """Line index of the scalar at dotted, longest-prefix matched."""
    child_indent, entries = _children(lines, lo, hi, context)
    if not entries:
        raise ConfigRenderError(
            f"{context}: locator {dotted!r} not found (empty block)"
        )
    for index, key in entries:
        if key == dotted:
            return index
    prefixed = [
        (index, key)
        for index, key in entries
        if dotted.startswith(key + ".")
    ]
    if not prefixed:
        raise ConfigRenderError(
            f"{context}: locator segment {dotted!r} matches no key "
            f"at this level (keys: {[key for _, key in entries]})"
        )
    # Longest key wins so dotted keys (grafana.ini) beat shorter
    # prefixes; per-level key uniqueness makes this unambiguous.
    index, key = max(prefixed, key=lambda item: len(item[1]))
    end = _block_end(lines, index, child_indent, hi)
    return _locate(
        lines, index + 1, end, dotted[len(key) + 1 :], context
    )


def _replace_scalar_line(
    line: str, rendered: str, context: str
) -> str:
    key_match = _KEY_LINE.match(line)
    if key_match is None:
        raise ConfigRenderError(
            f"{context}: internal locator resolution returned a "
            "non-key line"
        )
    head = line[: key_match.end()]
    rest = line[key_match.end() :]
    rest_match = _SCALAR_REST.match(rest)
    if rest_match is None or rest_match.group(2) is None:
        raise ConfigRenderError(
            f"{context}: locator points at a nested block, not a "
            "scalar value"
        )
    existing = rest_match.group(2)
    if (
        existing[0] in _FORBIDDEN_VALUE_LEADS
        or not _PLAIN_EXISTING_VALUE.match(existing)
    ):
        raise ConfigRenderError(
            f"{context}: existing value {existing!r} is not a plain "
            "scalar (block scalars, anchors/aliases, quoted values, "
            "and flow collections are outside the bounded patcher)"
        )
    comment = rest_match.group(3) or ""
    return f"{head} {rendered}{comment}"


def set_yaml_scalar(
    text: str, dotted: str, rendered: str, context: str
) -> str:
    """Replace the scalar at a dotted locator path, byte-preserving."""
    lines = _split_lines(text, context)
    index = _locate(lines, 0, len(lines), dotted, context)
    lines[index] = _replace_scalar_line(
        lines[index], rendered, context
    )
    return "\n".join(lines)


def set_top_level_scalar(
    text: str, key: str, rendered: str, context: str
) -> str:
    """Set or insert a top-level scalar key (after marker adoption).

    Used for tenancy.default_isolation_class on the spaces file: the
    key is replaced in place when present, otherwise inserted directly
    below the header marker so re-renders are byte-stable.
    """
    adopted = insert_marker(text, context)
    lines = _split_lines(adopted, context)
    for index, line in enumerate(lines):
        if not _is_content(line) or line.startswith(" "):
            continue
        key_match = _KEY_LINE.match(line)
        if key_match and key_match.group(2) == key:
            lines[index] = _replace_scalar_line(
                line, rendered, context
            )
            return "\n".join(lines)
    lines.insert(1, f"{key}: {rendered}")
    return "\n".join(lines)


def apply_sync_policy(
    text: str, enabled: bool, context: str
) -> str:
    """Ensure or remove the contract-fixed syncPolicy.automated block.

    When enabled, spec.syncPolicy.automated is guaranteed to be
    exactly the contract-fixed block (prune: true, selfHeal: true),
    inserted canonically indented when absent. When disabled, the
    automated block is removed (and an emptied syncPolicy key with
    it). All other bytes are preserved; marker adoption included.
    """
    adopted = insert_marker(text, context)
    lines = _split_lines(adopted, context)
    if any(line.strip() == "---" for line in lines):
        raise ConfigRenderError(
            f"{context}: multi-document YAML is outside the bounded "
            "sync-policy patcher"
        )
    top_indent, top_entries = _children(
        lines, 0, len(lines), context
    )
    spec = [
        (index, key) for index, key in top_entries if key == "spec"
    ]
    if not spec:
        raise ConfigRenderError(
            f"{context}: no top-level spec key; not an Application "
            "manifest the bounded patcher understands"
        )
    spec_index = spec[0][0]
    spec_end = _block_end(
        lines, spec_index, top_indent, len(lines)
    )
    spec_indent, spec_entries = _children(
        lines, spec_index + 1, spec_end, context
    )
    if spec_indent < 0:
        raise ConfigRenderError(
            f"{context}: top-level spec block is empty"
        )
    sync = [
        (index, key)
        for index, key in spec_entries
        if key == "syncPolicy"
    ]

    def automated_block(indent: int) -> list[str]:
        pad = " " * indent
        return [
            f"{pad}automated:",
            f"{pad}  prune: true",
            f"{pad}  selfHeal: true",
        ]

    if not sync:
        if not enabled:
            return "\n".join(lines)
        pad = " " * spec_indent
        insertion = [f"{pad}syncPolicy:"] + automated_block(
            spec_indent + 2
        )
        # Insert after the last content line of the spec block so a
        # trailing blank stays trailing.
        anchor = spec_end
        while anchor - 1 > spec_index and not _is_content(
            lines[anchor - 1]
        ):
            anchor -= 1
        lines[anchor:anchor] = insertion
        return "\n".join(lines)

    sync_index = sync[0][0]
    sync_end = _block_end(lines, sync_index, spec_indent, spec_end)
    sync_indent, sync_entries = _children(
        lines, sync_index + 1, sync_end, context
    )
    automated = [
        (index, key)
        for index, key in sync_entries
        if key == "automated"
    ]
    if enabled:
        block = automated_block(
            sync_indent if sync_indent >= 0 else spec_indent + 2
        )
        if automated:
            auto_index = automated[0][0]
            auto_end = _block_end(
                lines, auto_index, sync_indent, sync_end
            )
            lines[auto_index:auto_end] = block
        else:
            lines[sync_index + 1 : sync_index + 1] = block
        return "\n".join(lines)
    if automated:
        auto_index = automated[0][0]
        auto_end = _block_end(
            lines, auto_index, sync_indent, sync_end
        )
        del lines[auto_index:auto_end]
        if len(sync_entries) == 1:
            # automated was syncPolicy's only child; drop the now
            # childless key to keep the manifest valid YAML.
            del lines[sync_index]
    return "\n".join(lines)


def _parse_json_locator(
    locator: str, context: str
) -> list[str | int]:
    segments: list[str | int] = []
    for part in locator.split("."):
        segment_match = _JSON_SEGMENT.match(part)
        if segment_match is None:
            raise ConfigRenderError(
                f"{context}: JSON locator segment {part!r} is not "
                "'<name>' or '<name>[<index>]'"
            )
        segments.append(segment_match.group(1))
        for index in _JSON_INDEX.findall(segment_match.group(2)):
            segments.append(int(index))
    return segments


def json_path_patch(
    text: str, locator: str, value: Any, context: str
) -> str:
    """Set a locator path in a JSON target; re-emit canonically."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ConfigRenderError(
            f"{context}: render target is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigRenderError(
            f"{context}: JSON render target root must be an object"
        )
    segments = _parse_json_locator(locator, context)
    node: Any = data
    for segment in segments[:-1]:
        if isinstance(segment, str):
            if not isinstance(node, dict) or segment not in node:
                raise ConfigRenderError(
                    f"{context}: locator {locator!r} does not "
                    f"resolve at segment {segment!r}"
                )
            node = node[segment]
        else:
            if not isinstance(node, list) or segment >= len(node):
                raise ConfigRenderError(
                    f"{context}: locator {locator!r} does not "
                    f"resolve at index [{segment}]"
                )
            node = node[segment]
    last = segments[-1]
    if isinstance(last, str):
        if not isinstance(node, dict) or last not in node:
            raise ConfigRenderError(
                f"{context}: locator {locator!r} does not point at "
                "an existing JSON field; the patcher sets values, "
                "it never invents structure"
            )
        node[last] = value
    else:
        if not isinstance(node, list) or last >= len(node):
            raise ConfigRenderError(
                f"{context}: locator {locator!r} does not point at "
                "an existing JSON array element"
            )
        node[last] = value
    return canonical_json(data)
