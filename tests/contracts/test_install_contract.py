#!/usr/bin/env python3

import json
from pathlib import Path


def test_install_contract_alias_points_to_primary_schema() -> None:
    alias = json.loads(
        Path("contracts/install/INSTALL_CONTRACT.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert alias["allOf"][0]["$ref"] == "./INSTALL_CONTRACT_SCHEMA.json"


def test_install_contract_example_contains_required_keys() -> None:
    required = {
        "cluster_name",
        "environment",
        "deployment_mode",
        "gitops_repo_url",
        "gitops_path",
        "base_domain",
        "storage_profile",
        "object_storage_profile",
        "identity_profile",
        "secret_profile",
        "ingress_profile",
    }
    lines = Path("contracts/install/INSTALL_CONTRACT.example.yaml").read_text(
        encoding="utf-8"
    ).splitlines()
    keys = {line.split(":")[0] for line in lines if ":" in line}
    assert required.issubset(keys)
