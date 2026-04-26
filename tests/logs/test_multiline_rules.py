#!/usr/bin/env python3

import json
from pathlib import Path


def test_multiline_contract_has_required_patterns() -> None:
    contract = json.loads(
        Path("contracts/logs/LOG_PARSING_CONTRACT.json").read_text(encoding="utf-8")
    )
    patterns = set(contract["multiline_patterns"])
    assert {"java", "go", "python"}.issubset(patterns)
