# DID Character Sheet — Android Companion

The Android app is a portrait-first mobile companion to the Windows DID Character Sheet. Windows remains authoritative for character rules, saved character data, validation and persistence.

## Current project

`android/` is now a complete Gradle Android application rather than a loose source sketch. The app module compiles the Phase 8 sources in `android/phase8/`, while `MainActivity.kt` wires together pairing, reconnect, the synchronized character sheet and GitHub update checking.

GitHub Actions builds a debug APK for every Phase 8 change. The CI build uses Gradle 8.11.1 directly, so the repository does not depend on a committed Gradle-wrapper JAR.

## Releases

Android releases use tags such as `android-v0.8.0` and the Android updater reads `updates/android.json`. Android and Windows have independent version numbers and release schedules.

`.github/workflows/android-release.yml` validates compatibility, builds a signed release APK, creates the GitHub Release, uploads `DID_Character_Sheet_Android_<version>.apk`, and then updates `updates/android.json` on `main` with the final download/release URLs.

The release workflow deliberately refuses to publish Android while `updates/windows.json` advertises a Windows version older than Android's `minimum_desktop_version`.

## Synchronization

Normal use does not copy `.didchar` files to the phone. Android pairs with a running Windows DID application, stores a per-device credential in private application storage, reconnects automatically, and consumes canonical Windows snapshots.

For Phase 8, pairing is restricted to private/link-local IPv4 LAN addresses and expiring pairing codes. When disconnected, the last snapshot may remain visible but all character mutation controls are read-only. Mutations are never queued for later replay.

The Phase 8 files are split by responsibility:

- `DidSyncClient.kt` — pairing, authenticated WebSocket reconnect, revisions, LAN/expiry validation and commands.
- `DidCompanionViewModel.kt` — UI state, reconnect policy, minimum Windows version enforcement and resource commands.
- `DidCharacterSnapshot.kt` — typed read-only view of the canonical Windows character JSON.
- `DidCompanionSheet.kt` — Character / Equipment / Notes phone navigation backed by synchronized state.
- `Phase8CompanionRoot.kt` — connection-vs-character root surface.
- `Phase8ActivityBridge.kt` — Activity bridge for pairing and update actions.
- `PairingScanner.kt` — QR pairing via Google Code Scanner; manual paste remains available.
- `GitHubUpdateChecker.kt`, `AndroidUpdateController.kt`, `UpdateNotice.kt` — GitHub update flow.

The first writable synchronized slice is HP, Adversity Tokens and Improvement Points. Improvements, inventory and notes are already transported/displayed from the canonical Windows snapshot but remain read-only until their command contracts are added.

## Compatibility

`updates/android.json` records Android version, minimum compatible Windows version, sync protocol version, published APK/release URLs and release notes.

Android `0.8.0` is staged against the first sync-enabled Windows release, `1.0.11`, with Sync Protocol v1. Windows `1.0.10` correctly advertises protocol `0` because it predates mobile sync.

The Android code constants, manifests, Windows compatibility table, protocol docs and test vectors are cross-checked by GitHub Actions so they cannot silently drift apart.

## Signing

A debug APK requires no private signing configuration. Publishing an update through the Android release workflow requires the four repository secrets documented in `phase8/Phase8Dependencies.md`. The release keystore must remain stable across Android releases and must never be committed to the repository.
