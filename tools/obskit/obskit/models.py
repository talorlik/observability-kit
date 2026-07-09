"""Shared structured-data primitives for the obskit executor.

Frozen dataclasses only (TR-18: type hints mandatory, dataclasses for
structured data). Module-specific report models live with their
modules; this file holds only shapes shared across preflight,
discovery, and evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass

REPORT_VERSION = "v1"
REPORT_OWNER = "platform-observability"


@dataclass(frozen=True)
class ClusterInfo:
    """Identity of the cluster a report describes."""

    name: str
    kubernetes_version: str
    distribution: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "kubernetes_version": self.kubernetes_version,
            "distribution": self.distribution,
        }


@dataclass(frozen=True)
class StorageClassInfo:
    name: str
    provisioner: str
    default: bool


@dataclass(frozen=True)
class IngressClassInfo:
    name: str
    controller: str


@dataclass(frozen=True)
class WorkloadRef:
    """A workload controller observed in the cluster."""

    namespace: str
    name: str
    kind: str


@dataclass(frozen=True)
class ServiceInfo:
    namespace: str
    name: str
    ports: tuple[int, ...]


def report_metadata(source_marker: str) -> dict[str, str]:
    """Metadata block required by every report schema.

    Deliberately carries no timestamps or host-derived values: reports
    must be byte-identical for identical inputs (TR-18 determinism).
    """
    return {
        "version": REPORT_VERSION,
        "owner": REPORT_OWNER,
        "source_marker": source_marker,
    }
