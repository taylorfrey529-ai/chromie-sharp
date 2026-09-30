# Chromie# roadmap

Chromie# is the private-realm launcher and lifecycle manager for the ChromieCraft / TrinityCore Workbench.

## M0 — Architecture

- [x] repository layout
- [x] loopback protocol boundary
- [x] versioned JSON envelope
- [x] shared status semantics
- [x] C# diagnostic client shell

## M1 — Headless Chromie#

- [x] Workbench discovery
- [x] database reachability probe
- [x] server status/start/stop/restart adapter
- [x] client preflight/launch adapter
- [x] diagnostics/log tail endpoint
- [x] fake-Workbench contract tests
- [ ] live MariaDB gate
- [ ] live authserver gate
- [ ] live worldserver gate

## M2 — Chromie# Launcher Shell

- [x] Battle.net-style product boundary
- [x] cross-platform Avalonia desktop shell
- [x] launcher status endpoint
- [x] PLAY / REPAIR state machine
- [x] ordered server-start -> client-launch pipeline
- [x] non-destructive repair-plan endpoint
- [x] Workbench / database / auth / world / client / runtime cards
- [ ] live event stream
- [ ] background/tray lifecycle
- [ ] packaged desktop artifact

## M3 — Strict Launch Pipeline

- [x] build 12340 verification from persisted runtime manifest
- [x] authenticated X11 positive/negative authorization probe
- [x] Workbench-native Wine/client preflight and 32-bit bootstrap
- [x] DXVK payload validation
- [x] realmlist validation and guarded local configuration
- [x] server runtime/data preflight gate
- [x] stopped MariaDB treated as PLAY-managed standby
- [ ] genuine current-runtime client launch gate
- [ ] launcher minimize/tray transition after confirmed launch

## M4 — Realm Manager

- [ ] account creation and password reset
- [ ] realm access / GM security levels
- [ ] character lookup and online inspection
- [ ] authoritative GM-console operations
- [ ] post-mutation read-only verification

## M5 — Repair & Recall

- [ ] consume the persisted Workbench binary manifest
- [ ] verify numbered volumes and whole logical SHA-256
- [ ] stream restore without duplicate full archives
- [ ] diagnose only the failed component
- [ ] explicit owner-controlled repair execution

## M6 — Game Library

- [ ] realm/runtime profiles
- [ ] AddOn profiles
- [ ] client settings
- [ ] multiple local private-realm configurations

## M7 — Production Launcher

- [ ] crash recovery
- [ ] append-only administrative audit trail
- [ ] self-update channel
- [ ] Native AOT compatibility assessment
- [ ] signed release packaging

## Product contract

Open Chromie#. Click **PLAY**. Chromie# validates the local Workbench, makes the private realm ready, launches World of Warcraft, then continues monitoring the realm and client. When a blocking gate fails, PLAY becomes REPAIR and Chromie# reports the exact failed dependency rather than guessing.
