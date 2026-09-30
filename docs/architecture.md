# Chromie# architecture

## Product boundary

Chromie# is a launcher/control plane, not a TrinityCore fork and not a replacement game client.

```text
Chromie# Launcher (C# / Avalonia)
             |
             | JSON / HTTP on loopback
             v
chromie_backend (Python control plane)
  |-- LauncherService
  |-- WorkbenchLocator
  |-- DatabaseService
  |-- ServerService ------> server.sh ------> authserver / worldserver
  |-- ClientService ------> client.sh ------> Wine / Wow.exe
  `-- DiagnosticsService
```

The C# layer never shells directly into TrinityCore. Python owns process execution, probing, lifecycle policy, repair planning, and future audit enforcement.

## Launcher state model

Chromie# exposes `/api/v1/launcher/status` with an ordered set of gates. Gates have a stable key, human label, status, blocking flag, message, and evidence.

M2 blocking gates are:

1. Workbench mounted.
2. MariaDB reachable.
3. ChromieCraft client preflight passes.

Auth/world server state is non-blocking before PLAY because PLAY is responsible for starting them. Wine/DXVK and authenticated X11 are visible but non-blocking until M3 installs strict validators.

If every blocking gate passes, launcher mode is `PLAY`. Otherwise mode is `REPAIR` and the API returns `repair_reasons`.

## PLAY pipeline

1. Re-evaluate launcher gates.
2. Refuse launch if any blocking gate fails.
3. Inspect authserver/worldserver state.
4. Start the private realm when it is not already running.
5. Launch the client through `client.sh launch`.
6. Return structured step evidence.
7. M3 will add strict build/runtime/display/realmlist validation before step 5.

## REPAIR contract

M2 repair is deliberately diagnostic and non-destructive. `/api/v1/launcher/repair` returns an explicit action plan such as Workbench recall, database start, or client verification. Automatic mutation/restore is deferred to M5 and remains owner-controlled.

## Evidence rule

A successful button press, HTTP 200, or fake Workbench test is not proof of a live TrinityCore/ChromieCraft launch. Live gates require current-runtime evidence from the actual Workbench.


## M3 strict validation

Before PLAY is enabled, Chromie# now requires current evidence for the persisted ChromieCraft build identity, the Workbench-native client/Wine preflight, and authenticated X11 access. X11 validation uses the Workbench authority file without reading or logging cookie bytes: an authorized `xdpyinfo` probe must pass, an explicitly empty authority probe must fail, and a second authorized probe must still pass.

Realmlist state is visible but can be prepared by the launch pipeline. PLAY verifies the Wine 32-bit bootstrap, configures the realmlist only when needed, starts the realm, waits for loopback auth/world listeners at 3724 and 8085, then invokes `client.sh launch`.

A fake runtime can validate control-flow and security invariants in CI, but it never marks the genuine current-runtime launch gate passed.


## M3.1 readiness sequencing

A stopped database is a normal pre-launch state, not a repair condition. Launcher status therefore reports MariaDB as non-blocking standby when it is not reachable; `server.sh start` owns starting the database and both TrinityCore daemons.

Before PLAY is enabled, Chromie# now requires `server.sh preflight` to pass. That preflight proves the prepared database state, TrinityCore configs, and canonical `dbc/maps/vmaps/mmaps` data are present. DXVK is also a separate blocking gate through `client.sh dxvk-check`.

This prevents a lifecycle deadlock where PLAY required MariaDB to be running even though PLAY itself is responsible for starting it.
