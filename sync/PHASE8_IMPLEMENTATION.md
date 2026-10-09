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
- 64 KiB inbound command/pairing message limit
- bounded identity/request fields
- malformed-protocol handling without escaping the network callback
- `STATE_UNAVAILABLE` response when canonical serialization temporarily fails

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
- identifies the existing DID Tools menu and injects `Mobile Companion` before `Check for Updates`

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
- private/link-local IPv4 enforcement for Phase 8 LAN connections
- pairing-code expiry enforcement

`android/phase8/DidCompanionViewModel.kt`

- reconnects automatically with bounded retry delays
- exposes connection state and canonical character state
- parses typed `DidCharacterSnapshot`
- disables mutations while disconnected or incompatible
- enforces the minimum Windows version
- re-fetches canonical state after rejected commands
- retains the last renderable snapshot but makes it read-only if a newer canonical payload cannot be parsed

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
- manual pasted-code fallback remains available

### Buildable Android application

The Phase 8 branch now contains a complete Gradle Android application under `android/`, not only loose Kotlin source files:

- `android/settings.gradle.kts`
- `android/build.gradle.kts`
- `android/gradle.properties`
- `android/app/build.gradle.kts`
- `android/app/src/main/AndroidManifest.xml`
- `android/app/src/main/java/com/did/charactersheet/MainActivity.kt`

`MainActivity` wires the companion ViewModel, QR/update bridge, update notice and synchronized companion root. The app is portrait-first and contains no normal `.didchar` ownership/import flow.

GitHub Actions runs a real Gradle `:app:assembleDebug` build and uploads the resulting debug APK as a workflow artifact when compilation succeeds.

### GitHub Android update flow

`android/phase8/GitHubUpdateChecker.kt`

- reads `updates/android.json` from the repository
- validates the Android manifest before trusting it
- compares app versions
- exposes release notes, required desktop version, sync protocol and download/release URLs

`android/phase8/AndroidUpdateController.kt`

- update-check state machine
- opens the published update through Android's normal install/download consent flow
- refuses non-HTTPS or non-GitHub update links
- does not attempt silent installation

`android/phase8/UpdateNotice.kt`

- Compose update-available / retry UI

`.github/workflows/android-release.yml`

- validates the Android/Windows compatibility state
- reconstructs the release keystore from GitHub repository secrets
- builds a signed release APK
- creates the `android-vX.Y.Z` GitHub Release
- uploads the APK
- finalizes `updates/android.json` on `main` with the published URLs

The keystore itself is never committed. Android's signing identity must remain stable across future releases.

### GitHub update/compatibility manifests

- `updates/windows.json`
- `updates/android.json`

Android `0.8.0` currently targets the first sync-enabled Windows release, planned as `1.0.11`, using Sync Protocol v1. Android release URLs intentionally remain `null` until a signed APK is actually published. The currently published Windows `1.0.10` correctly advertises protocol `0` because it predates mobile sync.

Validation cross-checks:

- platform/version/tag consistency
- Windows/Android protocol compatibility
- Android code version vs manifest
- Android Gradle `versionName` vs manifest
- Android minimum-desktop constant vs manifest
- release URL consistency
- protocol docs/test vectors/code constants
- buildable Android project/source invariants

### Automated validation

`.github/workflows/phase8-validation.yml` performs three classes of checks:

1. Python syntax + manifest/protocol/source-contract validation.
2. Windows PySide6 sync/controller/adapter unit tests on `windows-latest`.
3. Real Android Gradle debug compilation on `ubuntu-latest`, with the APK uploaded as an Actions artifact when successful.

Windows tests cover pairing/authentication, invalid/revoked credentials, malformed/oversized input, serializer failure handling, stale revisions, accepted/rejected commands, HP/AT/IP adapter behavior, read-only character rejection, automatic server startup, desktop-originated change detection, active-character switching and prevention of double-counting mobile-originated changes.

## Remaining integration boundary

The Android Gradle project and Phase 8 Android application are now integrated on this branch. The remaining code integration boundary is the **latest finished Windows desktop source tree**.

The latest Windows source ZIP is already present in the conversation and has been materialized, so it does not need to be uploaded again. The current execution runtime, however, is failing to open/extract that ZIP programmatically. Because the finished desktop app changed after the individually indexed source revisions, the final bootstrap into `frontend_2_8.py`, packaging/spec update and installer build should not be guessed against an older revision.

Once the latest archive can be programmatically inspected, the remaining desktop work is intentionally small:

- place the Phase 8 Windows modules beside the finished frontend/backend
- instantiate `install_mobile_companion(window, CharacterStorageSystem, APP_VERSION)` at the correct main-window bootstrap point
- ensure shutdown occurs with the window lifecycle
- include QR/runtime modules in the PyInstaller/installer packaging
- set the first sync-enabled Windows release/version metadata consistently
- run the existing DID release tests plus the Phase 8 tests against the real finished source

## First end-to-end acceptance test

When the integrated Windows build is ready, the first real-device test should verify this exact sequence:

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

No `.didchar` copy/import step is part of the Phase 8 acceptance flow. Actual phone testing is still required; CI compilation is not a substitute for device acceptance testing.
