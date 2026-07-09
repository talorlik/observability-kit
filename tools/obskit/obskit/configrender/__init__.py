"""Configuration rendering runtime (Batch 19, TR-20, ADR-0003).

Implements `obskit render` - the execution engine for the propagation
and reconciliation contract
(contracts/management/PROPAGATION_RECONCILIATION_CONTRACT_V1.yaml):
the unified configuration document becomes committed native
configuration at each binding's render_target, deterministically and
GitOps-only. `obskit drift` and `obskit rollback` (Tasks 3-4) are
wired as stubs in this build.
"""
