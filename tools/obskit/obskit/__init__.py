"""Observability Kit discovery and preflight execution engine.

Batch 17 (TB-17, TR-18). The core is standard-library-only; the
Kubernetes client is an optional extra imported lazily by the live
reader. Boundaries are contracted in
contracts/discovery/EXECUTOR_ARCHITECTURE_CONTRACT_V1.yaml and decided
in docs/adr/ADR_0001_DISCOVERY_EXECUTOR_ARCHITECTURE.md.
"""

__version__ = "0.1.0"
