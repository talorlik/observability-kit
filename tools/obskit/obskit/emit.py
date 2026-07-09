"""Deterministic report emission.

Every obskit artifact is serialized through canonical_json so that
identical inputs produce byte-identical outputs (TR-18): sorted keys,
fixed two-space indentation, trailing newline, no locale- or
environment-dependent formatting.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

STDOUT_SENTINEL = "-"


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_report(payload: dict[str, Any], output: str) -> None:
    """Write a report to a file path, or stdout when output is "-"."""
    text = canonical_json(payload)
    if output == STDOUT_SENTINEL:
        sys.stdout.write(text)
        return
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
