#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "install" / "discovery-engine" / "preflight_checks.py"


def run_preflight(input_doc: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "input.json"
        out_path = tmp_path / "output.json"
        in_path.write_text(json.dumps(input_doc))
        subprocess.run(
            ["python3", str(SCRIPT), "--input", str(in_path), "--output", str(out_path)],
            check=True,
        )
        return json.loads(out_path.read_text())


def test_preflight_check_class_coverage() -> None:
    input_doc = {
        "cluster_name": "reference-cluster",
        "kubernetes_version": "1.29",
        "distribution": "eks",
        "cluster_connectivity": True,
        "required_permissions": False,
        "required_api_readiness": True,
        "required_crd_readiness": False,
        "storage_compatibility": True,
        "gitops_prerequisites": False,
    }
    report = run_preflight(input_doc)

    checks = report["checks"]
    check_ids = {item["id"] for item in checks}
    expected_ids = {
        "cluster_connectivity",
        "required_permissions",
        "required_api_readiness",
        "required_crd_readiness",
        "storage_compatibility",
        "gitops_prerequisites",
    }
    assert check_ids == expected_ids
    assert any(item["status"] == "pass" for item in checks)
    assert any(item["status"] == "fail" for item in checks)


if __name__ == "__main__":
    test_preflight_check_class_coverage()
    print("test_preflight_check_class_coverage passed")
