from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import ComponentState


@dataclass(frozen=True, slots=True)
class WorkbenchLocator:
    root: Path

    @property
    def server_script(self) -> Path:
        return self.root / "server.sh"

    @property
    def client_script(self) -> Path:
        return self.root / "client.sh"

    @property
    def wow_candidates(self) -> tuple[Path, ...]:
        return (
            self.root / "client" / "ChromieCraft_3.3.5a" / "Wow.exe",
            self.root / "ChromieCraft_3.3.5a" / "Wow.exe",
            self.root / "client" / "Wow.exe",
        )

    @property
    def wow_exe(self) -> Path | None:
        for path in self.wow_candidates:
            if path.is_file():
                return path
        return None

    def state(self) -> ComponentState:
        if not self.root.is_dir():
            return ComponentState("missing", {"path": str(self.root), "mounted": False})
        return ComponentState(
            "ready",
            {
                "path": str(self.root),
                "mounted": True,
                "server_script": self.server_script.is_file(),
                "client_script": self.client_script.is_file(),
                "wow_exe": str(self.wow_exe) if self.wow_exe else None,
            },
        )
