"""Observability Kit AI/MCP runtime (Batch 24, ADR-0009).

One typed, stdlib-core package with four entrypoints, selected as the
container argument (`python3 -m airuntime <component>`):

- ``kagent``    - controller: casefile orchestration, investigation
                  runs, action-gate approvals, audit (TR-15).
- ``khook``     - Kubernetes event trigger dispatcher with dedupe and
                  burst control, read-only dispatch (triggers/khook/).
- ``gateway``   - MCP gateway: catalog-scoped routing, identity access
                  matrix, tool risk classification, response envelope
                  and redaction enforcement, deny-on-failover
                  (contracts/mcp/).
- ``mcpserver`` - read-path MCP tool host for the services/mcp/
                  service contracts.

The runtime executes the repository contracts verbatim through
constants embedded in :mod:`airuntime.contracts`;
scripts/ci/validate_ai_activation.sh cross-checks those constants
against the contract YAML sources (no YAML import at runtime).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
