from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .client_service import ClientService
from .models import OperationResult, utc_now
from .server_service import ServerService
from .status_service import StatusService
from .validation_service import LaunchValidationService


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

    def __init__(
        self,
        status: StatusService,
        server: ServerService,
        client: ClientService,
        validator: LaunchValidationService,
    ) -> None:
        self.status_service = status
        self.server = server
        self.client = client
        self.validator = validator

    @staticmethod
    def _gate(key: str, label: str, result: OperationResult, *, blocking: bool, standby_on_fail: bool = False) -> LauncherGate:
        return LauncherGate(
            key,
            label,
            "pass" if result.ok else "standby" if standby_on_fail else "fail",
            blocking,
            result.message,
            result.evidence,
        )

    def status(self) -> dict[str, Any]:
        snapshot = self.status_service.snapshot()
        client = self.client.preflight()
        build = self.validator.build_identity()
        runtime = self.validator.runtime_preflight()
        dxvk = self.validator.dxvk()
        server_ready = self.validator.server_preflight()
        display = self.validator.display_authentication()
        realmlist = self.validator.realmlist()

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
                "pass" if snapshot.database.state == "reachable" else "standby",
                False,
                "Database reachable" if snapshot.database.state == "reachable" else "Database is stopped; PLAY will start it through server.sh",
                snapshot.database.evidence,
            ),
            self._gate("server_data", "Server Runtime / Data", server_ready, blocking=True),
            self._gate("client", "ChromieCraft Client", client, blocking=True),
            self._gate("build", "Build 12340", build, blocking=True),
            self._gate("runtime", "Wine Runtime", runtime, blocking=True),
            self._gate("dxvk", "DXVK", dxvk, blocking=True),
            self._gate("display", "Authenticated Display", display, blocking=True),
            self._gate("realmlist", "Local Realm", realmlist, blocking=False, standby_on_fail=True),
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
                "Chromie# cannot launch until strict blocking gates pass",
                {"launcher": before},
            )

        steps: list[dict[str, Any]] = []

        realmlist_gate = next((gate for gate in before["gates"] if gate["key"] == "realmlist"), None)
        if realmlist_gate and realmlist_gate["status"] != "pass":
            configured = self.validator.configure_realmlist()
            steps.append({"step": "client.configure-realmlist", **configured.to_dict()})
            if not configured.ok:
                return OperationResult(False, "REALMLIST_CONFIGURE_FAILED", "Chromie# could not configure the local realm", {"steps": steps})

        wine = self.validator.wine_bootstrap()
        steps.append({"step": "client.wine-check", **wine.to_dict()})
        if not wine.ok:
            return OperationResult(False, "WINE_BOOTSTRAP_FAILED", "Chromie# could not validate the Wine process bootstrap", {"steps": steps})

        auth, world = self.server.status()
        if auth.state != "running" or world.state != "running":
            started = self.server.action("start")
            steps.append({"step": "server.start", **started.to_dict()})
            if not started.ok:
                return OperationResult(False, "SERVER_START_FAILED", "Chromie# could not start the realm", {"steps": steps})
        else:
            steps.append(
                {
                    "step": "server.start",
                    "ok": True,
                    "code": "ALREADY_RUNNING",
                    "message": "Realm already running",
                    "evidence": {},
                }
            )

        ports = self.validator.server_ports()
        steps.append({"step": "server.listeners", **ports.to_dict()})
        if not ports.ok:
            return OperationResult(False, "SERVER_PORTS_NOT_READY", "Realm processes started but listeners are not ready", {"steps": steps})

        launched = self.client.launch()
        steps.append({"step": "client.launch", **launched.to_dict()})
        if not launched.ok:
            return OperationResult(False, "CLIENT_LAUNCH_FAILED", "Realm is ready but the client could not launch", {"steps": steps})

        return OperationResult(
            True,
            "OK",
            "Chromie# strict launch pipeline completed",
            {"steps": steps, "launcher": self.status()},
        )

    def repair_plan(self) -> OperationResult:
        current = self.status()
        actions: list[dict[str, str]] = []
        action_map = {
            "workbench": ("recall-workbench", "Restore or mount the verified Workbench bundle."),
            "server_data": ("prepare-server-data", "Complete and validate dbc/maps/vmaps/mmaps plus the prepared database/runtime state."),
            "client": ("verify-client", "Verify client.sh and Wow.exe against the persisted Workbench."),
            "build": ("verify-build-manifest", "Restore or verify the persisted build-12340 runtime manifest."),
            "runtime": ("repair-runtime", "Repair the Workbench Wine runtime before launch."),
            "dxvk": ("repair-dxvk", "Restore or verify the Workbench DXVK payload before launch."),
            "display": ("repair-display-auth", "Restore the authenticated X11 display without weakening access control."),
        }
        for reason in current["repair_reasons"]:
            action, message = action_map.get(reason, ("inspect", "Inspect the failed launcher gate."))
            actions.append({"gate": reason, "action": action, "message": message})

        realmlist = next((gate for gate in current["gates"] if gate["key"] == "realmlist"), None)
        if realmlist and realmlist["status"] != "pass":
            actions.append(
                {
                    "gate": "realmlist",
                    "action": "configure-realmlist",
                    "message": "Set the detected locale realmlist.wtf to the local 127.0.0.1 realm.",
                }
            )

        if not actions:
            return OperationResult(
                True,
                "NO_REPAIR_REQUIRED",
                "All strict launcher gates pass",
                {"launcher": current, "actions": []},
            )
        return OperationResult(
            True,
            "REPAIR_PLAN",
            "Chromie# generated a non-destructive strict repair plan",
            {"launcher": current, "actions": actions},
        )
