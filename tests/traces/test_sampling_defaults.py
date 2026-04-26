#!/usr/bin/env python3

import json
from pathlib import Path


def test_sampling_contract_defaults() -> None:
    contract = json.loads(
        Path("contracts/traces/TRACE_SAMPLING_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["default_policy"]["sampler"] == "parentbased_traceidratio"
    assert 0 < contract["default_policy"]["ratio"] <= 1
