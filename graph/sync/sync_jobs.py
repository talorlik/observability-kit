#!/usr/bin/env python3

"""Minimal Batch 11 sync helpers for idempotent graph writes."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Iterable


@dataclass(frozen=True)
class ServiceEdge:
    source: str
    target: str
    environment: str


def dependency_merge_query() -> str:
    """Return MERGE-based query used for replay-safe dependency upserts."""
    return (
        "MERGE (src:Service {name: $source, environment: $environment}) "
        "MERGE (dst:Service {name: $target, environment: $environment}) "
        "MERGE (src)-[r:DEPENDS_ON]->(dst) "
        "ON CREATE SET r.first_seen = timestamp() "
        "SET r.last_seen = timestamp()"
    )


def state_fingerprint(edges: Iterable[ServiceEdge]) -> str:
    """Generate stable fingerprint to confirm repeated-run convergence."""
    normalized = sorted(
        [
            {"source": edge.source, "target": edge.target, "environment": edge.environment}
            for edge in edges
        ],
        key=lambda item: (item["environment"], item["source"], item["target"]),
    )
    payload = json.dumps(normalized, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
