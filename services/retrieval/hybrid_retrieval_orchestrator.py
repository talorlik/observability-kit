#!/usr/bin/env python3

"""Hybrid retrieval orchestration for RCA evidence bundles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    incident_id: str
    vector_evidence_links: List[str]
    graph_evidence_links: List[str]
    traceable_lineage: bool


def build_bundle(
    bundle_id: str,
    incident_id: str,
    vector_links: List[str],
    graph_links: List[str],
) -> EvidenceBundle:
    """Construct evidence bundle requiring both vector and graph sources."""
    if not vector_links:
        raise ValueError("vector_links must not be empty")
    if not graph_links:
        raise ValueError("graph_links must not be empty")
    return EvidenceBundle(
        bundle_id=bundle_id,
        incident_id=incident_id,
        vector_evidence_links=vector_links,
        graph_evidence_links=graph_links,
        traceable_lineage=True,
    )
