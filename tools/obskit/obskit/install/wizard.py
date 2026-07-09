"""Interactive answer capture for the guided installer (TR-19).

Prompts, via input(), for every field the install contract schema
requires, plus the attached-service endpoints when the chosen
deployment mode is attach or hybrid (the schema's allOf requires
attached_services for those modes). The deployment_mode prompt
defaults to the mode-recommendation step's recommendation; empty
input takes the offered default where one exists.

Parity invariant: the wizard produces exactly the answers-mapping
shape an --answers file supplies, and the flow records it to
answers.json, so every interactive run is replayable
non-interactively (flow contract invariant non_interactive_parity).
"""

from __future__ import annotations

from typing import Any, Callable

from obskit.install.models import InstallFlowError

# Modes whose schema allOf requires the attached_services object.
MODES_REQUIRING_ATTACHED_SERVICES: tuple[str, ...] = (
    "attach",
    "hybrid",
)

# attached_services properties, in schema order.
ATTACHED_SERVICE_FIELDS: tuple[str, ...] = (
    "opensearch_endpoint",
    "dashboards_endpoint",
    "otlp_endpoint",
)


def _ask(
    input_fn: Callable[[str], str] | None, prompt: str
) -> str:
    # input is resolved at call time (not bound as a default) so a
    # monkeypatched builtins.input drives the wizard in tests.
    reader = input_fn if input_fn is not None else input
    try:
        return reader(prompt).strip()
    except EOFError as exc:
        raise InstallFlowError(
            "interactive input ended before all required answers "
            "were captured"
        ) from exc


def capture_answers(
    schema: dict[str, Any],
    recommended_mode: str | None,
    input_fn: Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Prompt for every schema-required field; return the mapping.

    Empty input takes the offered default where one exists (only
    deployment_mode offers one: the recommendation); otherwise the
    empty value flows into schema validation, which rejects it with
    a clean non-zero exit - the wizard never invents values.
    """
    properties: dict[str, Any] = schema.get("properties", {})
    answers: dict[str, Any] = {}
    for field_name in schema.get("required", ()):
        spec = properties.get(field_name, {})
        enum = spec.get("enum")
        hint = f" ({'/'.join(enum)})" if enum else ""
        default = (
            recommended_mode
            if field_name == "deployment_mode"
            and recommended_mode is not None
            else None
        )
        suffix = f" [{default}]" if default is not None else ""
        value = _ask(input_fn, f"{field_name}{hint}{suffix}: ")
        if not value and default is not None:
            value = default
        answers[field_name] = value

    if (
        answers.get("deployment_mode")
        in MODES_REQUIRING_ATTACHED_SERVICES
    ):
        attached: dict[str, str] = {}
        for field_name in ATTACHED_SERVICE_FIELDS:
            # The schema requires opensearch_endpoint for attach and
            # hybrid modes: attaching means reusing an existing
            # OpenSearch, and an empty value would silently deploy
            # the standalone default backend instead.
            required = field_name == "opensearch_endpoint"
            suffix = "" if required else " (empty to skip)"
            value = _ask(
                input_fn,
                f"attached_services.{field_name}{suffix}: ",
            )
            while required and not value:
                value = _ask(
                    input_fn,
                    f"attached_services.{field_name} is required for"
                    f" {answers['deployment_mode']} mode: ",
                )
            if value:
                attached[field_name] = value
        answers["attached_services"] = attached

    return answers
