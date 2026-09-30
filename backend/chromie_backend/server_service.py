from __future__ import annotations

import subprocess

from .models import ComponentState, OperationResult
from .process import run_checked
from .workbench import WorkbenchLocator


class ServerService:
    def __init__(self, locator: WorkbenchLocator) -> None:
        self.locator = locator

    def status(self) -> tuple[ComponentState, ComponentState]:
        script = self.locator.server_script
        if not script.is_file():
            missing = ComponentState("missing", {"path": str(script)})
            return missing, missing
        try:
            result = run_checked([script, "status"], cwd=self.locator.root, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            unknown = ComponentState("unknown", {"error": type(exc).__name__, "detail": str(exc)})
            return unknown, unknown
        evidence = result.evidence()
        text = (result.stdout + "\n" + result.stderr).lower()
        if result.returncode == 0:
            # The wrapper may report both daemons or a single aggregate state.
            auth_state = "running" if "auth" in text or "running" in text else "ready"
            world_state = "running" if "world" in text or "running" in text else "ready"
        else:
            auth_state = world_state = "stopped"
        return ComponentState(auth_state, evidence), ComponentState(world_state, evidence)

    def action(self, action: str) -> OperationResult:
        if action not in {"start", "stop", "restart"}:
            return OperationResult(False, "INVALID_ACTION", f"Unsupported server action: {action}")
        script = self.locator.server_script
        if not script.is_file():
            return OperationResult(False, "SERVER_SCRIPT_MISSING", "server.sh is not available", {"path": str(script)})
        try:
            result = run_checked([script, action], cwd=self.locator.root, timeout=30)
        except subprocess.TimeoutExpired as exc:
            return OperationResult(False, "SERVER_ACTION_TIMEOUT", f"server.sh {action} timed out", {"timeout": exc.timeout})
        except OSError as exc:
            return OperationResult(False, "SERVER_ACTION_EXEC_ERROR", str(exc), {"path": str(script)})
        return OperationResult(
            result.returncode == 0,
            "OK" if result.returncode == 0 else "SERVER_ACTION_FAILED",
            f"server {action} completed" if result.returncode == 0 else f"server {action} failed",
            result.evidence(),
        )
