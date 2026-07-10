"""Model provider registry (ADR-0008).

Two contracted providers exist in
contracts/ai/MODEL_PROVIDER_ADAPTER_CONTRACT_V1.yaml: the deterministic
``local-stub`` rehearsal provider (implemented here, used by every
offline test and the disposable harness) and the ``anthropic-reference``
production provider, which requires a credentialed profile and is
deliberately NOT implemented in this codebase - requesting it raises so
no code path can ever attempt a network model call from the rehearsal
runtime.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from airuntime.contracts import (
    MODEL_REQUEST_FIELDS,
    REFERENCE_PROVIDER,
    REHEARSAL_PROVIDER,
)


class LocalStubProvider:
    """Deterministic rehearsal provider: same request -> same response."""

    name = REHEARSAL_PROVIDER

    def complete(self, request: dict[str, Any]) -> dict[str, Any]:
        missing = [f for f in MODEL_REQUEST_FIELDS if f not in request]
        if missing:
            raise ValueError(
                f"model request missing contract fields: {missing}"
            )
        # Redaction is a caller responsibility: prompts reach the
        # provider already redacted, and the declared profile is the
        # caller's attestation of that. An absent profile is a
        # programming error, not a soft default.
        if not request["redaction_profile"]:
            raise ValueError(
                "redaction_profile is required: prompts must be redacted "
                "before they reach a model provider"
            )
        intent = str(
            request.get("intent") or request.get("input") or "analysis"
        )
        # Stable digest over the whole request makes the content unique
        # per distinct request yet fully reproducible.
        digest = hashlib.sha256(
            json.dumps(request, sort_keys=True).encode()
        ).hexdigest()
        content = f"local-stub analysis for {intent} [{digest[:12]}]"
        # Length-derived token counts: deterministic, monotone with the
        # payload size, and obviously not a real tokenizer.
        input_tokens = max(
            1, len(json.dumps(request, sort_keys=True)) // 4
        )
        output_tokens = max(1, len(content) // 4)
        return {
            "provider": self.name,
            "model_ref": request["model_ref"],
            "content": content,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
            "stop_reason": "end_turn",
        }


def get_provider(name: str) -> LocalStubProvider:
    if name == REHEARSAL_PROVIDER:
        return LocalStubProvider()
    if name == REFERENCE_PROVIDER:
        raise NotImplementedError(
            "anthropic-reference requires a credentialed production "
            "profile; keys resolve through the secrets backend adapter"
        )
    raise ValueError(f"unknown model provider: {name!r}")
