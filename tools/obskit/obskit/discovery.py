"""Discovery probes for the obskit executor (TR-04, TR-05, TR-18).

Implements `obskit discover`: probes storage and ingress, GitOps and
secrets integrations, and workload inventory through a ClusterReader
(read-only by construction; the fixture and live backends share this
code path) and emits a report conforming to
contracts/discovery/DISCOVERY_PROBES_SCHEMA.json.

Detection model
---------------

Integrations are described by declarative signatures, not imperative
per-tool code. A signature matches when any cluster CRD ends with one
of its CRD suffixes, or any workload's name or namespace contains one
of its workload markers. The probed names mirror the profiles in
contracts/compatibility/PROFILE_CATALOG.json (nginx-ingress,
gateway-api, argocd, flux, external-secrets, vault, sealed-secrets)
so discovery output feeds compatibility evaluation directly.
Secret integrations are detected purely from CRDs and workloads:
Secret resources are never read - the bundled RBAC manifest grants no
secret access by design.

Onboardable-candidate rule
--------------------------

A service is an onboardable candidate if and only if:

1. its namespace is not a system namespace (not "default" and not
   prefixed "kube-"), and
2. it exposes at least one port.

The rule is intentionally structural and deterministic: it depends
only on snapshot content, so identical inputs always yield identical
candidacy flags (TR-18 determinism). Collection ordering is stable
because every ClusterReader accessor returns stably sorted tuples;
this module preserves reader order.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

from obskit.emit import write_report
from obskit.models import (
    IngressClassInfo,
    ServiceInfo,
    WorkloadRef,
    report_metadata,
)
from obskit.reader import ClusterReader, build_reader

SOURCE_MARKER = "TR-18"

# Gateway API CRDs share this API group on any conformant cluster.
GATEWAY_API_CRD_SUFFIX = ".gateway.networking.k8s.io"

# Candidacy rule inputs (documented in the module docstring).
SYSTEM_NAMESPACES: frozenset[str] = frozenset({"default"})
SYSTEM_NAMESPACE_PREFIXES: tuple[str, ...] = ("kube-",)


@dataclass(frozen=True)
class IntegrationSignature:
    """Declarative detection signature for one known integration.

    crd_suffixes match against the end of CRD names (API-group
    anchored, e.g. ".argoproj.io"); workload_markers match as
    substrings of workload names and namespaces.
    """

    name: str
    crd_suffixes: tuple[str, ...]
    workload_markers: tuple[str, ...]

    def detected(
        self,
        crds: tuple[str, ...],
        workloads: tuple[WorkloadRef, ...],
    ) -> bool:
        if any(
            crd.endswith(suffix)
            for crd in crds
            for suffix in self.crd_suffixes
        ):
            return True
        return any(
            marker in workload.name or marker in workload.namespace
            for workload in workloads
            for marker in self.workload_markers
        )


# Names track contracts/compatibility/PROFILE_CATALOG.json profiles.
GITOPS_SIGNATURES: tuple[IntegrationSignature, ...] = (
    IntegrationSignature(
        name="argocd",
        crd_suffixes=(".argoproj.io",),
        workload_markers=("argocd",),
    ),
    IntegrationSignature(
        name="flux",
        crd_suffixes=(
            ".toolkit.fluxcd.io",
            ".fluxcd.io",
        ),
        workload_markers=("flux",),
    ),
)

SECRET_SIGNATURES: tuple[IntegrationSignature, ...] = (
    IntegrationSignature(
        name="external-secrets",
        crd_suffixes=(".external-secrets.io",),
        workload_markers=("external-secrets",),
    ),
    IntegrationSignature(
        name="sealed-secrets",
        crd_suffixes=("sealedsecrets.bitnami.com",),
        workload_markers=("sealed-secrets",),
    ),
    IntegrationSignature(
        name="vault",
        crd_suffixes=(".secrets.hashicorp.com", ".vault.banzaicloud.com"),
        workload_markers=("vault",),
    ),
)


def _gateway_api_present(crds: tuple[str, ...]) -> bool:
    return any(crd.endswith(GATEWAY_API_CRD_SUFFIX) for crd in crds)


def _nginx_ingress_detected(
    ingress_classes: tuple[IngressClassInfo, ...],
    workloads: tuple[WorkloadRef, ...],
) -> bool:
    """Detect ingress-nginx from IngressClass controllers or workloads.

    The upstream controller value is "k8s.io/ingress-nginx"; class
    names commonly contain "nginx". Workload names cover clusters
    where the IngressClass is absent but the controller runs.
    """
    for ingress_class in ingress_classes:
        if "ingress-nginx" in ingress_class.controller:
            return True
        if "nginx" in ingress_class.name:
            return True
    return any(
        "ingress-nginx" in workload.name or "nginx-ingress" in workload.name
        for workload in workloads
    )


def _storage_and_ingress(reader: ClusterReader) -> dict[str, Any]:
    crds = reader.crd_names()
    workloads = reader.workloads()
    storage_classes = [
        {"name": sc.name, "default": sc.default}
        for sc in reader.storage_classes()
    ]
    ingress_controllers = [
        {
            "name": "gateway-api",
            "detected": _gateway_api_present(crds),
        },
        {
            "name": "nginx-ingress",
            "detected": _nginx_ingress_detected(
                reader.ingress_classes(), workloads
            ),
        },
    ]
    return {
        "storage_classes": storage_classes,
        "ingress_controllers": ingress_controllers,
        "gateway_api_crds": {"present": _gateway_api_present(crds)},
    }


def _gitops_and_secrets(reader: ClusterReader) -> dict[str, Any]:
    crds = reader.crd_names()
    workloads = reader.workloads()

    def evaluate(
        signatures: tuple[IntegrationSignature, ...],
    ) -> list[dict[str, Any]]:
        return [
            {
                "name": signature.name,
                "detected": signature.detected(crds, workloads),
            }
            for signature in sorted(signatures, key=lambda s: s.name)
        ]

    return {
        "gitops_controllers": evaluate(GITOPS_SIGNATURES),
        "secret_integrations": evaluate(SECRET_SIGNATURES),
    }


def _controller_key(kind: str) -> str:
    """Map a workload kind to its report key ("Deployment" -> "deployments")."""
    return kind.lower() + "s"


def _onboardable_candidate(service: ServiceInfo) -> bool:
    if service.namespace in SYSTEM_NAMESPACES:
        return False
    if service.namespace.startswith(SYSTEM_NAMESPACE_PREFIXES):
        return False
    return len(service.ports) > 0


def _workload_inventory(reader: ClusterReader) -> dict[str, Any]:
    controllers: dict[str, int] = {}
    for workload in reader.workloads():
        key = _controller_key(workload.kind)
        controllers[key] = controllers.get(key, 0) + 1
    services = [
        {
            "namespace": service.namespace,
            "name": service.name,
            "ports": list(service.ports),
            "onboardable_candidate": _onboardable_candidate(service),
        }
        for service in reader.services()
    ]
    return {
        "namespaces": list(reader.namespaces()),
        "controllers": controllers,
        "services": services,
    }


def build_probes_report(reader: ClusterReader) -> dict[str, Any]:
    """Assemble the full discovery probes report from one reader.

    Pure with respect to the reader: no I/O of its own, no clock, no
    environment reads - identical reader content yields an identical
    report dict (TR-18 determinism).
    """
    return {
        "metadata": report_metadata(SOURCE_MARKER),
        "cluster": reader.cluster_info().to_dict(),
        "probes": {
            "storage_and_ingress": _storage_and_ingress(reader),
            "gitops_and_secrets": _gitops_and_secrets(reader),
            "workload_inventory": _workload_inventory(reader),
        },
    }


def run(args: argparse.Namespace) -> int:
    """CLI entry point for `obskit discover`."""
    try:
        reader = build_reader(
            snapshot=args.snapshot,
            live=args.live,
            kubeconfig=args.kubeconfig,
            context=args.context,
            cluster_name=args.cluster_name,
        )
        report = build_probes_report(reader)
        write_report(report, args.output)
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"obskit discover: error: {exc}", file=sys.stderr)
        return 1
    return 0
