# DID Character Sheet 1.0.13 — Issue Tracker (2026-10-21)

Status semantics: **CODED / NOT VERIFIED** means changed in the source and awaiting hands-on regression testing. Only mark **FIXED** after tester confirms expected behavior on installed Windows/Android builds. **OPEN / BLOCKED** means not implemented or still dependent on missing inputs.

| ID | Feature/Issue | Status | Required acceptance check |
|---|---|---|---|
| 001 | Android pull-to-refresh spinner overlays sheet without moving it | OPEN / BLOCKED — current V8 Android project not in upload | Pull on character view; spinner overlays top; sheet does not translate; one canonical `get_state`; error finishes; no overlapping requests |
| 002 | Android sluggishness and live sync stability | PARTIAL CODED / NOT VERIFIED — desktop fallback poll throttled and skipped while no live clients; Android lifecycle unavailable | Leave Android connected 15–30 minutes; change AT; inspect CPU/reconnect logs; verify no repeated full snapshots |
| 003 | Smart QR normal-camera opening, install fallback, deep-link handling | STAGED / BLOCKED — HTTPS landing page and opt-in Windows link QR coded; Android V8 deep-link handler and hosting deployment absent | Android installed: camera opens app and pairs. Uninstalled: install page shown; approve APK; freshly rescan; no permanent credentials in URL |
| 004 | Companion dialog clipped / overlapping QR / dark placeholder | CODED / NOT VERIFIED | Check Windows 100%, 125%, 150%, 200% scaling, small window and dark/light themes; footer always visible |
| 005 | Connected / Connecting / Disconnected / Paired but offline status | CODED / NOT VERIFIED (Windows); Android OPEN | Unpaired; pairing; authenticated; disconnect/reconnect; status matches real socket |
| 006 | Duplicate paired phone entries | PARTIAL CODED / NOT VERIFIED — display dedup by device_id, live sessions for same device id evicted; distinct Android IDs still need investigation | Pair same physical phone repeatedly and confirm one entry/connection, including Android device-ID persistence |
| 007 | Rename / remove phone with correct confirmation | CODED / NOT VERIFIED | Rename, restart and reconnect; name persists; remove Cancel on left, Remove Phone on right; confirm revokes live token |
| 008 | Phone-connected indicator beside redesigned Saved field | CODED / NOT VERIFIED | Connect Aurora phone; badge shows by Saved without sheet moving; disconnect and reconnect; live AT sync maintained |
| 009 | Android connecting/disconnected flapping + Done/Return navigation | OPEN / BLOCKED — V8 Android sources not provided | Successful pairing shows Connected/Done; return without device Back; recover from brief network drop |
| 010 | Android debug build creates DID Phase 9 T… duplicate launcher | OPEN / BLOCKED — no Android Gradle/build manifests present | Verify current application IDs/variant and release-signing SHA; update Pocket DID without uninstall/data loss |
| 011 | Main sheet horizontal/vertical movement | PARTIAL CODED / NOT VERIFIED — status cell reserved; outer/inventory/improvement scroll gutters reserved | Expand item, switch views/Notes, resize window/scaling; no horizontal/vertical jump |
| 012 | Inventory text wraps/description/collapse | PARTIAL CODED / NOT VERIFIED — existing title layout preserved and geometry minimum aligned to quantity | Extra-long title avoids delete; description fully visible; collapse restores compact row |
| 013 | Inventory quantity pill stretches with card | CODED / NOT VERIFIED — 34×54 fixed and centered | Compare collapsed/expanded 1-line/multiline items; control size constant, centered |
| 014 | Integrated Campaign Manager player/DM guide | CODED / NOT VERIFIED | Open Campaigns > How to Use / Help > Players/DMs; scroll guide, return to same tab; try dark mode and inline rules editor |
| 015 | Windows/Android release packaging and QR deployment | OPEN / BLOCKED — requires Android project, live GitHub Pages/custom host, signed APK | Verify current release signing and hosting; publish new release only after device tests |

## Protocol and data preservation
- No character, save-file, credentials, campaign content, inventory, or user files were modified by this patch.
- No protocol version, `pair`/`hello`/`get_state` field names, permanent token storage paths, or command validation were changed.
- Tested 1.0.13 server against a Qt-transport stub for old JSON pairing, authenticated reconnect, live AT state push, manual `get_state`, duplicate-session eviction, custom phone names, and invalid token rejection.
- **Still required:** test against the real current Android V8 client and Windows PySide6 build; test bundled PyInstaller executable.

## Tester findings (append; do not overwrite)
| Date | Issue | Repro, expected vs observed | Build, machine, log/screenshot | Result |
|---|---|---|---|---|
| 2026-10-21 | Initial 1.0.13 implementation | Source coded; not yet device-tested | Windows sources only | Awaiting verification |
