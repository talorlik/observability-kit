#!/usr/bin/env python3

import argparse
import json
import tempfile
from dataclasses import dataclass
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


def _safe_write_path(user_path: str) -> Path:
    target = Path(user_path).expanduser()
    parent = target.parent if target.parent != Path("") else Path(".")
    parent_resolved = parent.resolve(strict=True)
    if not any(_is_within(parent_resolved, base) for base in ALLOWED_BASES):
        raise ValueError(f"Output path parent is outside allowed directories: {target}")
    return target.resolve()


@dataclass(frozen=True)
class CheckClass:
    check_id: str
    description: str
    input_key: str
    reason_code: str


CHECK_CLASSES = [
    CheckClass(
        "cluster_connectivity",
        "Cluster API reachable with provided credentials.",
        "cluster_connectivity",
        "cluster_connectivity_failed",
    ),
    CheckClass(
        "required_permissions",
        "Preflight service account can read required resources.",
        "required_permissions",
        "rbac_access_missing",
    ),
    CheckClass(
        "required_api_readiness",
        "Required APIs and APIService endpoints are available.",
        "required_api_readiness",
        "required_api_unavailable",
    ),
    CheckClass(
        "required_crd_readiness",
        "Gateway API CRDs are installed when gateway profile is set.",
        "required_crd_readiness",
        "gateway_api_crds_required",
    ),
    CheckClass(
        "storage_compatibility",
        "Detected storage profile is compatible with selected mode.",
        "storage_compatibility",
        "storage_profile_incompatible",
    ),
    CheckClass(
        "gitops_prerequisites",
        "A supported GitOps controller and CRDs are present.",
        "gitops_prerequisites",
        "gitops_controller_missing",
    ),
]


def _status(value: bool) -> str:
    return "pass" if value else "fail"


def run_preflight(input_doc: dict) -> dict:
    checks = []
    for check in CHECK_CLASSES:
        passed = bool(input_doc.get(check.input_key, False))
        item = {
            "id": check.check_id,
            "description": check.description,
            "status": _status(passed),
        }
        if not passed:
            item["reason_code"] = check.reason_code
        checks.append(item)

    pass_count = sum(1 for item in checks if item["status"] == "pass")
    fail_count = len(checks) - pass_count
    return {
        "metadata": {
            "version": "v1",
            "generated_by": "install/discovery-engine/preflight_checks.py",
        },
        "cluster": {
            "name": input_doc.get("cluster_name", "unknown"),
            "kubernetes_version": input_doc.get("kubernetes_version", "unknown"),
            "distribution": input_doc.get("distribution", "unknown"),
        },
        "checks": checks,
        "summary": {
            "total_checks": len(checks),
            "pass": pass_count,
            "fail": fail_count,
            "outcome": "pass" if fail_count == 0 else "fail",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run discovery preflight checks.")
    parser.add_argument("--input", required=True, help="Input JSON path")
    parser.add_argument("--output", required=True, help="Output JSON path")
    args = parser.parse_args()

    input_path = _safe_read_path(args.input)
    output_path = _safe_write_path(args.output)
    input_doc = json.loads(input_path.read_text(encoding="utf-8"))
    report = run_preflight(input_doc)
    output_path.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
