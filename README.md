# Chromie#

Chromie# is a local-first desktop launcher and lifecycle manager for a ChromieCraft / TrinityCore 3.3.5a private-server Workbench.

```text
C# Avalonia Launcher -> Chromie# Protocol -> Python Control Plane -> TrinityCore / MariaDB / Wine -> ChromieCraft
```

Chromie# wraps the existing emulator/runtime boundary instead of forking TrinityCore internals.

## Current milestone

M2 introduces the Battle.net-style launcher shell and PLAY/REPAIR lifecycle contract:

- loopback-only Python API by default
- `/api/v1/launcher/status`
- `/api/v1/launcher/play`
- `/api/v1/launcher/repair`
- ordered realm-start -> client-launch pipeline
- cross-platform .NET 10 / Avalonia desktop launcher
- Workbench, database, authserver, worldserver, client, runtime and display status cards
- non-destructive repair planning
- dependency-light console client retained as a diagnostic fallback

Strict Wine/DXVK, authenticated X11, realmlist and build-12340 launch gates are M3 and are not silently treated as passed.

## Run backend

```bash
./scripts/chromie-backend
```

Defaults:

```text
API:       http://127.0.0.1:5290/api/v1/
Workbench: /mnt/data/workspace/wow-private-server
Display:   :88
```

## Run desktop launcher

```bash
dotnet run --project src/ChromieSharp.Launcher/ChromieSharp.Launcher.csproj
```

Set `CHROMIE_API_URL` to override the API base URL.

## Diagnostic console

```bash
dotnet run --project src/ChromieSharp.Console/ChromieSharp.Console.csproj -- status
```

## Safety defaults

- management API binds to loopback by default
- C# never executes TrinityCore shell commands directly
- repair planning is non-destructive in M2
- missing runtime components are reported, not recreated implicitly
- live launch gates are never marked passed from mocks
