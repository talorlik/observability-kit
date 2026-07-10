"""UI catalog aggregation from the single-pane access contract.

Extracts the ui_catalog entries of
contracts/management/SINGLE_PANE_ACCESS_CONTRACT_V1.yaml with the
line-based stdlib technique established by obskit.configrender.facts
and tenantctl.state_machine (ADR-0003/ADR-0004): only the exact keys
and indentation shapes the contract fixes are read, and a contract
that yields no entries fails loudly. This keeps the YAML contract the
single source of truth without requiring PyYAML in the core
(ADR-0005 offline-CI force; the portal runtime never imports yaml).

Endpoint values stay profile_key REFERENCES into the deployed
admin-access profile `endpoints` object (or the documented null
exception for the existing Argo CD install). Resolution to a host is
a per-request lookup into a deployment-provided mapping; no URL,
hostname, or IP is ever stored (fail_if_hardcoded_endpoint).
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

from portalsvc.models import CatalogEntry, SsoRoleMapping

# Plane groups every entry must map, verbatim from the single-pane
# access contract (fail_if_missing_auth_or_tenancy_block).
READONLY_PLANE_GROUP = "role_mapping.readonly_group"
ADMIN_PLANE_GROUP = "role_mapping.admin_group"
_REQUIRED_PLANE_GROUPS = (READONLY_PLANE_GROUP, ADMIN_PLANE_GROUP)


class CatalogContractError(RuntimeError):
    """Raised when the ui_catalog cannot be extracted."""


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value


class _EntryBuilder:
    """Mutable accumulator for one ui_catalog entry."""

    def __init__(self, entry_id: str) -> None:
        self.id = entry_id
        self.system: str | None = None
        self.display_name: str | None = None
        self.endpoint_source: str | None = None
        self.endpoint_profile_key: str | None = None
        self.profile_key_seen = False
        self.mappings: list[tuple[str, str]] = []

    def finish(self, contract_path: Path) -> CatalogEntry:
        missing = [
            name
            for name, value in (
                ("system", self.system),
                ("display_name", self.display_name),
                ("endpoint.source", self.endpoint_source),
            )
            if value is None
        ]
        if missing or not self.profile_key_seen:
            if not self.profile_key_seen:
                missing.append("endpoint.profile_key")
            raise CatalogContractError(
                f"ui_catalog entry {self.id!r} in {contract_path} is "
                f"missing required field(s) {missing}"
            )
        mapped_groups = {group for group, _ in self.mappings}
        for group in _REQUIRED_PLANE_GROUPS:
            if group not in mapped_groups:
                raise CatalogContractError(
                    f"ui_catalog entry {self.id!r} maps no native "
                    f"role for {group!r} "
                    "(fail_if_missing_auth_or_tenancy_block)"
                )
        assert self.system is not None
        assert self.display_name is not None
        assert self.endpoint_source is not None
        return CatalogEntry(
            id=self.id,
            system=self.system,
            display_name=self.display_name,
            endpoint_source=self.endpoint_source,
            endpoint_profile_key=self.endpoint_profile_key,
            sso_role_mappings=tuple(
                SsoRoleMapping(plane_group=group, native_role=role)
                for group, role in self.mappings
            ),
        )


def load_ui_catalog(contract_path: Path) -> tuple[CatalogEntry, ...]:
    """Extract the ui_catalog entries from the contract file.

    The parser tracks the one top-level section it needs (ui_catalog)
    and, inside an entry, the current 4-indent block, so multi-line
    prose blocks (purpose, notes, rules, native_mechanism) are
    skipped without ever being interpreted as structure.
    """
    if not contract_path.is_file():
        raise CatalogContractError(
            f"single-pane access contract not found: {contract_path}"
        )
    entries: list[CatalogEntry] = []
    section: str | None = None
    current: _EntryBuilder | None = None
    block: str | None = None
    sso_sub: str | None = None
    pending_group: str | None = None
    folded_role: list[str] | None = None

    def finish_mapping() -> None:
        nonlocal pending_group, folded_role
        if pending_group is not None and folded_role is not None:
            assert current is not None
            current.mappings.append(
                (pending_group, " ".join(folded_role).strip())
            )
        pending_group = None
        folded_role = None

    def finish_entry() -> None:
        nonlocal current
        finish_mapping()
        if current is not None:
            entries.append(current.finish(contract_path))
        current = None

    for raw in contract_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent_of(raw)
        if indent == 0:
            finish_entry()
            section = (
                stripped[:-1] if stripped.endswith(":") else None
            )
            block = None
            sso_sub = None
            continue
        if section != "ui_catalog":
            continue
        # Folded native_role prose: any line indented deeper than the
        # native_role key itself continues the scalar.
        if folded_role is not None and indent >= 12:
            folded_role.append(stripped)
            continue
        if indent == 2 and stripped.startswith("- "):
            finish_entry()
            item = stripped[2:].strip()
            if not item.startswith("id:"):
                raise CatalogContractError(
                    "ui_catalog entry does not start with an id "
                    f"field: {stripped!r}"
                )
            current = _EntryBuilder(
                _scalar(item.split(":", 1)[1])
            )
            block = None
            sso_sub = None
            continue
        if current is None:
            continue
        if indent == 4:
            finish_mapping()
            sso_sub = None
            if stripped.startswith("system:"):
                current.system = _scalar(stripped.split(":", 1)[1])
                block = None
            elif stripped.startswith("display_name:"):
                current.display_name = _scalar(
                    stripped.split(":", 1)[1]
                )
                block = None
            elif stripped == "endpoint:":
                block = "endpoint"
            elif stripped == "sso_role_mapping:":
                block = "sso_role_mapping"
            else:
                # purpose, exposure, tls, tenant_scoping, and every
                # other block are not portal navigation facts.
                block = None
            continue
        if indent == 6 and block == "endpoint":
            if stripped.startswith("source:"):
                current.endpoint_source = _scalar(
                    stripped.split(":", 1)[1]
                )
            elif stripped.startswith("profile_key:"):
                value = _scalar(stripped.split(":", 1)[1])
                current.profile_key_seen = True
                current.endpoint_profile_key = (
                    None if value in ("null", "~", "") else value
                )
            continue
        if indent == 6 and block == "sso_role_mapping":
            finish_mapping()
            sso_sub = (
                "mappings" if stripped == "mappings:" else None
            )
            continue
        if (
            indent == 8
            and block == "sso_role_mapping"
            and sso_sub == "mappings"
            and stripped.startswith("- plane_group:")
        ):
            finish_mapping()
            pending_group = _scalar(stripped.split(":", 1)[1])
            continue
        if (
            indent == 10
            and pending_group is not None
            and stripped.startswith("native_role:")
        ):
            value = stripped.split(":", 1)[1].strip()
            if value in (">-", ">", "|", "|-"):
                folded_role = []
            else:
                folded_role = [_scalar(value)]
            continue

    finish_entry()
    if not entries:
        raise CatalogContractError(
            f"contract {contract_path} yields no parseable "
            "ui_catalog entries"
        )
    return tuple(entries)


def resolve_endpoint(
    entry: CatalogEntry, endpoints: Mapping[str, str]
) -> str | None:
    """Resolve one entry against a deployment-provided endpoint map.

    `endpoints` mirrors the deployed admin-access profile `endpoints`
    object (plus, optionally, the catalog id of a null-profile_key
    entry such as the existing Argo CD install). The result is used
    for the current response only and never stored; entries with no
    deployment-provided value resolve to None and render as
    unresolved.
    """
    key = (
        entry.endpoint_profile_key
        if entry.endpoint_profile_key is not None
        else entry.id
    )
    return endpoints.get(key)
