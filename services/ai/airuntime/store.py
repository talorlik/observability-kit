"""Persistence layer for the AI runtime control plane.

Executes contracts/ai/KAGENT_PERSISTENCE_CONTRACT_V1.yaml: three schema
namespaces (kagent_core, kagent_runs, kagent_audit), a write-once audit
trail, and the contract's connection secret vocabulary. PostgreSQL is
the contracted engine (behind the [postgres] extra, pure-Python
pg8000); the SQLite store is interface-identical and exists for
offline CI tests and local development only - it maps the schema
namespaces onto table-name prefixes because SQLite has no schemas.

The audit namespace is write-once by API surface: this module exposes
append and select for audit records and no update or delete path.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Protocol

SCHEMA_NAMESPACES = ("kagent_core", "kagent_runs", "kagent_audit")

_DDL = {
    "kagent_core.agents": (
        "agent_id TEXT PRIMARY KEY",
        "role TEXT NOT NULL",
        "registered_at TEXT NOT NULL",
    ),
    "kagent_runs.casefiles": (
        "casefile_id TEXT PRIMARY KEY",
        "tenant_id TEXT NOT NULL",
        "status TEXT NOT NULL",
        "created_at TEXT NOT NULL",
        "updated_at TEXT NOT NULL",
        "document TEXT NOT NULL",
    ),
    "kagent_runs.approvals": (
        "approval_id TEXT PRIMARY KEY",
        "casefile_id TEXT NOT NULL",
        "tool TEXT NOT NULL",
        "risk_class TEXT NOT NULL",
        "requested_by TEXT NOT NULL",
        "requested_at TEXT NOT NULL",
        "deadline_at TEXT NOT NULL",
        "warning_at TEXT NOT NULL",
        "state TEXT NOT NULL",
        "approver TEXT",
        "decision TEXT",
        "decided_at TEXT",
        # APPROVAL_FLOW_V1 required_approval_fields: approved
        # write.critical records must persist their change_ticket.
        "change_ticket TEXT",
        "escalation TEXT NOT NULL",
    ),
    "kagent_audit.records": (
        "record_id INTEGER PRIMARY KEY AUTOINCREMENT",
        "casefile_id TEXT",
        "tenant_id TEXT",
        "event_type TEXT NOT NULL",
        "actor TEXT NOT NULL",
        "payload TEXT NOT NULL",
        "recorded_at TEXT NOT NULL",
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AuditRecord:
    event_type: str
    actor: str
    payload: dict[str, Any]
    casefile_id: str | None = None
    tenant_id: str | None = None
    recorded_at: str = field(default_factory=utc_now)


class Store(Protocol):
    """Interface both engines implement; KAgent depends only on this."""

    def init_schema(self) -> None: ...

    def upsert_casefile(self, casefile: dict[str, Any]) -> None: ...

    def get_casefile(self, casefile_id: str) -> dict[str, Any] | None: ...

    def list_casefiles(self) -> list[dict[str, Any]]: ...

    def insert_approval(self, approval: dict[str, Any]) -> None: ...

    def update_approval(self, approval: dict[str, Any]) -> None: ...

    def get_approval(self, approval_id: str) -> dict[str, Any] | None: ...

    def list_approvals(self, state: str | None = None) -> list[dict[str, Any]]: ...

    def append_audit(self, record: AuditRecord) -> None: ...

    def audit_records(self) -> list[dict[str, Any]]: ...


_APPROVAL_COLUMNS = (
    "approval_id", "casefile_id", "tool", "risk_class", "requested_by",
    "requested_at", "deadline_at", "warning_at", "state", "approver",
    "decision", "decided_at", "change_ticket", "escalation",
)


class _SqlStoreBase:
    """Shared SQL logic; subclasses provide connection + name mapping."""

    placeholder = "?"

    def _table(self, namespaced: str) -> str:
        raise NotImplementedError

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        raise NotImplementedError

    def init_schema(self) -> None:
        for name, columns in _DDL.items():
            ddl_columns = ", ".join(columns)
            if self.placeholder == "%s":
                ddl_columns = ddl_columns.replace(
                    "INTEGER PRIMARY KEY AUTOINCREMENT",
                    "BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY",
                )
            self._execute(
                f"CREATE TABLE IF NOT EXISTS {self._table(name)} "
                f"({ddl_columns})"
            )

    def upsert_casefile(self, casefile: dict[str, Any]) -> None:
        table = self._table("kagent_runs.casefiles")
        ph = self.placeholder
        self._execute(
            f"INSERT INTO {table} (casefile_id, tenant_id, status, "
            f"created_at, updated_at, document) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}) "
            f"ON CONFLICT (casefile_id) DO UPDATE SET "
            f"status = EXCLUDED.status, updated_at = EXCLUDED.updated_at, "
            f"document = EXCLUDED.document",
            (
                casefile["casefile_id"],
                casefile["tenant_id"],
                casefile["status"],
                casefile["created_at"],
                casefile["updated_at"],
                json.dumps(casefile, sort_keys=True),
            ),
        )

    def get_casefile(self, casefile_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            f"SELECT document FROM {self._table('kagent_runs.casefiles')} "
            f"WHERE casefile_id = {self.placeholder}",
            (casefile_id,),
        )
        return json.loads(rows[0][0]) if rows else None

    def list_casefiles(self) -> list[dict[str, Any]]:
        rows = self._execute(
            f"SELECT document FROM {self._table('kagent_runs.casefiles')} "
            f"ORDER BY created_at"
        )
        return [json.loads(row[0]) for row in rows]

    def insert_approval(self, approval: dict[str, Any]) -> None:
        table = self._table("kagent_runs.approvals")
        placeholders = ", ".join([self.placeholder] * len(_APPROVAL_COLUMNS))
        values = tuple(
            json.dumps(approval[column], sort_keys=True)
            if column == "escalation" else approval.get(column)
            for column in _APPROVAL_COLUMNS
        )
        self._execute(
            f"INSERT INTO {table} ({', '.join(_APPROVAL_COLUMNS)}) "
            f"VALUES ({placeholders})",
            values,
        )

    def update_approval(self, approval: dict[str, Any]) -> None:
        table = self._table("kagent_runs.approvals")
        ph = self.placeholder
        self._execute(
            f"UPDATE {table} SET state = {ph}, approver = {ph}, "
            f"decision = {ph}, decided_at = {ph}, change_ticket = {ph} "
            f"WHERE approval_id = {ph}",
            (
                approval["state"],
                approval.get("approver"),
                approval.get("decision"),
                approval.get("decided_at"),
                approval.get("change_ticket"),
                approval["approval_id"],
            ),
        )

    def _row_to_approval(self, row: tuple) -> dict[str, Any]:
        approval = dict(zip(_APPROVAL_COLUMNS, row))
        approval["escalation"] = json.loads(approval["escalation"])
        return approval

    def get_approval(self, approval_id: str) -> dict[str, Any] | None:
        rows = self._execute(
            f"SELECT {', '.join(_APPROVAL_COLUMNS)} "
            f"FROM {self._table('kagent_runs.approvals')} "
            f"WHERE approval_id = {self.placeholder}",
            (approval_id,),
        )
        return self._row_to_approval(rows[0]) if rows else None

    def list_approvals(self, state: str | None = None) -> list[dict[str, Any]]:
        table = self._table("kagent_runs.approvals")
        columns = ", ".join(_APPROVAL_COLUMNS)
        if state is None:
            rows = self._execute(
                f"SELECT {columns} FROM {table} ORDER BY requested_at"
            )
        else:
            rows = self._execute(
                f"SELECT {columns} FROM {table} "
                f"WHERE state = {self.placeholder} ORDER BY requested_at",
                (state,),
            )
        return [self._row_to_approval(row) for row in rows]

    def append_audit(self, record: AuditRecord) -> None:
        table = self._table("kagent_audit.records")
        ph = self.placeholder
        self._execute(
            f"INSERT INTO {table} (casefile_id, tenant_id, event_type, "
            f"actor, payload, recorded_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (
                record.casefile_id,
                record.tenant_id,
                record.event_type,
                record.actor,
                json.dumps(record.payload, sort_keys=True),
                record.recorded_at,
            ),
        )

    def audit_records(self) -> list[dict[str, Any]]:
        rows = self._execute(
            f"SELECT record_id, casefile_id, tenant_id, event_type, actor, "
            f"payload, recorded_at "
            f"FROM {self._table('kagent_audit.records')} ORDER BY record_id"
        )
        return [
            {
                "record_id": row[0],
                "casefile_id": row[1],
                "tenant_id": row[2],
                "event_type": row[3],
                "actor": row[4],
                "payload": json.loads(row[5]),
                "recorded_at": row[6],
            }
            for row in rows
        ]


class SqliteStore(_SqlStoreBase):
    """Offline-test and local-dev store. Namespaces become prefixes."""

    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()

    def _table(self, namespaced: str) -> str:
        return namespaced.replace(".", "_")

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        with self._lock:
            cursor = self._conn.execute(sql, tuple(params))
            rows = cursor.fetchall() if cursor.description else []
            self._conn.commit()
            return rows


class PostgresStore(_SqlStoreBase):
    """Contracted engine (KAGENT_PERSISTENCE_CONTRACT_V1.yaml).

    Real PostgreSQL schemas mirror the contract's schema namespaces.
    Requires the [postgres] extra (pg8000).
    """

    placeholder = "%s"

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        sslmode: str = "disable",
    ) -> None:
        import pg8000.dbapi  # deferred: [postgres] extra only

        self._conn = pg8000.dbapi.Connection(
            user=username,
            password=password,
            host=host,
            port=port,
            database=database,
            ssl_context=None if sslmode == "disable" else True,
        )
        self._lock = threading.Lock()

    def _table(self, namespaced: str) -> str:
        return namespaced

    def init_schema(self) -> None:
        for namespace in SCHEMA_NAMESPACES:
            self._execute(f"CREATE SCHEMA IF NOT EXISTS {namespace}")
        super().init_schema()

    def _execute(self, sql: str, params: Iterable[Any] = ()) -> list[tuple]:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall() if cursor.description else []
            self._conn.commit()
            return [tuple(row) for row in rows]


def store_from_env(env: dict[str, str]) -> Store:
    """Build the store the deployment environment prescribes.

    KAGENT_STORE=postgres reads the contract secret keys
    (KAGENT_POSTGRES_HOST/PORT/DB/USER/PASSWORD/SSLMODE, materialized
    from the kagent-postgres-credentials secret). Anything else falls
    back to SQLite at KAGENT_SQLITE_PATH (default in-memory).
    """
    if env.get("KAGENT_STORE") == "postgres":
        return PostgresStore(
            host=env["KAGENT_POSTGRES_HOST"],
            port=int(env["KAGENT_POSTGRES_PORT"]),
            database=env["KAGENT_POSTGRES_DB"],
            username=env["KAGENT_POSTGRES_USER"],
            password=env["KAGENT_POSTGRES_PASSWORD"],
            sslmode=env.get("KAGENT_POSTGRES_SSLMODE", "disable"),
        )
    return SqliteStore(env.get("KAGENT_SQLITE_PATH", ":memory:"))
