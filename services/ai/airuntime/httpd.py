"""Minimal stdlib HTTP plumbing shared by the runtime entrypoints.

Every runtime component (kagent controller, MCP gateway, MCP server
host) serves the same probe surface the gitops/platform/ai manifests
declare (/healthz, /readyz) plus a JSON API routed by exact
(method, path-prefix) pairs. ThreadingHTTPServer keeps slow handlers
(tool calls with contract-bounded timeouts) from blocking probes.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

Handler = Callable[[str, dict[str, Any]], tuple[int, dict[str, Any]]]


class JsonApi:
    """Route table: (method, prefix) -> handler(subpath, body)."""

    def __init__(self, component: str) -> None:
        self.component = component
        self.ready = True
        self._routes: list[tuple[str, str, Handler]] = []

    def route(self, method: str, prefix: str, handler: Handler) -> None:
        self._routes.append((method, prefix, handler))

    def dispatch(
        self, method: str, path: str, body: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/healthz":
            return 200, {"status": "ok", "component": self.component}
        if method == "GET" and path == "/readyz":
            if self.ready:
                return 200, {"status": "ready", "component": self.component}
            return 503, {"status": "not-ready", "component": self.component}
        for route_method, prefix, handler in self._routes:
            if method == route_method and path.startswith(prefix):
                subpath = path[len(prefix):].strip("/")
                return handler(subpath, body)
        return 404, {"error": f"no route for {method} {path}"}


def serve(api: JsonApi, port: int) -> None:
    class _RequestHandler(BaseHTTPRequestHandler):
        def _respond(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                self._write(400, {"error": "invalid JSON body"})
                return
            try:
                status, payload = api.dispatch(
                    self.command, self.path.split("?", 1)[0], body
                )
            except KeyError as exc:
                status, payload = 400, {"error": f"missing field {exc}"}
            except Exception as exc:  # fail loudly, never silently
                status, payload = 500, {"error": str(exc)}
            self._write(status, payload)

        def _write(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, sort_keys=True).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            self._respond()

        def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
            self._respond()

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[{api.component}] {fmt % args}")

    ThreadingHTTPServer(("0.0.0.0", port), _RequestHandler).serve_forever()


def http_json(
    method: str,
    url: str,
    body: dict[str, Any] | None = None,
    timeout: float = 10.0,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Stdlib JSON client used for component-to-component calls."""
    import urllib.error
    import urllib.request

    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    for name, value in (headers or {}).items():
        request.add_header(name, value)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read() or b"{}")
        except json.JSONDecodeError:
            return exc.code, {"error": "non-JSON error body"}
