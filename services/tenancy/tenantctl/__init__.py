"""Tenant control plane service core (Batch 20 Task 2, TR-21).

Implements the contract-bearing logic of the tenant control plane
fixed by contracts/tenancy/TENANT_CONTROL_PLANE_API_V1.yaml and
contracts/tenancy/TENANT_LIFECYCLE_CONTRACT_V1.yaml (ADR-0004): the
lifecycle state machine, idempotent-replay evaluation, approval-gate
checks, audit-record construction, and GitOps render planning.

Two-layer architecture per ADR-0004: everything in this package except
tenantctl.api is standard-library-only (plus the repo's own obskit
package consumed as a library) and fixture-testable offline. The
FastAPI adapter in tenantctl.api degrades gracefully when FastAPI is
not installed: the module stays importable and build_app raises a
clear error.
"""

from __future__ import annotations

__version__ = "0.1.0"
