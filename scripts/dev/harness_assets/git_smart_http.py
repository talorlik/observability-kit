"""Smart-HTTP git server over TLS for the evidence harness.

Argo CD's repo-server lists refs with go-git, which speaks only the
smart HTTP protocol, so a static (dumb) server cannot serve the
disposable GitOps clone. This shim answers the two smart-protocol
endpoints by delegating to `git http-backend` as a CGI subprocess:

    GET  /<repo>/info/refs?service=git-upload-pack
    POST /<repo>/git-upload-pack

Read-only by construction: receive-pack is never advertised
(http.receivepack stays unset) and the harness ships the repository
with kubectl cp, not pushes. TLS comes from the per-run self-signed
certificate the harness mounts at /certs.

Runs inside the git-server pod (python:3.12-alpine plus the git
package); not a product component.
"""

from __future__ import annotations

import http.server
import os
import ssl
import subprocess
import urllib.parse

REPO_ROOT = "/repos"
PORT = 8443
CERT = "/certs/tls.crt"
KEY = "/certs/tls.key"


class GitSmartHTTPHandler(http.server.BaseHTTPRequestHandler):
    """CGI bridge to `git http-backend`."""

    protocol_version = "HTTP/1.1"

    def _delegate(self, body: bytes | None) -> None:
        parsed = urllib.parse.urlparse(self.path)
        env = dict(os.environ)
        env.update(
            {
                "GIT_PROJECT_ROOT": REPO_ROOT,
                "GIT_HTTP_EXPORT_ALL": "1",
                "PATH_INFO": parsed.path,
                "QUERY_STRING": parsed.query,
                "REQUEST_METHOD": self.command,
                "REMOTE_ADDR": self.client_address[0],
                "CONTENT_TYPE": self.headers.get(
                    "content-type", ""
                ),
                "HTTP_CONTENT_ENCODING": self.headers.get(
                    "content-encoding", ""
                ),
            }
        )
        if body is not None:
            env["CONTENT_LENGTH"] = str(len(body))
        completed = subprocess.run(
            ["git", "http-backend"],
            input=body,
            env=env,
            capture_output=True,
        )
        raw = completed.stdout
        # CGI header terminator: git http-backend emits LF or CRLF
        # depending on platform; accept both or the payload is lost.
        crlf_index = raw.find(b"\r\n\r\n")
        lf_index = raw.find(b"\n\n")
        if crlf_index != -1 and (
            lf_index == -1 or crlf_index <= lf_index
        ):
            header_blob = raw[:crlf_index]
            payload = raw[crlf_index + 4:]
        elif lf_index != -1:
            header_blob = raw[:lf_index]
            payload = raw[lf_index + 2:]
        else:
            header_blob = raw
            payload = b""
        status = 200
        headers: list[tuple[str, str]] = []
        for line in header_blob.decode(
            "latin-1", errors="replace"
        ).splitlines():
            if not line.strip():
                continue
            key, _, value = line.partition(":")
            if key.strip().lower() == "status":
                status = int(value.strip().split()[0])
            else:
                headers.append((key.strip(), value.strip()))
        self.send_response(status)
        for key, value in headers:
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        self._delegate(None)

    def do_POST(self) -> None:  # noqa: N802 (http.server API)
        length = int(self.headers.get("content-length", "0"))
        self._delegate(self.rfile.read(length))

    def log_message(self, format: str, *args: object) -> None:
        print(f"{self.address_string()} {format % args}", flush=True)


def main() -> None:
    server = http.server.ThreadingHTTPServer(
        ("0.0.0.0", PORT), GitSmartHTTPHandler
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(CERT, KEY)
    server.socket = context.wrap_socket(
        server.socket, server_side=True
    )
    print(f"git smart-http server listening on :{PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
