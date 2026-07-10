"""Observability Kit demo playground services (Batch 27, ADR-0011).

One standard-library-only package, five entrypoints selected by the
container args: ``http-api``, ``worker``, ``scheduled-job``,
``datastore``, and ``loadgen``. All telemetry is emitted as OTLP/HTTP
JSON to the platform gateway collector by :mod:`demosvc.otel`; no
service writes to OpenSearch or Neo4j directly.
"""

__version__ = "0.1.0"
