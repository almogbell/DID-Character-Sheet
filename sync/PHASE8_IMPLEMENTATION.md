# Phase 8 implementation

This branch contains the first real Windows↔Android companion foundation.

## Added code

### Windows

`windows/mobile_sync_server.py`

A PySide6 `QWebSocketServer` implementation which:

- listens on the LAN (default port 8765)
- creates short-lived one-time pairing tokens
- exchanges pairing tokens for persistent per-device credentials
- stores paired devices in the desktop app-data folder
- supports device revocation
- authenticates reconnects
- keeps a monotonic state revision
- rejects stale commands
- broadcasts canonical desktop character state
- provides hooks for desktop-originated character changes

The server intentionally does **not** implement DID rules. The finished desktop app must supply:

```python
MobileSyncServer(
    desktop_version=APP_VERSION,
    state_provider=...,   # return canonical current-character dict or None
    command_handler=...,  # run existing desktop validation/mutation/save path
)
```

`command_handler` is where HP/AT/IP commands must be routed through the existing finished application. Do not directly mutate values in `mobile_sync_server.py`.

### Android

`android/phase8/DidSyncClient.kt`

The Android companion client:

- pairs from a QR JSON payload
- stores the permanent device token in private SharedPreferences
- reconnects to the saved PC
- receives canonical `state` snapshots
- tracks server revisions
- rejects the assumption that a local edit is final until Windows broadcasts state
- supports `resource.change` commands for the first Phase 8 slice

It uses OkHttp WebSockets. The Android Gradle module needs:

```kotlin
implementation("com.squareup.okhttp3:okhttp:4.12.0")
```

`android/phase8/GitHubUpdateChecker.kt`

Reads:

`https://raw.githubusercontent.com/almogbell/DID-Character-Sheet/main/updates/android.json`

and reports whether a newer Android version exists.

## Still required before this is considered working

The latest finished Windows source must be wired to the callback interface above. In particular we must locate the exact current methods which:

1. serialize the active character,
2. change HP,
3. change Adversity Tokens,
4. change Improvement Points,
5. perform the normal save/autosave,
6. refresh the desktop UI,
7. fire when the active character changes.

Those integration points must be taken from the actual finished source rather than guessed from older revisions.

The Android UI also still needs:

- QR scanning screen
- connection-state screen
- pairing/revoke UX
- wiring its existing HP/AT/IP controls to `DidSyncClient`
- update-available dialog and APK install flow

## Important behavior

The phone does not own `.didchar` files. When disconnected it may display cached state, but it is read-only. Windows remains authoritative at all times.
