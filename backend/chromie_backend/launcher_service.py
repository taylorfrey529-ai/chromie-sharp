from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .client_service import ClientService
from .models import OperationResult, utc_now
from .server_service import ServerService
from .status_service import StatusService


@dataclass(slots=True)
class LauncherGate:
    key: str
    label: str
    status: str
    blocking: bool
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LauncherService:
    """Battle.net-style lifecycle coordinator for the local ChromieCraft realm."""

    def __init__(self, status: StatusService, server: ServerService, client: ClientService) -> None:
        self.status_service = status
        self.server = server
        self.client = client

    def status(self) -> dict[str, Any]:
        snapshot = self.status_service.snapshot()
        preflight = self.client.preflight()
        gates = [
            LauncherGate(
                "workbench",
                "Workbench",
                "pass" if snapshot.workbench.state == "ready" else "fail",
                True,
                "Workbench mounted" if snapshot.workbench.state == "ready" else "Workbench recovery required",
                snapshot.workbench.evidence,
            ),
            LauncherGate(
                "database",
                "MariaDB",
                "pass" if snapshot.database.state == "reachable" else "fail",
                True,
                "Database reachable" if snapshot.database.state == "reachable" else "Database is not reachable",
                snapshot.database.evidence,
            ),
            LauncherGate(
                "client",
                "ChromieCraft Client",
                "pass" if preflight.ok else "fail",
                True,
                preflight.message,
                preflight.evidence,
            ),
            LauncherGate(
                "authserver",
                "Auth Server",
                "pass" if snapshot.authserver.state == "running" else "standby" if snapshot.authserver.state == "stopped" else "fail",
                False,
                f"Auth server: {snapshot.authserver.state}",
                snapshot.authserver.evidence,
            ),
            LauncherGate(
                "worldserver",
                "World Server",
                "pass" if snapshot.worldserver.state == "running" else "standby" if snapshot.worldserver.state == "stopped" else "fail",
                False,
                f"World server: {snapshot.worldserver.state}",
                snapshot.worldserver.evidence,
            ),
            LauncherGate(
                "runtime",
                "Wine / DXVK",
                "pass" if snapshot.wine.state == "available" else "pending",
                False,
                "Runtime detected" if snapshot.wine.state == "available" else "Strict runtime validation lands in M3",
                {"wine": snapshot.wine.to_dict(), "dxvk": snapshot.dxvk.to_dict()},
            ),
            LauncherGate(
                "display",
                "Display",
                "pending",
                False,
                "Configured; authenticated X11 validation lands in M3",
                snapshot.display.evidence,
            ),
        ]
        failed = [gate for gate in gates if gate.blocking and gate.status != "pass"]
        return {
            "timestamp": utc_now(),
            "mode": "REPAIR" if failed else "PLAY",
            "can_play": not failed,
            "gates": [gate.to_dict() for gate in gates],
            "repair_reasons": [gate.key for gate in failed],
            "runtime": snapshot.to_dict(),
        }

    def play(self) -> OperationResult:
        before = self.status()
        if not before["can_play"]:
            return OperationResult(
                False,
                "LAUNCHER_REPAIR_REQUIRED",
                "Chromie# cannot launch until blocking gates pass",
                {"launcher": before},
            )

        steps: list[dict[str, Any]] = []
        auth, world = self.server.status()
        if auth.state != "running" or world.state != "running":
            started = self.server.action("start")
            steps.append({"step": "server.start", **started.to_dict()})
            if not started.ok:
                return OperationResult(False, "SERVER_START_FAILED", "Chromie# could not start the realm", {"steps": steps})
        else:
            steps.append({"step": "server.start", "ok": True, "code": "ALREADY_RUNNING", "message": "Realm already running", "evidence": {}})

        launched = self.client.launch()
        steps.append({"step": "client.launch", **launched.to_dict()})
        if not launched.ok:
            return OperationResult(False, "CLIENT_LAUNCH_FAILED", "Realm is ready but the client could not launch", {"steps": steps})

        return OperationResult(True, "OK", "Chromie# launch pipeline completed", {"steps": steps, "launcher": self.status()})

    def repair_plan(self) -> OperationResult:
        current = self.status()
        actions: list[dict[str, str]] = []
        for reason in current["repair_reasons"]:
            if reason == "workbench":
                actions.append({"gate": reason, "action": "recall-workbench", "message": "Restore or mount the verified Workbench bundle."})
            elif reason == "database":
                actions.append({"gate": reason, "action": "start-database", "message": "Start the local MariaDB service and re-run health checks."})
            elif reason == "client":
                actions.append({"gate": reason, "action": "verify-client", "message": "Verify client.sh and Wow.exe against the persisted Workbench."})
        if not actions:
            return OperationResult(True, "NO_REPAIR_REQUIRED", "All blocking launcher gates pass", {"launcher": current, "actions": []})
        return OperationResult(True, "REPAIR_PLAN", "Chromie# generated a non-destructive repair plan", {"launcher": current, "actions": actions})
