# Chromie#

Chromie# is a local-first control plane for a ChromieCraft / TrinityCore 3.3.5a private-server workbench.

The design deliberately wraps the existing emulator/runtime instead of forking TrinityCore internals:

`C# operator frontend -> Chromie# protocol -> Python control plane -> TrinityCore / MariaDB / Wine -> ChromieCraft`

## Current milestone

This repository implements the M0 architecture and the first M1 headless vertical slice:

- loopback-only Python API (`127.0.0.1` by default)
- versioned `/api/v1` protocol
- Workbench discovery without assuming an ephemeral mount exists
- database reachability probe without exposing credentials
- `server.sh` status/start/stop/restart adapter
- ChromieCraft client preflight and guarded launch adapter
- structured request IDs and machine-readable errors
- dependency-light .NET 10 operator console
- Python contract tests using a fake Workbench
- CI for Python tests and .NET 10 compilation

Live TrinityCore/client gates are not considered passed unless the real Workbench is mounted and probed in the current runtime.

## Run the backend

```bash
./scripts/chromie-backend
```

Environment overrides:

```bash
CHROMIE_WORKBENCH_ROOT=/mnt/data/workspace/wow-private-server \
CHROMIE_API_HOST=127.0.0.1 \
CHROMIE_API_PORT=5290 \
./scripts/chromie-backend
```

## Use the C# operator console

```bash
dotnet run --project src/ChromieSharp.Console/ChromieSharp.Console.csproj -- status
```

Commands: `health`, `status`, `start`, `stop`, `restart`, `preflight`, `launch`, `logs`.

## Security defaults

- management API binds to loopback only by default
- database credentials are not required for the M1 reachability probe and are never logged
- frontend never shells directly into TrinityCore
- mutation commands are executed only by the Python control plane
- missing runtime components are reported as missing rather than reconstructed implicitly
