"""Build the live post-install readiness report from cluster state.

Emits a report conforming to
contracts/install/POST_INSTALL_READINESS.schema.json with
metadata.emitted_after=live-install and the three contracted
readiness sections derived from observed state (never declared):

- platform_components: the Argo CD platform-core Application is
  Synced/Healthy and the collector workloads are fully rolled out.
- telemetry_paths: the gateway Service has ready endpoints and the
  agent DaemonSet covers every schedulable node.
- policy_and_access: the attached OpenSearch answers an authenticated
  cluster-health probe and the per-run credential Secrets exist.

Validated by scripts/validate/post_install_readiness.sh with
READINESS_REPORT_PATH pointing at the emitted file.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--context", required=True)
    parser.add_argument("--platform-namespace", required=True)
    parser.add_argument("--backend-namespace", required=True)
    parser.add_argument(
        "--application-state",
        required=True,
        help="JSON dump of the Argo CD platform-core Application",
    )
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def _kubectl_json(
    args: argparse.Namespace, *cli: str
) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "kubectl",
            "--kubeconfig", args.kubeconfig,
            "--context", args.context,
            *cli,
            "-o", "json",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


def _platform_components(
    args: argparse.Namespace,
) -> tuple[str, dict[str, Any]]:
    application = json.loads(
        Path(args.application_state).read_text()
    )
    sync = application["status"]["sync"]["status"]
    health = application["status"]["health"]["status"]
    daemonset = _kubectl_json(
        args, "-n", args.platform_namespace, "get",
        "daemonset", "otel-agent",
    )
    deployment = _kubectl_json(
        args, "-n", args.platform_namespace, "get",
        "deployment", "otel-gateway",
    )
    ds_status = daemonset["status"]
    agent_ready = (
        ds_status.get("numberReady", 0)
        == ds_status.get("desiredNumberScheduled", -1)
    )
    dep_status = deployment["status"]
    gateway_ready = (
        dep_status.get("readyReplicas", 0)
        == dep_status.get("replicas", -1)
    )
    passed = (
        sync == "Synced"
        and health == "Healthy"
        and agent_ready
        and gateway_ready
    )
    return "pass" if passed else "fail", {
        "argocd_sync": sync,
        "argocd_health": health,
        "otel_agent_ready": agent_ready,
        "otel_gateway_ready": gateway_ready,
    }


def _telemetry_paths(
    args: argparse.Namespace,
) -> tuple[str, dict[str, Any]]:
    endpoints = _kubectl_json(
        args, "-n", args.platform_namespace, "get",
        "endpoints", "otel-gateway",
    )
    ready_addresses = sum(
        len(subset.get("addresses", []))
        for subset in endpoints.get("subsets", [])
    )
    nodes = _kubectl_json(args, "get", "nodes")
    schedulable = sum(
        1
        for node in nodes["items"]
        if not node["spec"].get("unschedulable", False)
    )
    daemonset = _kubectl_json(
        args, "-n", args.platform_namespace, "get",
        "daemonset", "otel-agent",
    )
    agent_ready = daemonset["status"].get("numberReady", 0)
    passed = ready_addresses > 0 and agent_ready >= schedulable
    return "pass" if passed else "fail", {
        "gateway_ready_endpoint_addresses": ready_addresses,
        "schedulable_nodes": schedulable,
        "agent_pods_ready": agent_ready,
    }


def _policy_and_access(
    args: argparse.Namespace,
) -> tuple[str, dict[str, Any]]:
    secrets_present = True
    for secret in ("opensearch-admin", "neo4j-auth"):
        try:
            _kubectl_json(
                args, "-n", args.backend_namespace, "get",
                "secret", secret,
            )
        except subprocess.CalledProcessError:
            secrets_present = False
    probe = subprocess.run(
        [
            "kubectl",
            "--kubeconfig", args.kubeconfig,
            "--context", args.context,
            "-n", args.backend_namespace,
            "exec", "deploy/opensearch", "--",
            "bash", "-c",
            'curl -fsk -u "admin:${OPENSEARCH_INITIAL_ADMIN_PASSWORD}"'
            " https://localhost:9200/_cluster/health",
        ],
        capture_output=True,
        text=True,
    )
    backend_status = None
    if probe.returncode == 0:
        backend_status = json.loads(probe.stdout).get("status")
    passed = secrets_present and backend_status in ("green", "yellow")
    return "pass" if passed else "fail", {
        "credential_secrets_present": secrets_present,
        "opensearch_cluster_status": backend_status,
    }


def main() -> int:
    args = _parse_args()
    sections = []
    details: dict[str, Any] = {}
    for section_id, description, evaluate in (
        (
            "platform_components",
            "Core platform component health and reconciliation "
            "status.",
            _platform_components,
        ),
        (
            "telemetry_paths",
            "Smoke checks for logs, metrics, and traces pipelines.",
            _telemetry_paths,
        ),
        (
            "policy_and_access",
            "Identity, secret, and policy control validation "
            "summary.",
            _policy_and_access,
        ),
    ):
        status, observed = evaluate(args)
        sections.append(
            {
                "id": section_id,
                "description": description,
                "status": status,
            }
        )
        details[section_id] = observed

    report = {
        "metadata": {
            "version": "v1",
            "generated_by": (
                "scripts/dev/harness_assets/build_readiness_report.py"
            ),
            "emitted_after": "live-install",
            "captured_at": datetime.now(timezone.utc).isoformat(),
        },
        "readiness_sections": sections,
        "observed": details,
    }
    output = Path(args.output)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n"
    )
    failed = [
        section["id"]
        for section in sections
        if section["status"] != "pass"
    ]
    print(f"readiness report written: {output}")
    if failed:
        print(f"ERROR: readiness sections failed: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
