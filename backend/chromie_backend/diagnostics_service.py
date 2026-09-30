from __future__ import annotations

from collections import deque
from pathlib import Path


class DiagnosticsService:
    def __init__(self, root: Path) -> None:
        self.root = root

    def tail(self, lines: int = 100) -> dict[str, list[str]]:
        lines = min(max(lines, 1), 500)
        candidates = [
            self.root / ".chromie" / "logs" / "client-launch.log",
            self.root / "logs" / "worldserver.log",
            self.root / "logs" / "authserver.log",
            self.root / "worldserver.log",
            self.root / "authserver.log",
        ]
        result: dict[str, list[str]] = {}
        for path in candidates:
            if not path.is_file():
                continue
            try:
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    result[str(path)] = list(deque(handle, maxlen=lines))
            except OSError:
                continue
        return result
