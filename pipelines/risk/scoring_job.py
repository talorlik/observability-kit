#!/usr/bin/env python3

"""Deterministic risk scoring job for Batch 12."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Dict


@dataclass(frozen=True)
class ServiceSignals:
    incident_frequency_30d: int
    dependency_blast_radius_score: float
    error_budget_burn_rate_6h: float
    change_failure_rate_14d: float


WEIGHTS: Dict[str, float] = {
    "incident_frequency_30d": 0.30,
    "dependency_blast_radius_score": 0.25,
    "error_budget_burn_rate_6h": 0.30,
    "change_failure_rate_14d": 0.15,
}


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(value, upper))


def score_service(signals: ServiceSignals) -> int:
    """Return deterministic integer score in [0, 100]."""
    weighted = (
        signals.incident_frequency_30d * WEIGHTS["incident_frequency_30d"]
        + signals.dependency_blast_radius_score * WEIGHTS["dependency_blast_radius_score"]
        + signals.error_budget_burn_rate_6h * WEIGHTS["error_budget_burn_rate_6h"]
        + signals.change_failure_rate_14d * WEIGHTS["change_failure_rate_14d"]
    )
    return int(round(_clamp(weighted)))


def score_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def deterministic_run_fingerprint(service_scores: Dict[str, int]) -> str:
    """Stable hash for run-to-run determinism validation."""
    payload = json.dumps(service_scores, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
