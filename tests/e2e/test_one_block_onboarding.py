#!/usr/bin/env python3

import json
from pathlib import Path


def test_one_block_validation_references_single_values_block() -> None:
    report = json.loads(
        Path("contracts/onboarding/ONE_BLOCK_ONBOARDING_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["pilot_render_result"]["values_blocks_detected"] == 1
