from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Settings:
    workbench_root: Path
    api_host: str
    api_port: int
    db_host: str
    db_port: int
    display: str

    @classmethod
    def from_env(cls) -> "Settings":
        root = Path(os.environ.get("CHROMIE_WORKBENCH_ROOT", "/mnt/data/workspace/wow-private-server"))
        host = os.environ.get("CHROMIE_API_HOST", "127.0.0.1")
        if host not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("CHROMIE_ALLOW_REMOTE") != "1":
            raise ValueError("Refusing non-loopback CHROMIE_API_HOST without CHROMIE_ALLOW_REMOTE=1")
        return cls(
            workbench_root=root,
            api_host=host,
            api_port=int(os.environ.get("CHROMIE_API_PORT", "5290")),
            db_host=os.environ.get("CHROMIE_DB_HOST", "127.0.0.1"),
            db_port=int(os.environ.get("CHROMIE_DB_PORT", "3306")),
            display=os.environ.get("CHROMIE_DISPLAY", os.environ.get("DISPLAY", ":88")),
        )
