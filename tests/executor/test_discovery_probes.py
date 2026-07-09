#!/usr/bin/env python3
"""Offline fixture-driven tests for `obskit discover` (Batch 17, TR-18).

Exercises the three contracted probe groups on the reference snapshot
and asserts the detection semantics: integration signatures resolve to
detected/not-detected per the recorded cluster state, the workload
inventory aggregates controllers and onboardable service candidates,
and every emitted list keeps the stable ordering the determinism
contract requires.

Owned by scripts/ci/validate_discovery_executor.sh.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "executor" / "fixtures"

EXPECTED_PROBE_GROUPS = [
    "gitops_and_secrets",
    "storage_and_ingress",
    "workload_inventory",
]


def _cli_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "tools" / "obskit")
    return env


def run_discover(snapshot: Path) -> tuple[int, dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "discovery_probes.json"
        proc = subprocess.run(
            [
                "python3",
                "-m",
                "obskit.cli",
                "discover",
                "--snapshot",
                str(snapshot),
                "--output",
                str(out_path),
            ],
            cwd=ROOT,
            env=_cli_env(),
            capture_output=True,
            text=True,
        )
        assert out_path.is_file(), (
            f"discover wrote no report; stderr: {proc.stderr}"
        )
        return proc.returncode, json.loads(out_path.read_text())


def _detection_map(items: list[dict]) -> dict[str, bool]:
    return {item["name"]: item["detected"] for item in items}


def test_probe_groups_present_and_exit_zero() -> None:
    code, report = run_discover(
        FIXTURES / "snapshot_discovery_reference.json"
    )
    assert code == 0, f"expected exit 0, got {code}"
    assert sorted(report["probes"].keys()) == EXPECTED_PROBE_GROUPS, (
        sorted(report["probes"].keys())
    )
    assert report["cluster"]["name"] == "reference-cluster"


def test_gitops_and_secrets_detection_semantics() -> None:
    _, report = run_discover(FIXTURES / "snapshot_discovery_reference.json")
    group = report["probes"]["gitops_and_secrets"]

    controllers = _detection_map(group["gitops_controllers"])
    # The reference snapshot runs Argo CD but not Flux; both contracted
    # controller signatures must still be reported.
    assert controllers == {"argocd": True, "flux": False}, controllers

    secrets = _detection_map(group["secret_integrations"])
    assert secrets == {
        "external-secrets": True,
        "sealed-secrets": False,
        "vault": False,
    }, secrets


def test_storage_and_ingress_detection_semantics() -> None:
    _, report = run_discover(FIXTURES / "snapshot_discovery_reference.json")
    group = report["probes"]["storage_and_ingress"]

    storage = {
        item["name"]: item["default"] for item in group["storage_classes"]
    }
    assert storage == {"standard-rwo": True, "nfs-rwx": False}, storage

    ingress = _detection_map(group["ingress_controllers"])
    assert ingress == {"nginx-ingress": True, "gateway-api": True}, ingress
    assert group["gateway_api_crds"] == {"present": True}


def test_workload_inventory_semantics() -> None:
    _, report = run_discover(FIXTURES / "snapshot_discovery_reference.json")
    inventory = report["probes"]["workload_inventory"]

    assert inventory["controllers"] == {
        "cronjobs": 1,
        "daemonsets": 1,
        "deployments": 5,
        "statefulsets": 1,
    }, inventory["controllers"]

    assert "payments" in inventory["namespaces"]
    assert "platform" in inventory["namespaces"]

    services = {
        (item["namespace"], item["name"]): item for item in
        inventory["services"]
    }
    onboardable = sorted(
        name for (_, name), item in services.items()
        if item["onboardable_candidate"]
    )
    assert onboardable == ["checkout-api", "reporting-worker"], onboardable
    # A service without ports is never an onboardable candidate.
    notifier = services[("platform", "internal-notifier")]
    assert notifier["ports"] == []
    assert notifier["onboardable_candidate"] is False


def test_stable_ordering_of_emitted_lists() -> None:
    _, report = run_discover(FIXTURES / "snapshot_discovery_reference.json")
    probes = report["probes"]

    gitops = [i["name"] for i in probes["gitops_and_secrets"]["gitops_controllers"]]
    assert gitops == sorted(gitops), gitops
    secrets = [i["name"] for i in probes["gitops_and_secrets"]["secret_integrations"]]
    assert secrets == sorted(secrets), secrets
    storage = [i["name"] for i in probes["storage_and_ingress"]["storage_classes"]]
    assert storage == sorted(storage), storage
    ingress = [i["name"] for i in probes["storage_and_ingress"]["ingress_controllers"]]
    assert ingress == sorted(ingress), ingress
    namespaces = probes["workload_inventory"]["namespaces"]
    assert namespaces == sorted(namespaces), namespaces
    service_keys = [
        (i["namespace"], i["name"])
        for i in probes["workload_inventory"]["services"]
    ]
    assert service_keys == sorted(service_keys), service_keys


if __name__ == "__main__":
    test_probe_groups_present_and_exit_zero()
    print("test_probe_groups_present_and_exit_zero passed")
    test_gitops_and_secrets_detection_semantics()
    print("test_gitops_and_secrets_detection_semantics passed")
    test_storage_and_ingress_detection_semantics()
    print("test_storage_and_ingress_detection_semantics passed")
    test_workload_inventory_semantics()
    print("test_workload_inventory_semantics passed")
    test_stable_ordering_of_emitted_lists()
    print("test_stable_ordering_of_emitted_lists passed")
