"""Preflight execution engine (Batch 17 Task 2, TR-04/TR-05/TR-18).

Evaluates every contracted preflight check class against OBSERVED
cluster state supplied by a ClusterReader (live or fixture) and emits
a report conforming to contracts/discovery/PREFLIGHT_REPORT_SCHEMA.json.

Contracted check classes (install/discovery-engine/preflight_checks.py
is the authoritative catalog; ids and descriptions match it verbatim)
and the stable emission order of the checks list:

1. cluster_connectivity
2. required_permissions
3. required_api_readiness
4. required_crd_readiness
5. storage_compatibility
6. gitops_prerequisites

Unlike the Batch 3 simulator, which trusts declared booleans, every
check here derives its status from reader observations only.

Gating rule: cluster_connectivity is the gate for every other check.
When it fails, the remaining checks cannot be observed (live mode
would raise on every API call), so they are emitted as status "skip"
with reason_code "skipped_cluster_unreachable" rather than guessed.

Gateway API relevance rule (required_crd_readiness): the contracted
description ties the check to the gateway profile, but profiles are
declared, not observed. The observed-state equivalent used here: the
Gateway API is in use if and only if at least one CRD in the
gateway.networking.k8s.io group exists. If none exist the check is
"skip" (reason_code "gateway_api_not_in_use") - the ingress path
needs no Gateway CRDs. If some exist, the core set (gatewayclasses,
gateways, httproutes) must be complete; a partial install fails with
the Batch 3 reason code "gateway_api_crds_required".

Blocking classification (exit-code contract): a check failure is
always blocking - exit code is non-zero exactly when summary.outcome
is "fail". Two conditions are classified "warn" (non-blocking,
exit 0) because the Batch 18 guided installer can remediate both
without operator surgery:

- storage_compatibility with storage classes present but none
  default (reason_code "default_storage_class_missing"): the
  installer can pin an explicit storageClassName.
- gitops_prerequisites with no controller detected (reason_code
  "gitops_controller_missing"): the kit ships its own ArgoCD
  bootstrap (gitops/bootstrap/argocd/), so absence is installable.

Reason codes reuse the Batch 3 catalog where a code exists for the
failure (cluster_connectivity_failed, rbac_access_missing,
required_api_unavailable, gateway_api_crds_required,
storage_profile_incompatible, gitops_controller_missing); the warn
and skip conditions above have no Batch 3 equivalent and introduce
default_storage_class_missing, gateway_api_not_in_use, and
skipped_cluster_unreachable.

Determinism (TR-18): all inputs come from the reader's stably sorted
accessors, the checks list order is fixed, and emission goes through
obskit.emit.write_report (sorted keys, fixed indentation, trailing
newline). The report body carries no timestamps and no
environment-dependent values.
"""

from __future__ import annotations

from argparse import Namespace
from collections.abc import Callable
from dataclasses import dataclass

from obskit.emit import write_report
from obskit.models import report_metadata
from obskit.reader import ClusterReader, build_reader

SOURCE_MARKER = "TR-18"

# Read permissions the executor needs, derived from the resources the
# bundled RBAC manifest (tools/obskit/rbac/obskit-readonly-rbac.yaml)
# grants. Order mirrors the manifest's rule order; resources use the
# reader's "group/plural" convention ("" group has no prefix). The
# executor only ever lists, so "list" is the verb probed; a subject
# that can list can observe everything the engine reads.
READ_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("list", "namespaces"),
    ("list", "nodes"),
    ("list", "services"),
    ("list", "pods"),
    ("list", "apps/deployments"),
    ("list", "apps/daemonsets"),
    ("list", "apps/statefulsets"),
    ("list", "storage.k8s.io/storageclasses"),
    ("list", "networking.k8s.io/ingressclasses"),
    ("list", "apiextensions.k8s.io/customresourcedefinitions"),
    ("list", "apiregistration.k8s.io/apiservices"),
)

# Group/versions every conformant target cluster must serve: the core
# and apps groups the platform workloads deploy into, batch for the
# optional in-cluster Job mode, RBAC for the delivery layer, and the
# storage/networking/apiextensions/apiregistration groups the
# discovery and preflight observations themselves read.
REQUIRED_API_VERSIONS: tuple[str, ...] = (
    "v1",
    "apps/v1",
    "batch/v1",
    "rbac.authorization.k8s.io/v1",
    "storage.k8s.io/v1",
    "networking.k8s.io/v1",
    "apiextensions.k8s.io/v1",
    "apiregistration.k8s.io/v1",
)

GATEWAY_API_GROUP = "gateway.networking.k8s.io"

# Core Gateway API resource set required once the group is in use.
GATEWAY_REQUIRED_CRDS: tuple[str, ...] = (
    "gatewayclasses.gateway.networking.k8s.io",
    "gateways.gateway.networking.k8s.io",
    "httproutes.gateway.networking.k8s.io",
)

