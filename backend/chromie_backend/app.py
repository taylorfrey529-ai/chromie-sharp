from __future__ import annotations

from .api import Services, build_server
from .client_service import ClientService
from .config import Settings
from .database_service import DatabaseService
from .diagnostics_service import DiagnosticsService
from .launcher_service import LauncherService
from .server_service import ServerService
from .status_service import StatusService
from .workbench import WorkbenchLocator


def build_services(settings: Settings) -> Services:
    locator = WorkbenchLocator(settings.workbench_root)
    database = DatabaseService(settings.db_host, settings.db_port)
    server = ServerService(locator)
    client = ClientService(locator, settings.display)
    status = StatusService(locator, database, server, client, settings.display)
    diagnostics = DiagnosticsService(settings.workbench_root)
    launcher = LauncherService(status, server, client)
    return Services(status=status, server=server, client=client, diagnostics=diagnostics, launcher=launcher)


def main() -> int:
    settings = Settings.from_env()
    services = build_services(settings)
    httpd = build_server(settings.api_host, settings.api_port, services)
    print(f"Chromie# backend listening on http://{settings.api_host}:{settings.api_port}/api/v1")
    print(f"Workbench root: {settings.workbench_root}")
    try:
        httpd.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
