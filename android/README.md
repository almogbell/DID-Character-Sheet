# DID Character Sheet — Android Companion

The Android app is a mobile companion to the Windows DID Character Sheet.

It is designed to feel like the desktop character sheet adapted for a phone, while keeping the Windows application authoritative for character rules and saved character data.

## Releases

Android releases use tags such as `android-v0.8.0` and the Android updater reads `updates/android.json`.

Android and Windows use independent version numbers and may be released separately.

After the full Android Studio project is merged under `android/` and the signing secrets are configured, `.github/workflows/android-release.yml` automates the release path: it validates compatibility, builds a signed release APK, creates the GitHub Release, uploads `DID_Character_Sheet_Android_<version>.apk`, and then updates `updates/android.json` on `main` with the final download/release URLs.

The workflow deliberately refuses to publish Android while `updates/windows.json` still advertises a Windows version older than Android's `minimum_desktop_version`.

## Synchronization

Normal use does not copy `.didchar` files to the phone. Android pairs with a running Windows DID application, stores a per-device credential in private application storage, reconnects automatically, and consumes canonical Windows snapshots.

For Phase 8, pairing is restricted to private/link-local IPv4 LAN addresses and expiring pairing codes. When disconnected, the last snapshot may remain visible but all character mutation controls are read-only. Mutations are never queued for later replay.

The Phase 8 files are split by responsibility:

- `DidSyncClient.kt` — pairing, authenticated WebSocket reconnect, revisions, LAN/expiry validation and commands.
- `DidCompanionViewModel.kt` — UI state, reconnect policy, minimum Windows version enforcement and resource commands.
- `DidCharacterSnapshot.kt` — typed read-only view of the canonical Windows character JSON.
- `DidCompanionSheet.kt` — Character / Equipment / Notes phone navigation backed by synchronized state.
- `Phase8CompanionRoot.kt` — connection-vs-character root surface.
- `Phase8ActivityBridge.kt` — thin Activity bridge for pairing and update actions.
- `PairingScanner.kt` — QR pairing via Google Code Scanner; manual paste remains available.
- `GitHubUpdateChecker.kt`, `AndroidUpdateController.kt`, `UpdateNotice.kt` — GitHub update flow.

The first writable synchronized slice is HP, Adversity Tokens and Improvement Points. Improvements, inventory and notes are already transported/displayed from the canonical Windows snapshot but remain read-only until their command contracts are added.

## Compatibility

`updates/android.json` records:

- Android version
- minimum compatible Windows version
- sync protocol version
- published APK/release URLs
- release notes

Android `0.8.0` is currently staged against the first sync-enabled Windows release, `1.0.11`, with Sync Protocol v1. Windows `1.0.10` correctly advertises protocol `0` because it predates mobile sync.

The Android code constants, manifests, Windows compatibility table, protocol docs and test vectors are cross-checked by GitHub Actions so they cannot silently drift apart.

## Required Android dependencies and signing

See `phase8/Phase8Dependencies.md` for Gradle dependencies, LAN cleartext handling, release signing environment variables and the GitHub signing-secret names.