# GitOps controller fingerprints: CRD group suffixes plus the
# controller workload names each project deploys under any namespace.
ARGOCD_CRD_SUFFIX = ".argoproj.io"
ARGOCD_WORKLOAD_PREFIX = "argocd-"
FLUX_CRD_SUFFIX = ".toolkit.fluxcd.io"
FLUX_CONTROLLER_NAMES: frozenset[str] = frozenset(
    {
        "source-controller",
        "kustomize-controller",
        "helm-controller",
        "notification-controller",
    }
)

REASON_CONNECTIVITY_FAILED = "cluster_connectivity_failed"
REASON_RBAC_MISSING = "rbac_access_missing"
REASON_API_UNAVAILABLE = "required_api_unavailable"
REASON_GATEWAY_CRDS_REQUIRED = "gateway_api_crds_required"
REASON_GATEWAY_NOT_IN_USE = "gateway_api_not_in_use"
REASON_STORAGE_INCOMPATIBLE = "storage_profile_incompatible"
REASON_NO_DEFAULT_STORAGE = "default_storage_class_missing"
REASON_GITOPS_MISSING = "gitops_controller_missing"
REASON_SKIPPED_UNREACHABLE = "skipped_cluster_unreachable"

STATUS_PASS = "pass"
STATUS_WARN = "warn"
STATUS_FAIL = "fail"
STATUS_SKIP = "skip"


@dataclass(frozen=True)
class CheckResult:
    """One evaluated preflight check, schema-shaped via to_dict."""

    check_id: str
    description: str
    status: str
    reason_code: str | None = None

    def to_dict(self) -> dict[str, str]:
        item = {
            "id": self.check_id,
            "description": self.description,
            "status": self.status,
        }
        if self.reason_code is not None:
            item["reason_code"] = self.reason_code
        return item


# Contracted descriptions, verbatim from CHECK_CLASSES in
# install/discovery-engine/preflight_checks.py.
_DESCRIPTIONS: dict[str, str] = {
    "cluster_connectivity": (
        "Cluster API reachable with provided credentials."
    ),
    "required_permissions": (
        "Preflight service account can read required resources."
    ),
    "required_api_readiness": (
        "Required APIs and APIService endpoints are available."
    ),
    "required_crd_readiness": (
        "Gateway API CRDs are installed when gateway profile is set."
    ),
    "storage_compatibility": (
        "Detected storage profile is compatible with selected mode."
    ),
    "gitops_prerequisites": (
        "A supported GitOps controller and CRDs are present."
    ),
}


def _check_cluster_connectivity(reader: ClusterReader) -> CheckResult:
    check_id = "cluster_connectivity"
    if reader.connectivity():
        return CheckResult(
            check_id, _DESCRIPTIONS[check_id], STATUS_PASS
        )
    return CheckResult(
        check_id,
        _DESCRIPTIONS[check_id],
        STATUS_FAIL,
        REASON_CONNECTIVITY_FAILED,
    )


def _check_required_permissions(reader: ClusterReader) -> CheckResult:
    check_id = "required_permissions"
    denied = [
        f"{verb}:{resource}"
        for verb, resource in READ_PERMISSIONS
        if not reader.can_i(verb, resource)
    ]
    if not denied:
        return CheckResult(
            check_id, _DESCRIPTIONS[check_id], STATUS_PASS
        )
    return CheckResult(
        check_id,
        _DESCRIPTIONS[check_id],
        STATUS_FAIL,
        REASON_RBAC_MISSING,
    )


def _check_required_api_readiness(reader: ClusterReader) -> CheckResult:
    check_id = "required_api_readiness"
    available = set(reader.api_versions())
    missing = sorted(set(REQUIRED_API_VERSIONS) - available)
    if not missing:
        return CheckResult(
            check_id, _DESCRIPTIONS[check_id], STATUS_PASS
        )
    return CheckResult(
        check_id,
        _DESCRIPTIONS[check_id],
        STATUS_FAIL,
        REASON_API_UNAVAILABLE,
    )


def _check_required_crd_readiness(reader: ClusterReader) -> CheckResult:
    """Gateway API CRDs, gated on observed Gateway API use.

    See the module docstring for the relevance rule: the group being
    entirely absent means the profile is not in use and the check is
    skipped; a partial core set is the contracted failure.
    """
    check_id = "required_crd_readiness"
    crds = set(reader.crd_names())
    gateway_group_present = any(
        name.endswith("." + GATEWAY_API_GROUP) for name in crds
    )
    if not gateway_group_present:
        return CheckResult(
            check_id,
            _DESCRIPTIONS[check_id],
            STATUS_SKIP,
            REASON_GATEWAY_NOT_IN_USE,
        )
    missing = sorted(set(GATEWAY_REQUIRED_CRDS) - crds)
    if not missing:
        return CheckResult(
            check_id, _DESCRIPTIONS[check_id], STATUS_PASS
        )
    return CheckResult(
        check_id,
        _DESCRIPTIONS[check_id],
        STATUS_FAIL,
        REASON_GATEWAY_CRDS_REQUIRED,
    )


