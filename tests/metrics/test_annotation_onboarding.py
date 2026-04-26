#!/usr/bin/env python3

import json
from pathlib import Path


def test_metrics_subscription_contract_controls() -> None:
    contract = json.loads(
        Path("contracts/metrics/METRICS_SUBSCRIPTION_CONTRACT.json").read_text(
            encoding="utf-8"
        )
    )
    controls = contract["required_onboarding_controls"]
    assert controls["opt_in_value"] == "true"
    assert contract["required_index_pattern"] == "metrics-*"
