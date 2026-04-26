#!/usr/bin/env python3

import argparse
import json
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP_ROOT = Path(tempfile.gettempdir()).resolve()
SYSTEM_TMP = Path("/tmp").resolve()
ALLOWED_BASES = (PROJECT_ROOT, TMP_ROOT, SYSTEM_TMP)


def _is_within(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _safe_read_path(user_path: str) -> Path:
    resolved = Path(user_path).expanduser().resolve(strict=True)
    if not any(_is_within(resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Input path is outside allowed directories: {resolved}")
    return resolved


def _safe_output_dir(user_path: str) -> Path:
    target = Path(user_path).expanduser()
    parent = target.parent if target.parent != Path("") else Path(".")
    parent_resolved = parent.resolve(strict=True)
    if not any(_is_within(parent_resolved, base) for base in ALLOWED_BASES):
        raise ValueError(
            f"Output directory parent is outside allowed directories: {target}"
        )
    target.mkdir(parents=True, exist_ok=True)
    resolved = target.resolve()
    if not any(_is_within(resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Output directory is outside allowed directories: {resolved}")
    return resolved


def _detected(items: list[dict], name_key: str = "name") -> list[str]:
    return [item[name_key] for item in items if item.get("detected")]


def generate_capability_matrix(discovery_doc: dict) -> dict:
    probes = discovery_doc["probes"]
    storage_classes = probes["storage_and_ingress"]["storage_classes"]
    ingress = probes["storage_and_ingress"]["ingress_controllers"]
    gitops = probes["gitops_and_secrets"]["gitops_controllers"]
    secrets = probes["gitops_and_secrets"]["secret_integrations"]

    storage_candidates = [item["name"] for item in storage_classes]
    default_storage = next(item["name"] for item in storage_classes if item.get("default"))
    ingress_candidates = _detected(ingress)
    gitops_candidates = _detected(gitops)
    secret_candidates = _detected(secrets)

    return {
        "metadata": {
            "version": "v1",
            "generated_by": "install/discovery-engine/report_generator.py",
            "cluster_name": discovery_doc.get("cluster", {}).get("name", "unknown"),
        },
        "capabilities": {
            "storage_profile_candidates": storage_candidates,
            "default_storage_profile": default_storage,
            "ingress_profile_candidates": ingress_candidates,
            "default_ingress_profile": ingress_candidates[0] if ingress_candidates else "",
            "gitops_controller_candidates": gitops_candidates,
            "default_gitops_controller": gitops_candidates[0] if gitops_candidates else "",
            "secret_profile_candidates": secret_candidates,
            "default_secret_profile": secret_candidates[0] if secret_candidates else "",
        },
    }


def generate_compatibility_result(
    preflight_doc: dict, capability_doc: dict, mode_table: dict, remediation_catalog: dict
) -> dict:
    checks = preflight_doc.get("checks", [])
    failed_reasons = sorted(
        {
            check["reason_code"]
            for check in checks
            if check.get("status") == "fail" and check.get("reason_code")
        }
    )

    if preflight_doc.get("summary", {}).get("fail", 0) > 0:
        grade = "conditional"
        recommended_mode = "attach"
    else:
        grade = "supported"
        recommended_mode = "standalone"

    supported_modes = set(mode_table["metadata"]["supported_modes"])
    if recommended_mode not in supported_modes:
        recommended_mode = "quickstart"

    remediations = remediation_catalog.get("remediations", {})
    remediation_list: list[str] = []
    for reason in failed_reasons:
        remediation_list.extend(remediations.get(reason, {}).get("actions", []))

    return {
        "metadata": {
            "version": "v1",
            "generated_by": "install/discovery-engine/report_generator.py",
            "cluster_name": preflight_doc.get("cluster", {}).get("name", "unknown"),
        },
        "input_refs": {
            "preflight_report": "generated/PREFLIGHT_REPORT.json",
            "discovery_probes": "contracts/discovery/DISCOVERY_PROBES_SAMPLE.json",
            "capability_matrix": "generated/GENERATED_CAPABILITY_MATRIX.json",
        },
        "compatibility_result": {
            "grade": grade,
            "reasons": failed_reasons,
            "recommended_deployment_mode": recommended_mode,
            "remediation_list": remediation_list,
        },
        "capability_snapshot": capability_doc.get("capabilities", {}),
    }


def generate_readiness_report() -> dict:
    return {
        "metadata": {
            "version": "v1",
            "generated_by": "install/discovery-engine/report_generator.py",
            "emitted_after": "dry-run-install",
        },
        "readiness_sections": [
            {
                "id": "platform_components",
                "description": "Core platform component health and reconciliation status.",
                "status": "pending",
            },
            {
                "id": "telemetry_paths",
                "description": "Smoke checks for logs, metrics, and traces pipelines.",
                "status": "pending",
            },
            {
                "id": "policy_and_access",
                "description": "Identity, secret, and policy control validation summary.",
                "status": "pending",
            },
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate discovery output bundle.")
    parser.add_argument("--preflight", required=True, help="Preflight report JSON path")
    parser.add_argument("--probes", required=True, help="Discovery probes JSON path")
    parser.add_argument("--mode-table", required=True, help="Mode decision table JSON path")
    parser.add_argument(
        "--remediations", required=True, help="Remediation catalog JSON path"
    )
    parser.add_argument("--output-dir", required=True, help="Output directory")
    args = parser.parse_args()

    preflight_path = _safe_read_path(args.preflight)
    probes_path = _safe_read_path(args.probes)
    mode_table_path = _safe_read_path(args.mode_table)
    remediations_path = _safe_read_path(args.remediations)

    preflight_doc = json.loads(preflight_path.read_text(encoding="utf-8"))
    probes_doc = json.loads(probes_path.read_text(encoding="utf-8"))
    mode_table = json.loads(mode_table_path.read_text(encoding="utf-8"))
    remediation_catalog = json.loads(
        remediations_path.read_text(encoding="utf-8")
    )

    output_dir = _safe_output_dir(args.output_dir)

    capability_doc = generate_capability_matrix(probes_doc)
    compatibility_doc = generate_compatibility_result(
        preflight_doc, capability_doc, mode_table, remediation_catalog
    )
    readiness_doc = generate_readiness_report()

    (output_dir / "GENERATED_CAPABILITY_MATRIX.json").write_text(
        json.dumps(capability_doc, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "GENERATED_COMPATIBILITY_RESULT.json").write_text(
        json.dumps(compatibility_doc, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "POST_INSTALL_READINESS_REPORT.json").write_text(
        json.dumps(readiness_doc, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
