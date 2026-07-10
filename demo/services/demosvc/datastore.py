"""Demo datastore-backed service (Batch 27, ADR-0011).

A JSON API on port 8081 backed by stdlib ``sqlite3`` in-pod (ADR-0011
decision 4: genuine ``db.*`` client spans without a database pod).
Every HTTP request is a SERVER span continuing the caller's
traceparent; every SQL operation underneath it is a CLIENT span with
``db.system=sqlite``, ``db.operation.name``, and ``db.query.text``
attributes, plus a ``demo.db.operations`` counter and a
``demo.db.duration`` histogram.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from demosvc.otel import Telemetry, TraceContext

_DEFAULT_DB_PATH = "/tmp/demo.db"

_CREATE_TABLE_SQL = (
    "CREATE TABLE IF NOT EXISTS orders ("
    "id INTEGER PRIMARY KEY AUTOINCREMENT, "
    "item TEXT NOT NULL, "
    "quantity INTEGER NOT NULL, "
    "created_at REAL NOT NULL)"
)
_INSERT_SQL = (
    "INSERT INTO orders (item, quantity, created_at) VALUES (?, ?, ?)"
)
_SELECT_SQL = (
    "SELECT id, item, quantity, created_at FROM orders "
    "ORDER BY id DESC LIMIT ?"
)
_COUNT_SQL = "SELECT COUNT(id) FROM orders"


class OrderStore:
    """SQLite-backed order store; every operation is span-wrapped."""

    def __init__(self, path: str, telemetry: Telemetry) -> None:
        self._path = path
        self._telemetry = telemetry
        self._execute("CREATE", _CREATE_TABLE_SQL, (), parent=None)

    def insert_order(
        self, item: str, quantity: int, parent: TraceContext | None
    ) -> int:
        rows = self._execute(
            "INSERT", _INSERT_SQL, (item, quantity, time.time()), parent
        )
        # _execute returns [(lastrowid,)] for INSERT.
        return int(rows[0][0])

    def list_orders(
        self, limit: int, parent: TraceContext | None
    ) -> list[dict[str, object]]:
        rows = self._execute("SELECT", _SELECT_SQL, (limit,), parent)
        return [
            {
                "order_id": row[0],
                "item": row[1],
                "quantity": row[2],
                "created_at": row[3],
            }
            for row in rows
        ]

    def count_orders(self, parent: TraceContext | None) -> int:
        rows = self._execute("SELECT", _COUNT_SQL, (), parent)
        return int(rows[0][0])

    def _execute(
        self,
        operation: str,
        query: str,
        params: tuple[object, ...],
        parent: TraceContext | None,
    ) -> list[tuple[object, ...]]:
        """Run one statement under a db-client CLIENT span.

        A connection per operation keeps the store trivially safe
        under the threading HTTP server; at demo traffic volume the
        connect cost is noise.
        """
        telemetry = self._telemetry
        started = time.monotonic()
        with telemetry.span(
            f"sqlite.{operation.lower()} orders",
            kind="CLIENT",
            parent=parent,
            attributes={
                "db.system": "sqlite",
                "db.operation.name": operation,
                "db.query.text": query,
                "db.collection.name": "orders",
                "db.namespace": self._path,
            },
        ):
            connection = sqlite3.connect(self._path, timeout=5)
            try:
                cursor = connection.execute(query, params)
                if operation == "INSERT":
                    rows: list[tuple[object, ...]] = [(cursor.lastrowid,)]
                else:
                    rows = list(cursor.fetchall())
                connection.commit()
            finally:
                connection.close()
        duration_ms = (time.monotonic() - started) * 1000.0
        telemetry.counter(
            "demo.db.operations", 1, {"db.operation.name": operation}
        )
        telemetry.histogram(
            "demo.db.duration", duration_ms, {"db.operation.name": operation}
        )
        return rows


class DatastoreHandler(BaseHTTPRequestHandler):
    """Routes: POST /orders, GET /orders, GET /status, GET /healthz."""

    # Injected by main() (and by the offline tests).
    telemetry: Telemetry
    store: OrderStore

    server_version = "demo-datastore/0.1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        """Access logs are emitted as trace-correlated OTLP records."""

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        self._handle("GET")

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        self._handle("POST")

    def _handle(self, method: str) -> None:
        route = self.path.split("?", 1)[0]
        if route == "/healthz":
            self._respond(200, {"status": "ok"})
            return

        telemetry = self.telemetry
        parent = TraceContext.from_traceparent(self.headers.get("traceparent"))
        started = time.monotonic()
        status = 500
        body: dict[str, object] = {"error": "internal"}
        with telemetry.span(
            f"{method} {route}",
            kind="SERVER",
            parent=parent,
            attributes={
                "http.request.method": method,
                "http.route": route,
            },
        ) as span:
            try:
                status, body = self._dispatch(method, route, span.context)
            except sqlite3.Error as exc:
                status, body = 500, {"error": f"db failure: {exc}"}
                span.set_status(False, f"db failure: {exc}")
                telemetry.log(
                    "ERROR",
                    f"database failure on {method} {route}: {exc}",
                    {"http.route": route},
                    trace=span.context,
                )
            span.set_attribute("http.response.status_code", status)
            telemetry.log(
                "INFO",
                f"{method} {route} -> {status}",
                {
                    "http.route": route,
                    "http.response.status_code": status,
                },
                trace=span.context,
            )

        duration_ms = (time.monotonic() - started) * 1000.0
        telemetry.counter(
            "demo.http.requests",
            1,
            {
                "http.route": route,
                "http.request.method": method,
                "http.response.status_code": status,
            },
        )
        telemetry.histogram(
            "demo.http.server.duration", duration_ms, {"http.route": route}
        )
        self._respond(status, body)

    def _dispatch(
        self, method: str, route: str, parent: TraceContext
    ) -> tuple[int, dict[str, object]]:
        if route == "/orders" and method == "POST":
            payload = self._read_json()
            item = str(payload.get("item", "widget"))
            quantity = int(payload.get("quantity", 1) or 1)
            order_id = self.store.insert_order(item, quantity, parent)
            return 201, {"order_id": order_id}
        if route == "/orders" and method == "GET":
            return 200, {"orders": self.store.list_orders(50, parent)}
        if route == "/status" and method == "GET":
            return 200, {
                "service": "demo-datastore",
                "orders": self.store.count_orders(parent),
            }
        return 404, {"error": f"no route {method} {route}"}

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return {}
        try:
            parsed = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _respond(self, status: int, body: dict[str, object]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def build_server(
    telemetry: Telemetry, store: OrderStore, port: int
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredDatastoreHandler",
        (DatastoreHandler,),
        {"telemetry": telemetry, "store": store},
    )
    return ThreadingHTTPServer(("0.0.0.0", port), handler)


def main() -> None:
    telemetry = Telemetry("demo-datastore")
    db_path = os.environ.get("DEMO_DB_PATH", _DEFAULT_DB_PATH)
    port = int(os.environ.get("DEMO_HTTP_PORT", "8081"))
    store = OrderStore(db_path, telemetry)
    server = build_server(telemetry, store, port)
    telemetry.log(
        "INFO",
        f"demo-datastore listening on :{port}",
        {"db.namespace": db_path},
    )
    telemetry.flush()
    try:
        server.serve_forever()
    finally:
        telemetry.flush()


if __name__ == "__main__":
    main()
