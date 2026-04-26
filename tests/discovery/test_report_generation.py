#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "install" / "discovery-engine" / "report_generator.py"
PREFLIGHT = ROOT / "contracts" / "discovery" / "PREFLIGHT_REPORT_SAMPLE.json"
PROBES = ROOT / "contracts" / "discovery" / "DISCOVERY_PROBES_SAMPLE.json"
MODE_TABLE = ROOT / "contracts" / "compatibility" / "MODE_DECISION_TABLE.json"
REMEDIATIONS = ROOT / "contracts" / "compatibility" / "REMEDIATION_CATALOG.json"


def test_full_expected_file_generation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "generated"
        subprocess.run(
            [
                "python3",
                str(GENERATOR),
                "--preflight",
                str(PREFLIGHT),
                "--probes",
                str(PROBES),
                "--mode-table",
                str(MODE_TABLE),
                "--remediations",
                str(REMEDIATIONS),
                "--output-dir",
                str(out_dir),
            ],
            check=True,
        )

        expected = {
            "GENERATED_CAPABILITY_MATRIX.json",
            "GENERATED_COMPATIBILITY_RESULT.json",
            "POST_INSTALL_READINESS_REPORT.json",
        }
        produced = {p.name for p in out_dir.glob("*.json")}
        assert produced == expected

        compatibility = json.loads(
            (out_dir / "GENERATED_COMPATIBILITY_RESULT.json").read_text()
        )
        assert compatibility["compatibility_result"]["recommended_deployment_mode"] in {
            "quickstart",
            "attach",
            "standalone",
            "hybrid",
        }


if __name__ == "__main__":
    test_full_expected_file_generation()
    print("test_full_expected_file_generation passed")
