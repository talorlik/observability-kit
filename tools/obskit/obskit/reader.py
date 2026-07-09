"""Cluster input backends for the obskit executor.

One ClusterReader interface, two backends (TR-18):

- FixtureReader loads a recorded cluster snapshot (JSON) and drives
  the offline, fixture-driven CI path.
- LiveReader talks to a live cluster through the Kubernetes client,
  which is an optional extra imported lazily here and nowhere else.

Both backends feed the identical evaluation path, so CLI runs and
in-cluster Job runs produce interchangeable reports. Every accessor
returns stably sorted tuples: determinism is a reader guarantee, not
a caller concern.

Snapshot format (fixture backend), all keys optional except cluster:

    {
      "cluster": {"name": "...", "kubernetes_version": "...",
                  "distribution": "..."},
      "connectivity": true,
      "permissions": {"list:namespaces": true, ...},
      "api_versions": ["v1", "apps/v1", ...],
      "crds": ["gateways.gateway.networking.k8s.io", ...],
      "storage_classes": [{"name": "...", "provisioner": "...",
                           "default": true}],
      "ingress_classes": [{"name": "...", "controller": "..."}],
      "namespaces": ["..."],
      "workloads": [{"namespace": "...", "name": "...",
                     "kind": "Deployment"}],
      "services": [{"namespace": "...", "name": "...",
                    "ports": [443]}]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from obskit.models import (
    ClusterInfo,
    IngressClassInfo,
    ServiceInfo,
    StorageClassInfo,
    WorkloadRef,
)


class ClusterReader(Protocol):
    """Read-only view of a cluster, live or recorded."""

    def cluster_info(self) -> ClusterInfo: ...

    def connectivity(self) -> bool: ...

    def can_i(self, verb: str, resource: str) -> bool: ...

    def api_versions(self) -> tuple[str, ...]: ...

    def crd_names(self) -> tuple[str, ...]: ...

    def storage_classes(self) -> tuple[StorageClassInfo, ...]: ...

    def ingress_classes(self) -> tuple[IngressClassInfo, ...]: ...

    def namespaces(self) -> tuple[str, ...]: ...

    def workloads(self) -> tuple[WorkloadRef, ...]: ...

    def services(self) -> tuple[ServiceInfo, ...]: ...


class FixtureReader:
    """Recorded-snapshot backend; drives offline CI (TR-18)."""

    def __init__(self, snapshot_path: str | Path) -> None:
        raw = Path(snapshot_path).read_text(encoding="utf-8")
        self._doc: dict[str, object] = json.loads(raw)
        if "cluster" not in self._doc:
            raise ValueError(
                f"snapshot {snapshot_path} has no 'cluster' key"
            )

    def _shaped(self, key: str, expected: type) -> object:
        """Fetch a snapshot key, failing loudly on a wrong shape.

        Deliberately raises ValueError (not assert): shape errors in
        operator-supplied snapshots are expected input errors and must
        survive `python -O`.
        """
        default: object = [] if expected is list else {}
        value = self._doc.get(key, default)
        if not isinstance(value, expected):
            raise ValueError(
                f"snapshot key {key!r} must be a "
                f"{expected.__name__}, got {type(value).__name__}"
            )
        return value

    def cluster_info(self) -> ClusterInfo:
        cluster = self._shaped("cluster", dict)
        assert isinstance(cluster, dict)  # narrowed by _shaped
        return ClusterInfo(
            name=str(cluster["name"]),
            kubernetes_version=str(
                cluster.get("kubernetes_version", "unknown")
            ),
            distribution=str(cluster.get("distribution", "unknown")),
        )

    def connectivity(self) -> bool:
        return bool(self._doc.get("connectivity", True))

    def can_i(self, verb: str, resource: str) -> bool:
        permissions = self._shaped("permissions", dict)
        assert isinstance(permissions, dict)  # narrowed by _shaped
        return bool(permissions.get(f"{verb}:{resource}", False))

    def api_versions(self) -> tuple[str, ...]:
        values = self._shaped("api_versions", list)
        assert isinstance(values, list)  # narrowed by _shaped
        return tuple(sorted(str(v) for v in values))

    def crd_names(self) -> tuple[str, ...]:
        values = self._shaped("crds", list)
        assert isinstance(values, list)  # narrowed by _shaped
        return tuple(sorted(str(v) for v in values))

    def storage_classes(self) -> tuple[StorageClassInfo, ...]:
        values = self._shaped("storage_classes", list)
        assert isinstance(values, list)  # narrowed by _shaped
        items = [
            StorageClassInfo(
                name=str(v["name"]),
                provisioner=str(v.get("provisioner", "unknown")),
                default=bool(v.get("default", False)),
            )
            for v in values
        ]
        return tuple(sorted(items, key=lambda s: s.name))

    def ingress_classes(self) -> tuple[IngressClassInfo, ...]:
        values = self._shaped("ingress_classes", list)
        assert isinstance(values, list)  # narrowed by _shaped
        items = [
            IngressClassInfo(
                name=str(v["name"]),
                controller=str(v.get("controller", "unknown")),
            )
            for v in values
        ]
        return tuple(sorted(items, key=lambda i: i.name))

    def namespaces(self) -> tuple[str, ...]:
        values = self._shaped("namespaces", list)
        assert isinstance(values, list)  # narrowed by _shaped
        return tuple(sorted(str(v) for v in values))

    def workloads(self) -> tuple[WorkloadRef, ...]:
        values = self._shaped("workloads", list)
        assert isinstance(values, list)  # narrowed by _shaped
        items = [
            WorkloadRef(
                namespace=str(v["namespace"]),
                name=str(v["name"]),
                kind=str(v.get("kind", "Deployment")),
            )
            for v in values
        ]
        return tuple(
            sorted(items, key=lambda w: (w.namespace, w.kind, w.name))
        )

    def services(self) -> tuple[ServiceInfo, ...]:
        values = self._shaped("services", list)
        assert isinstance(values, list)  # narrowed by _shaped
        items = [
            ServiceInfo(
                namespace=str(v["namespace"]),
                name=str(v["name"]),
                ports=tuple(
                    sorted(int(p) for p in v.get("ports", []))
                ),
            )
            for v in values
        ]
        return tuple(sorted(items, key=lambda s: (s.namespace, s.name)))


def _detect_distribution(provider_ids: list[str], node_labels: list[dict[str, str]]) -> str:
    """Best-effort distribution inference from generic node fields.

    This inspects only standard Kubernetes node fields; it introduces
    no provider-specific dependency (TR-18). Unknowns stay "unknown"
    rather than guessing.
    """
    joined_labels: set[str] = set()
    for labels in node_labels:
        joined_labels.update(labels.keys())
    prefixes = {pid.split(":", 1)[0] for pid in provider_ids if pid}
    if any(k.startswith("eks.amazonaws.com/") for k in joined_labels):
        return "eks"
    if "aws" in prefixes:
        return "eks"
    if "gce" in prefixes:
        return "gke"
    if "azure" in prefixes:
        return "aks"
    if any(k.startswith("node.openshift.io/") for k in joined_labels):
        return "openshift"
    if "k3s" in prefixes or any(
        k.startswith("k3s.io/") for k in joined_labels
    ):
        return "k3s"
    if "kind" in prefixes:
        return "kind"
    return "unknown"


class LiveReader:
    """Live-cluster backend over the Kubernetes API (read-only).

    Requires the obskit[k8s] extra. The import happens here, lazily,
    so the stdlib-only core stays importable without it. All calls use
    get/list verbs only; the required_permissions probe uses
    SelfSubjectAccessReview, which the default system:basic-user
    binding already allows.
    """

    def __init__(
        self,
        kubeconfig: str | None,
        context: str | None,
        cluster_name: str | None,
    ) -> None:
        try:
            from kubernetes import client, config  # noqa: PLC0415
        except ImportError as exc:  # pragma: no cover - env dependent
            raise RuntimeError(
                "live mode requires the obskit[k8s] extra: "
                "pip install 'obskit[k8s]' "
                "(see tools/obskit/requirements.txt)"
            ) from exc
        self._client = client
        # Explicit flags always win: a CLI run inside a pod that names
        # a kubeconfig means the operator wants that cluster, not the
        # pod's own service account.
        if kubeconfig or context:
            config.load_kube_config(
                config_file=kubeconfig, context=context
            )
            self._context_name = context or "current-context"
        else:
            try:
                config.load_incluster_config()
                self._context_name = "in-cluster"
            except config.ConfigException:
                config.load_kube_config()
                self._context_name = "current-context"
        self._api = client.ApiClient()
        self._cluster_name = cluster_name or self._context_name

    def cluster_info(self) -> ClusterInfo:
        version = self._client.VersionApi(self._api).get_code()
        kubernetes_version = (
            f"{version.major}.{version.minor}".replace("+", "")
        )
        nodes = self._client.CoreV1Api(self._api).list_node().items
        provider_ids = [
            (node.spec.provider_id or "") for node in nodes
        ]
        node_labels = [
            dict(node.metadata.labels or {}) for node in nodes
        ]
        return ClusterInfo(
            name=self._cluster_name,
            kubernetes_version=kubernetes_version,
            distribution=_detect_distribution(
                provider_ids, node_labels
            ),
        )

    def connectivity(self) -> bool:
        try:
            self._client.VersionApi(self._api).get_code()
            return True
        except Exception:  # noqa: BLE001 - any failure means no
            return False

    def can_i(self, verb: str, resource: str) -> bool:
        group = ""
        plural = resource
        if "/" in resource:
            group, plural = resource.split("/", 1)
        body = self._client.V1SelfSubjectAccessReview(
            spec=self._client.V1SelfSubjectAccessReviewSpec(
                resource_attributes=self._client.V1ResourceAttributes(
                    verb=verb, group=group, resource=plural
                )
            )
        )
        review = self._client.AuthorizationV1Api(
            self._api
        ).create_self_subject_access_review(body)
        return bool(review.status and review.status.allowed)

    def api_versions(self) -> tuple[str, ...]:
        core = self._client.CoreApi(self._api).get_api_versions()
        versions = set(core.versions or [])
        groups = self._client.ApisApi(self._api).get_api_versions()
        for group in groups.groups or []:
            for version in group.versions or []:
                versions.add(version.group_version)
        return tuple(sorted(versions))

    def crd_names(self) -> tuple[str, ...]:
        crds = self._client.ApiextensionsV1Api(
            self._api
        ).list_custom_resource_definition()
        return tuple(sorted(item.metadata.name for item in crds.items))

    def storage_classes(self) -> tuple[StorageClassInfo, ...]:
        classes = self._client.StorageV1Api(
            self._api
        ).list_storage_class()
        default_key = "storageclass.kubernetes.io/is-default-class"
        items = [
            StorageClassInfo(
                name=item.metadata.name,
                provisioner=item.provisioner or "unknown",
                default=(
                    (item.metadata.annotations or {}).get(default_key)
                    == "true"
                ),
            )
            for item in classes.items
        ]
        return tuple(sorted(items, key=lambda s: s.name))

    def ingress_classes(self) -> tuple[IngressClassInfo, ...]:
        classes = self._client.NetworkingV1Api(
            self._api
        ).list_ingress_class()
        items = [
            IngressClassInfo(
                name=item.metadata.name,
                controller=item.spec.controller or "unknown",
            )
            for item in classes.items
        ]
        return tuple(sorted(items, key=lambda i: i.name))

    def namespaces(self) -> tuple[str, ...]:
        spaces = self._client.CoreV1Api(self._api).list_namespace()
        return tuple(
            sorted(item.metadata.name for item in spaces.items)
        )

    def workloads(self) -> tuple[WorkloadRef, ...]:
        apps = self._client.AppsV1Api(self._api)
        batch = self._client.BatchV1Api(self._api)
        items: list[WorkloadRef] = []
        listing = [
            ("Deployment", apps.list_deployment_for_all_namespaces),
            ("DaemonSet", apps.list_daemon_set_for_all_namespaces),
            ("StatefulSet", apps.list_stateful_set_for_all_namespaces),
            ("CronJob", batch.list_cron_job_for_all_namespaces),
        ]
        for kind, lister in listing:
            for item in lister().items:
                items.append(
                    WorkloadRef(
                        namespace=item.metadata.namespace,
                        name=item.metadata.name,
                        kind=kind,
                    )
                )
        return tuple(
            sorted(items, key=lambda w: (w.namespace, w.kind, w.name))
        )

    def services(self) -> tuple[ServiceInfo, ...]:
        services = self._client.CoreV1Api(
            self._api
        ).list_service_for_all_namespaces()
        items = [
            ServiceInfo(
                namespace=item.metadata.namespace,
                name=item.metadata.name,
                ports=tuple(
                    sorted(
                        port.port for port in (item.spec.ports or [])
                    )
                ),
            )
            for item in services.items
        ]
        return tuple(sorted(items, key=lambda s: (s.namespace, s.name)))


def build_reader(
    snapshot: str | None,
    live: bool,
    kubeconfig: str | None,
    context: str | None,
    cluster_name: str | None,
) -> ClusterReader:
    """Construct the backend selected by the CLI flags."""
    if snapshot and live:
        raise ValueError("--snapshot and --live are mutually exclusive")
    if snapshot:
        return FixtureReader(snapshot)
    if live:
        return LiveReader(kubeconfig, context, cluster_name)
    raise ValueError("one of --snapshot or --live is required")
