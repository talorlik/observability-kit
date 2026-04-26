#!/usr/bin/env python3

import json
from pathlib import Path


def test_correlation_contract_contains_trace_and_span_fields() -> None:
    contract = json.loads(
        Path("contracts/metrics_traces/CORRELATION_PIVOT_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    required = set(contract["required_correlation_fields"])
    assert {"trace_id", "span_id"}.issubset(required)
