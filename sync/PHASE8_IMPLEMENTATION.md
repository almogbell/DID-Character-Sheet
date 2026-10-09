# Phase 8 implementation status

Phase 8 changes DID Android from a copied-character-file prototype into a connected mobile companion for the finished Windows application. Windows is authoritative for character rules and saved data; Android displays canonical Windows snapshots and sends allowed commands back to Windows.

## Implemented on the Phase 8 branch

### Windows companion transport

`windows/mobile_sync_server.py`

- PySide6 `QWebSocketServer` on the LAN, default port `8765`
- explicit first-time pairing
- random short-lived one-time pairing token
- permanent per-device credentials after pairing
- private desktop app-data storage for paired devices
- paired-device revocation
- authenticated reconnects
- sync protocol/version handshake
- monotonically increasing state revisions
- stale-command rejection
- canonical state snapshots
- authenticated HP / Adversity / IP command transport

### Windows desktop integration layer

`windows/mobile_sync_frontend_adapter.py`

- uses the desktop `CharacterStorageSystem.character_to_dict()` serializer as the canonical mobile snapshot
- routes HP / Adversity / IP changes into the existing desktop character object
- uses the normal `mark_dirty(auto_save=True)` persistence path
- supports the finished frontend's `refresh_all()` path
- rejects mutations when the desktop character is read-only
- validates resource bounds before accepting phone commands

`windows/mobile_companion_controller.py`

- starts the companion server with the desktop app so previously paired phones can reconnect automatically
- owns the adapter/server/pairing dialog
- polls the canonical serialized desktop state every 500 ms
- broadcasts desktop-originated state changes without adding networking calls to every existing desktop mutation function
- detects active-character replacement separately
- records mobile-originated state signatures before server broadcast so the same mutation is not counted twice

`windows/mobile_companion_dialog.py`

- starts explicit pairing
- renders/copies pairing JSON and QR code
- lists paired phones
- revokes a paired phone
- shows connected-device count/status

`windows/mobile_companion_requirements.txt`

- adds the QR-code packaging dependency

### Android connection layer

`android/phase8/DidSyncClient.kt`

- QR/manual pairing payload parser
- private per-device credential storage
- authenticated reconnect to a saved computer
- canonical state reception
- state revision tracking
- stale/server rejection handling
- HP / Adversity / IP commands
- desktop version exposure for compatibility checks

`android/phase8/DidCompanionViewModel.kt`

- reconnects automatically with bounded retry delays
- exposes connection state and canonical character state
- parses typed `DidCharacterSnapshot`
- disables mutations while disconnected or incompatible
- enforces the minimum Windows version
- re-fetches canonical state after rejected commands

### Android canonical character model and UI

`android/phase8/DidCharacterSnapshot.kt`

Typed read-only view of the Windows snapshot including:

- character identity/backstory
- all six stats/die sizes/bonuses
- HP
- Adversity Tokens
- IP/level
- Improvements and Empowerments
- Improvement/Empowerment choices, including data needed for features such as Animal Buddy
- Inventory
- Notes, color/pin/link metadata
- portrait/image data

`android/phase8/DidCompanionSheet.kt`

- phone navigation: Character / Equipment / Notes
- Character tabs: Abilities / Improvements
- HP / AT / IP controls backed by Windows commands
- synchronized ability list
- synchronized improvement/empowerment list
- synchronized equipment list
- synchronized note list
- disconnected state remains read-only

`android/phase8/Phase8CompanionRoot.kt`

- single root surface choosing connection setup vs synchronized sheet
- connection/read-only banner
- reconnect/refresh path

`android/phase8/PairingScanner.kt`

- Google Code Scanner QR pairing helper
- no custom camera preview required

### GitHub Android update flow

`android/phase8/GitHubUpdateChecker.kt`

- reads `updates/android.json` from the repository
- validates the Android manifest before trusting it
- compares semantic-style app versions
- exposes release notes, required desktop version, sync protocol and download/release URLs

`android/phase8/AndroidUpdateController.kt`

- update-check state machine
- opens the published update through Android's normal install/download consent flow
- refuses non-HTTPS or non-GitHub update links
- does not attempt silent installation

`android/phase8/UpdateNotice.kt`

- Compose update-available / retry UI

### GitHub update/compatibility manifests

- `updates/windows.json`
- `updates/android.json`

Android `0.8.0` currently targets the first sync-enabled Windows release, planned as `1.0.11`, using sync protocol `1`. Android release URLs intentionally remain `null` until a signed APK is actually published.

`sync/validate_manifests.py` validates:

- platform/version/tag consistency
- Windows/Android protocol agreement
- Android code version vs manifest
- Android minimum-desktop constant vs manifest
- release URL consistency
- that a published Android release never requires a Windows version newer than the advertised Windows release

### Automated validation

`.github/workflows/phase8-validation.yml` runs on the Phase 8 branch and relevant pull requests.

Windows tests cover:

- pairing/authentication
- invalid/revoked credentials
- stale revisions
- accepted/rejected commands
- HP / AT / IP adapter behavior
- read-only character rejection
- automatic server startup
- desktop-originated change detection
- active-character switching
- prevention of double-counting mobile-originated changes

## What is intentionally not complete yet

The architecture and isolated Phase 8 modules are implemented, but two full-project integration/build steps still require the actual finished application trees:

1. **Finished Windows frontend integration** — copy the Phase 8 Windows modules beside the current desktop source, instantiate `install_mobile_companion(...)`, add `Mobile Companion` to the existing Tools menu, include QR/WebSocket dependencies in packaging, and build/test the real installer.
2. **Full Android Studio integration** — merge the Phase 8 source into the current Android project, wire the existing Activity to `Phase8CompanionRoot`, QR scanning and update notice/controller, add Gradle/network-security configuration, then compile/install on a real Android device.

The user's latest Windows source ZIP and Phase 7 Android project are available in the conversation. Exact archive integration is pending only because the current execution runtime is not successfully opening/extracting those ZIPs; they do not need to be re-uploaded.

## First end-to-end acceptance test

When the integrated builds are ready, the first device test should verify this exact sequence:

1. Launch sync-enabled Windows DID.
2. Open Tools -> Mobile Companion -> Start pairing.
3. Scan the QR code from Android.
4. Confirm the current Windows character appears on Android.
5. Change HP on Windows and confirm Android changes automatically.
6. Change HP on Android and confirm Windows changes, saves through its normal path, and sends the canonical result back.
7. Repeat for AT and IP.
8. Switch character on Windows and confirm Android switches to the new canonical character.
9. Disconnect Wi-Fi and confirm Android becomes read-only.
10. Restore the network and confirm automatic reconnect plus a fresh canonical snapshot.

No `.didchar` copy/import step is part of the Phase 8 acceptance flow.
