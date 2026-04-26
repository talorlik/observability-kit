#!/usr/bin/env python3

import json
from pathlib import Path


def test_retrieval_quality_contract_thresholds_present() -> None:
    doc = json.loads(
        Path("contracts/vector/RETRIEVAL_QUALITY_BASELINE_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    metrics = set(doc.get("quality_metrics", {}).keys())
    assert {"precision_at_5", "recall_at_10", "mean_reciprocal_rank"} == metrics


def test_governance_contract_has_required_audit_fields() -> None:
    doc = json.loads(
        Path("contracts/vector/GOVERNANCE_CONTROLS_VALIDATION.json").read_text(
            encoding="utf-8"
        )
    )
    fields = set(doc.get("retrieval_audit_events", {}).get("required_fields", []))
    assert "@timestamp" in fields
    assert "policy_decision" in fields
