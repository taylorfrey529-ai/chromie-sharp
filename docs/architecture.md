# Chromie# architecture

## Boundary

Chromie# is a control plane, not a TrinityCore fork.

- **C#** owns operator interaction.
- **Python** owns orchestration, process execution, probing, policy, and future audit enforcement.
- **TrinityCore / MariaDB / Wine / ChromieCraft** remain authoritative runtime components.

The C# layer never invokes shell commands directly. It communicates with the loopback Python API.

## M0/M1 component map

```text
ChromieSharp.Console (.NET 10)
        |
        | JSON / HTTP on loopback
        v
chromie_backend (Python stdlib)
  |-- WorkbenchLocator
  |-- DatabaseService
  |-- ServerService ----> server.sh ----> authserver/worldserver
  |-- ClientService ----> client.sh ----> Wine / Wow.exe
  `-- DiagnosticsService
```

## State semantics

Status is evidence-derived. A component may be `missing`, `unreachable`, `stopped`, `ready`, `running`, `exited`, `available`, `configured`, or `unknown`.

A button press or successful HTTP request is never itself proof that a live process is healthy. The caller should request `/api/v1/status` after mutations.

## Live validation gates

The fake Workbench used by tests proves protocol and lifecycle behavior only. It does not pass the live gates for MariaDB, authserver, worldserver, realm queries, X11 authentication, or the ChromieCraft client. Those gates require current runtime evidence.
