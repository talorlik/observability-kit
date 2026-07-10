"""Contract-loaded lifecycle state machine.

Loads states, initial/terminal states, and per-transition from/to,
idempotency, approval risk class, and audit field lists directly from
contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml at runtime, using
the line-based stdlib extraction technique established by
obskit.configrender.facts (ADR-0003): only the exact keys and
indentation shapes the contract fixes are read, and a contract that
yields no facts fails loudly. This keeps the YAML contract the single
source of truth without requiring PyYAML in the core (ADR-0004
offline-CI force).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from tenantctl.models import TRANSITION_NAMES


class LifecycleContractError(RuntimeError):
    """Raised when the lifecycle contract cannot be extracted."""


@dataclass(frozen=True)
class TransitionSpec:
    """One transition of the lifecycle contract's state machine."""

    name: str
    from_states: tuple[str, ...]
    to_state: str
    idempotent: bool
    # Approval risk class from the transition's approval block
    # (write.high-risk / write.critical), or None for non-destructive
    # transitions. Destructiveness is exactly approval-gatedness in the
    # lifecycle contract, so no separate flag is stored.
    approval_risk_class: str | None
    audit_required_fields: tuple[str, ...]

    @property
    def destructive(self) -> bool:
        return self.approval_risk_class is not None


@dataclass(frozen=True)
class LifecycleStateMachine:
    """The complete extracted state machine."""

    states: tuple[str, ...]
    initial_state: str
    terminal_states: tuple[str, ...]
    transitions: Mapping[str, TransitionSpec]

    def spec(self, name: str) -> TransitionSpec | None:
        return self.transitions.get(name)

    def is_state(self, value: str) -> bool:
        return value in self.states


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def load_state_machine(contract_path: Path) -> LifecycleStateMachine:
    """Extract the state machine from the lifecycle contract.

    The parser tracks the two top-level sections it needs
    (state_machine, transitions) and, inside a transition, the current
    4-indent field, so multi-line prose blocks (description, semantics,
    outputs_by_isolation_class, evidence_capture) are skipped without
    ever being interpreted as structure.
    """
    if not contract_path.is_file():
        raise LifecycleContractError(
            f"lifecycle contract not found: {contract_path}"
        )
    states: list[str] = []
    initial_state: str | None = None
    terminal_states: list[str] = []
    transitions: dict[str, dict[str, object]] = {}
    section: str | None = None
    machine_field: str | None = None
    current: dict[str, object] | None = None
    field: str | None = None
    subfield: str | None = None

    for raw in contract_path.read_text(encoding="utf-8").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = _indent_of(raw)
        if indent == 0:
            section = stripped[:-1] if stripped.endswith(":") else None
            machine_field = None
            current = None
            field = None
            subfield = None
            continue
        if section == "state_machine":
            if indent == 2:
                if stripped == "states:":
                    machine_field = "states"
                elif stripped == "terminal_states:":
                    machine_field = "terminal_states"
                elif stripped.startswith("initial_state:"):
                    initial_state = stripped.split(":", 1)[1].strip()
                    machine_field = None
                else:
                    machine_field = None
            elif indent == 4 and stripped.startswith("- "):
                if machine_field == "states":
                    states.append(stripped[2:].strip())
                elif machine_field == "terminal_states":
                    terminal_states.append(stripped[2:].strip())
            continue
        if section != "transitions":
            continue
        if indent == 2 and stripped.endswith(":"):
            name = stripped[:-1]
            current = {
                "from": [],
                "to": None,
                "idempotent": None,
                "risk_class": None,
                "audit_fields": [],
            }
            transitions[name] = current
            field = None
            subfield = None
            continue
        if current is None:
            continue
        if indent == 4:
            subfield = None
            if stripped == "from:":
                field = "from"
            elif stripped.startswith("to:"):
                current["to"] = stripped.split(":", 1)[1].strip()
                field = None
            elif stripped.startswith("idempotent:"):
                current["idempotent"] = (
                    stripped.split(":", 1)[1].strip() == "true"
                )
                field = None
            elif stripped == "approval:":
                field = "approval"
            elif stripped == "audit:":
                field = "audit"
            else:
                field = None
            continue
        if indent == 6:
            if field == "from" and stripped.startswith("- "):
                from_list = current["from"]
                assert isinstance(from_list, list)
                from_list.append(stripped[2:].strip())
            elif field == "approval" and stripped.startswith(
                "risk_class:"
            ):
                current["risk_class"] = (
                    stripped.split(":", 1)[1].strip()
                )
            elif field == "audit" and stripped == "required_fields:":
                subfield = "required_fields"
            continue
        if (
            indent == 8
            and subfield == "required_fields"
            and stripped.startswith("- ")
        ):
            audit_fields = current["audit_fields"]
            assert isinstance(audit_fields, list)
            audit_fields.append(stripped[2:].strip())

    if not states or initial_state is None or not terminal_states:
        raise LifecycleContractError(
            f"lifecycle contract {contract_path} yields no parseable "
            "state_machine block"
        )
    specs: dict[str, TransitionSpec] = {}
    for name, data in transitions.items():
        from_states = data["from"]
        to_state = data["to"]
        idempotent = data["idempotent"]
        risk_class = data["risk_class"]
        audit_fields = data["audit_fields"]
        assert isinstance(from_states, list)
        assert isinstance(audit_fields, list)
        if (
            not from_states
            or not isinstance(to_state, str)
            or idempotent is None
            or not audit_fields
        ):
            raise LifecycleContractError(
                f"lifecycle contract transition {name!r} is missing "
                "from/to/idempotent/audit facts"
            )
        for state in [*from_states, to_state]:
            if state not in states:
                raise LifecycleContractError(
                    f"transition {name!r} references unknown state "
                    f"{state!r}"
                )
        specs[name] = TransitionSpec(
            name=name,
            from_states=tuple(from_states),
            to_state=to_state,
            idempotent=bool(idempotent),
            approval_risk_class=(
                risk_class if isinstance(risk_class, str) else None
            ),
            audit_required_fields=tuple(audit_fields),
        )
    missing = sorted(set(TRANSITION_NAMES) - set(specs))
    if missing:
        raise LifecycleContractError(
            "lifecycle contract is missing expected transition(s) "
            f"{missing}; the API contract fixes exactly "
            f"{list(TRANSITION_NAMES)}"
        )
    return LifecycleStateMachine(
        states=tuple(states),
        initial_state=initial_state,
        terminal_states=tuple(terminal_states),
        transitions=specs,
    )
