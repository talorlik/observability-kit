#!/usr/bin/env python3

import json
from pathlib import Path


def test_never_index_fields_present() -> None:
    rules = json.loads(
        Path("contracts/logs/NEVER_INDEX_RULES.json").read_text(encoding="utf-8")
    )
    fields = set(rules["never_index_fields"])
    assert "user.password" in fields
    assert "http.request.header.authorization" in fields
