# Chromie# roadmap

## M0 — Architecture

- [x] repository layout
- [x] loopback protocol boundary
- [x] versioned JSON envelope
- [x] shared status semantics
- [x] C# operator client shell

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

## M2 — C# Console / operator frontend

- [x] dependency-light command client
- [ ] structured dashboard
- [ ] live event stream
- [ ] responsive long-running operation UX

## M3 — Client

- [ ] build 12340 verification
- [ ] authenticated X11 display probe
- [ ] Wine/DXVK runtime validation
- [ ] realmlist validation
- [ ] genuine current-runtime launch gate

Later milestones: administration, persistence/recall, Workbench UI, hardening/audit/recovery.