def _check_storage_compatibility(reader: ClusterReader) -> CheckResult:
    """Persistent storage must be provisionable.

    OpenSearch and Neo4j both require PersistentVolumes, so zero
    storage classes is a blocking failure. Classes present but none
    default is a warn: charts default to the cluster default class,
    but the installer can pin an explicit storageClassName instead.
    """
    check_id = "storage_compatibility"
    classes = reader.storage_classes()
    if not classes:
        return CheckResult(
            check_id,
            _DESCRIPTIONS[check_id],
            STATUS_FAIL,
            REASON_STORAGE_INCOMPATIBLE,
        )
    if not any(item.default for item in classes):
        return CheckResult(
            check_id,
            _DESCRIPTIONS[check_id],
            STATUS_WARN,
            REASON_NO_DEFAULT_STORAGE,
        )
    return CheckResult(check_id, _DESCRIPTIONS[check_id], STATUS_PASS)


def _check_gitops_prerequisites(reader: ClusterReader) -> CheckResult:
    """Detect a supported GitOps controller (Argo CD or Flux).

    Detection uses two observable fingerprints per project: CRDs in
    the project's API group, or the project's controller workloads by
    name. Absence is a warn, not a failure, because the kit bootstraps
    its own Argo CD (gitops/bootstrap/argocd/).
    """
    check_id = "gitops_prerequisites"
    crds = reader.crd_names()
    workload_names = {item.name for item in reader.workloads()}
    argocd_present = any(
        name.endswith(ARGOCD_CRD_SUFFIX) for name in crds
    ) or any(
        name.startswith(ARGOCD_WORKLOAD_PREFIX)
        for name in workload_names
    )
    flux_present = any(
        name.endswith(FLUX_CRD_SUFFIX) for name in crds
    ) or bool(FLUX_CONTROLLER_NAMES & workload_names)
    if argocd_present or flux_present:
        return CheckResult(
            check_id, _DESCRIPTIONS[check_id], STATUS_PASS
        )
    return CheckResult(
        check_id,
        _DESCRIPTIONS[check_id],
        STATUS_WARN,
        REASON_GITOPS_MISSING,
    )


# Post-connectivity checks in the contracted, stable emission order.
_GATED_CHECKS: tuple[
    tuple[str, Callable[[ClusterReader], CheckResult]], ...
] = (
    ("required_permissions", _check_required_permissions),
    ("required_api_readiness", _check_required_api_readiness),
    ("required_crd_readiness", _check_required_crd_readiness),
    ("storage_compatibility", _check_storage_compatibility),
    ("gitops_prerequisites", _check_gitops_prerequisites),
)


def _summarize(checks: list[CheckResult]) -> dict[str, int | str]:
    counts = {
        status: sum(1 for item in checks if item.status == status)
        for status in (STATUS_PASS, STATUS_WARN, STATUS_FAIL, STATUS_SKIP)
    }
    if counts[STATUS_FAIL] > 0:
        outcome = STATUS_FAIL
    elif counts[STATUS_WARN] > 0:
        outcome = STATUS_WARN
    else:
        outcome = STATUS_PASS
    return {
        "total_checks": len(checks),
        "pass": counts[STATUS_PASS],
        "warn": counts[STATUS_WARN],
        "fail": counts[STATUS_FAIL],
        "skip": counts[STATUS_SKIP],
        "outcome": outcome,
    }


def evaluate_preflight(reader: ClusterReader) -> dict[str, object]:
    """Run every contracted check class against observed state.

    Pure library entry point: takes any ClusterReader, returns the
    report dict shaped by PREFLIGHT_REPORT_SCHEMA.json. Deterministic
    for identical reader state (see module docstring).
    """
    connectivity = _check_cluster_connectivity(reader)
    checks: list[CheckResult] = [connectivity]
    if connectivity.status == STATUS_FAIL:
        checks.extend(
            CheckResult(
                check_id,
                _DESCRIPTIONS[check_id],
                STATUS_SKIP,
                REASON_SKIPPED_UNREACHABLE,
            )
            for check_id, _ in _GATED_CHECKS
        )
    else:
        checks.extend(evaluate(reader) for _, evaluate in _GATED_CHECKS)
    return {
        "metadata": report_metadata(SOURCE_MARKER),
        "cluster": reader.cluster_info().to_dict(),
        "checks": [item.to_dict() for item in checks],
        "summary": _summarize(checks),
    }


def run(args: Namespace) -> int:
    """CLI entry for `obskit preflight` (routed from obskit.cli).

    Returns 0 when summary.outcome is "pass" or "warn" (warn statuses
    are non-blocking by the classification in the module docstring)
    and 1 when any blocking check fails.
    """
    reader = build_reader(
        args.snapshot,
        args.live,
        args.kubeconfig,
        args.context,
        args.cluster_name,
    )
    report = evaluate_preflight(reader)
    write_report(report, args.output)
    summary = report["summary"]
    assert isinstance(summary, dict)
    return 0 if summary["outcome"] != STATUS_FAIL else 1
