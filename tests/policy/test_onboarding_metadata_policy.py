#!/usr/bin/env python3

from pathlib import Path


def test_kyverno_policy_requires_all_metadata_labels() -> None:
    policy = Path(
        "gitops/platform/security/kyverno/onboarding-metadata-policy.yaml"
    ).read_text(encoding="utf-8")
    assert "service.name" in policy
    assert "deployment.environment" in policy
    assert "service.owner" in policy
