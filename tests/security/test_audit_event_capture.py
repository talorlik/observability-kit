#!/usr/bin/env python3

import json
from pathlib import Path


def test_audit_validation_contains_required_events() -> None:
    doc = json.loads(
        Path("contracts/security/AUDIT_LOGGING_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    names = {t["name"] for t in doc.get("audit_tests", [])}
    assert "privileged_login_event" in names
    assert "onboarding_policy_deny_logged" in names
