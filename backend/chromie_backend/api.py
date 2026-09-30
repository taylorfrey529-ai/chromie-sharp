from __future__ import annotations

from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from typing import Any
from urllib.parse import parse_qs, urlparse
import uuid

from .client_service import ClientService
from .diagnostics_service import DiagnosticsService
from .launcher_service import LauncherService
from .models import OperationResult, utc_now
from .server_service import ServerService
from .status_service import StatusService


@dataclass(slots=True)
class Services:
    status: StatusService
    server: ServerService
    client: ClientService
    diagnostics: DiagnosticsService
    launcher: LauncherService


def envelope(request_id: str, operation: str, success: bool, *, data: Any = None, error_code: str | None = None, message: str | None = None) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "timestamp": utc_now(),
        "operation": operation,
        "success": success,
        "error_code": error_code,
        "message": message,
        "data": data,
    }


def build_server(host: str, port: int, services: Services) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ChromieSharp/0.2"

        def log_message(self, fmt: str, *args: object) -> None:
            return

        def _request_id(self) -> str:
            supplied = self.headers.get("X-Request-Id", "").strip()
            return supplied[:128] if supplied else str(uuid.uuid4())

        def _send(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
            self.send_response(int(status))
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _result(self, request_id: str, operation: str, result: OperationResult) -> None:
            status = HTTPStatus.OK if result.ok else HTTPStatus.CONFLICT
            self._send(
                status,
                envelope(
                    request_id,
                    operation,
                    result.ok,
                    data=result.evidence,
                    error_code=None if result.ok else result.code,
                    message=result.message,
                ),
            )

        def do_GET(self) -> None:  # noqa: N802
            request_id = self._request_id()
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            if path == "/api/v1/health":
                self._send(HTTPStatus.OK, envelope(request_id, "health", True, data={"service": "chromie_backend", "version": "v1"}))
            elif path == "/api/v1/status":
                self._send(HTTPStatus.OK, envelope(request_id, "status", True, data=services.status.snapshot().to_dict()))
            elif path == "/api/v1/launcher/status":
                self._send(HTTPStatus.OK, envelope(request_id, "launcher.status", True, data=services.launcher.status()))
            elif path == "/api/v1/client/preflight":
                self._result(request_id, "client.preflight", services.client.preflight())
            elif path == "/api/v1/logs":
                query = parse_qs(parsed.query)
                try:
                    lines = int(query.get("lines", ["100"])[0])
                except ValueError:
                    lines = 100
                self._send(HTTPStatus.OK, envelope(request_id, "logs", True, data=services.diagnostics.tail(lines)))
            else:
                self._send(
                    HTTPStatus.NOT_FOUND,
                    envelope(request_id, "unknown", False, error_code="NOT_FOUND", message="Unknown endpoint"),
                )

        def do_POST(self) -> None:  # noqa: N802
            request_id = self._request_id()
            path = urlparse(self.path).path.rstrip("/")
            server_actions = {
                "/api/v1/server/start": "start",
                "/api/v1/server/stop": "stop",
                "/api/v1/server/restart": "restart",
            }
            if path in server_actions:
                action = server_actions[path]
                self._result(request_id, f"server.{action}", services.server.action(action))
            elif path == "/api/v1/client/preflight":
                self._result(request_id, "client.preflight", services.client.preflight())
            elif path == "/api/v1/client/launch":
                self._result(request_id, "client.launch", services.client.launch())
            elif path == "/api/v1/launcher/play":
                self._result(request_id, "launcher.play", services.launcher.play())
            elif path == "/api/v1/launcher/repair":
                self._result(request_id, "launcher.repair", services.launcher.repair_plan())
            else:
                self._send(
                    HTTPStatus.NOT_FOUND,
                    envelope(request_id, "unknown", False, error_code="NOT_FOUND", message="Unknown endpoint"),
                )

    return ThreadingHTTPServer((host, port), Handler)
