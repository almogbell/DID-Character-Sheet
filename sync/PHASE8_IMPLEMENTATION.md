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
- recognizes the finished 1.0.10 Tools menu without depending on a permanent `Check for Updates` row
- injects `Mobile Companion` before the Dice Roller submenu
- shuts down with `QApplication.aboutToQuit`, so the existing frontend `closeEvent` does not need network-specific code

`windows/mobile_companion_dialog.py`

- starts explicit pairing
- renders/copies pairing JSON and QR code
- lists paired phones
- revokes a paired phone
- shows connected-device count/status

`windows/mobile_companion_requirements.txt`

- adds the QR-code packaging dependency

`windows/integrate_mobile_companion.py`

- idempotently patches the confirmed finished `BaseMainWindow` startup anchor
- updates the sync-enabled desktop version to `1.0.11` by default
- installs `MobileCompanionController` immediately after the normal initial refresh/undo bootstrap
- creates one backup before changing a local frontend file
- refuses to guess when the expected finished-frontend anchor is missing

### Finished Windows frontend inspection

The indexed finished frontend `frontend_2_8(20261009-160308).py` has now been inspected directly. It is Windows DID `1.0.10` and confirms the exact Phase 8 integration assumptions:

- `BaseMainWindow.__init__` owns the active `character`
- startup ends with `setup_keyboard_shortcuts()`, `refresh_all()`, and `reset_undo_history(treat_current_as_clean=True)`
- `refresh_all()` is the canonical full-sheet refresh path
- `mark_dirty(auto_save=True)` routes into the existing autosave/save path
- the finished Tools menu contains New/Save/Load/Delete/Earlier Versions/Edit Abilities plus the Dice Roller submenu
- the ordinary `Check for Updates` action is intentionally absent unless an update is actually available

Because of this inspection, the frontend code integration no longer depends on guessing an insertion point. The integration patcher is anchored to the finished startup sequence and tested for idempotence.

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

The Phase 8 branch contains a complete Gradle Android application under `android/`, not only loose Kotlin source files:

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

Android `0.8.0` targets the first sync-enabled Windows release, planned as `1.0.11`, using Sync Protocol v1. Android release URLs intentionally remain `null` until a signed APK is actually published. The currently published Windows `1.0.10` correctly advertises protocol `0` because it predates mobile sync.

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
2. Windows PySide6 sync/controller/adapter/integration-patcher unit tests on `windows-latest`.
3. Real Android Gradle debug compilation on `ubuntu-latest`, with the APK uploaded as an Actions artifact when successful.

Windows tests cover pairing/authentication, invalid/revoked credentials, malformed/oversized input, serializer failure handling, stale revisions, accepted/rejected commands, HP/AT/IP adapter behavior, read-only character rejection, automatic server startup, desktop-originated change detection, active-character switching, prevention of double-counting mobile-originated changes, finished Tools-menu detection and safe/idempotent frontend integration.

## Remaining integration boundary

The transport, Android project, update/release workflows and finished-frontend integration contract are implemented on this branch. Remaining work that can be automated before device testing is primarily packaging/release validation against the full local Windows build tree.

For the sync-enabled Windows build the required source-tree changes are now intentionally small:

- place the Phase 8 Windows modules beside the finished frontend/backend
- run `windows/integrate_mobile_companion.py frontend_2_8.py --version 1.0.11`
- install/include `windows/mobile_companion_requirements.txt`
- keep the existing frontend Tools-menu and close lifecycle code unchanged; the controller handles both integration points externally
- ensure the existing PyInstaller/installer inputs collect the newly imported modules and `qrcode` dependency
- run the existing DID release tests plus the Phase 8 tests against the integrated source tree
- publish Windows `1.0.11` before publishing Android `0.8.0`, because Android declares `1.0.11` as its minimum compatible desktop release

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
