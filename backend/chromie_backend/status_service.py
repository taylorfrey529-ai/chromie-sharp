from __future__ import annotations

from pathlib import Path
import os
import shutil

from .client_service import ClientService
from .database_service import DatabaseService
from .models import ChromieStatus, ComponentState, utc_now
from .server_service import ServerService
from .workbench import WorkbenchLocator


class StatusService:
    def __init__(
        self,
        locator: WorkbenchLocator,
        database: DatabaseService,
        server: ServerService,
        client: ClientService,
        display: str,
    ) -> None:
        self.locator = locator
        self.database = database
        self.server = server
        self.client = client
        self.display = display

    def snapshot(self) -> ChromieStatus:
        auth, world = self.server.status()
        display_state = self._display_state()
        return ChromieStatus(
            timestamp=utc_now(),
            workbench=self.locator.state(),
            database=self.database.status(),
            authserver=auth,
            worldserver=world,
            client=self.client.state(),
            display=display_state,
            wine=self._wine_state(),
            dxvk=self._dxvk_state(),
        )

    def _command_state(self, command: str) -> ComponentState:
        path = shutil.which(command)
        return ComponentState("available" if path else "missing", {"command": command, "path": path})

    def _wine_state(self) -> ComponentState:
        candidates = [
            self.locator.root / "runtime" / "wine-11.18-staging-amd64-wow64" / "bin" / "wine",
            self.locator.root / "runtime" / "wine" / "bin" / "wine",
        ]
        path = next((p for p in candidates if p.is_file()), None)
        if path is not None:
            return ComponentState("available", {"source": "workbench", "path": str(path)})
        fallback = shutil.which("wine")
        return ComponentState(
            "available" if fallback else "missing",
            {"source": "host" if fallback else "none", "path": fallback},
        )

    def _dxvk_state(self) -> ComponentState:
        candidates = [
            self.locator.root / "runtime" / "dxvk-3.1.1",
            self.locator.root / "runtime" / "dxvk",
            self.locator.root / "dxvk",
        ]
        path = next((p for p in candidates if p.exists()), None)
        return ComponentState("available" if path else "unknown", {"source": "workbench" if path else "none", "path": str(path) if path else None})

    def _display_state(self) -> ComponentState:
        # M1 deliberately reports observable configuration only; X11 authentication probing is an M3 gate.
        return ComponentState("configured", {"display": self.display, "environment_display": os.environ.get("DISPLAY")})
