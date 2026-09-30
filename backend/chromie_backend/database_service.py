from __future__ import annotations

import socket

from .models import ComponentState


class DatabaseService:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port

    def status(self) -> ComponentState:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.35):
                return ComponentState("reachable", {"host": self.host, "port": self.port})
        except OSError as exc:
            return ComponentState(
                "unreachable",
                {"host": self.host, "port": self.port, "error": type(exc).__name__},
            )
