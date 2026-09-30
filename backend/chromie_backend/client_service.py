from __future__ import annotations

import os
from pathlib import Path
import subprocess

from .models import ComponentState, OperationResult
from .workbench import WorkbenchLocator


class ClientService:
    def __init__(self, locator: WorkbenchLocator, display: str) -> None:
        self.locator = locator
        self.display = display
        self._process: subprocess.Popen[str] | None = None

    def preflight(self) -> OperationResult:
        missing: list[str] = []
        if not self.locator.root.is_dir():
            missing.append(str(self.locator.root))
        if not self.locator.client_script.is_file():
            missing.append(str(self.locator.client_script))
        wow = self.locator.wow_exe
        if wow is None:
            missing.append("Wow.exe")
        if missing:
            return OperationResult(False, "CLIENT_PREFLIGHT_FAILED", "ChromieCraft client preflight failed", {"missing": missing})
        return OperationResult(
            True,
            "OK",
            "ChromieCraft client preflight passed",
            {"client_script": str(self.locator.client_script), "wow_exe": str(wow), "display": self.display},
        )

    def state(self) -> ComponentState:
        if self._process is not None:
            rc = self._process.poll()
            if rc is None:
                return ComponentState("running", {"pid": self._process.pid})
            return ComponentState("exited", {"pid": self._process.pid, "returncode": rc})
        check = self.preflight()
        return ComponentState("ready" if check.ok else "missing", check.evidence)

    def launch(self) -> OperationResult:
        check = self.preflight()
        if not check.ok:
            return check
        if self._process is not None and self._process.poll() is None:
            return OperationResult(True, "ALREADY_RUNNING", "ChromieCraft client is already running", {"pid": self._process.pid})
        log_dir = self.locator.root / ".chromie" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "client-launch.log"
        env = os.environ.copy()
        env["DISPLAY"] = self.display
        try:
            stream = log_path.open("a", encoding="utf-8")
            self._process = subprocess.Popen(
                [str(self.locator.client_script), "launch"],
                cwd=str(self.locator.root),
                env=env,
                text=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as exc:
            return OperationResult(False, "CLIENT_LAUNCH_EXEC_ERROR", str(exc), {"path": str(self.locator.client_script)})
        return OperationResult(True, "OK", "ChromieCraft client launch requested", {"pid": self._process.pid, "log": str(log_path)})
