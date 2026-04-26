#!/usr/bin/env python3

from pathlib import Path


def _load_yaml_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_mode_rules_define_all_required_modes() -> None:
    content = _load_yaml_text("install/discovery-engine/mode_recommendation_rules.yaml")
    for mode in ("quickstart", "attach", "standalone", "hybrid"):
        assert f"- {mode}" in content


def test_remediation_catalog_contains_core_reason_codes() -> None:
    content = _load_yaml_text("install/discovery-engine/remediation_catalog.yaml")
    for reason in (
        "cluster_connectivity_failed",
        "rbac_access_missing",
        "required_api_unavailable",
        "gitops_controller_missing",
    ):
        assert f"{reason}:" in content
