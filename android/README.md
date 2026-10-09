# DID Character Sheet — Android Companion

The Android app is a mobile companion to the Windows DID Character Sheet.

It is designed to feel like the desktop character sheet adapted for a phone, while keeping the Windows application authoritative for character rules and saved character data.

## Releases

Android releases use tags such as `android-v0.8.0` and the Android updater reads `updates/android.json`.

Android and Windows use independent version numbers and may be released separately.

## Synchronization

Normal use does not copy `.didchar` files to the phone. Android pairs with a running Windows DID application, stores a per-device credential in private application storage, reconnects automatically, and consumes canonical Windows snapshots.

When disconnected, the last snapshot may remain visible but all character mutation controls are read-only. Mutations are never queued for later replay.

The Phase 8 files are split by responsibility:

- `DidSyncClient.kt` — pairing, authenticated WebSocket reconnect, revisions and commands.
- `DidCompanionViewModel.kt` — UI state, reconnect policy, minimum Windows version enforcement and resource commands.
- `DidCharacterSnapshot.kt` — typed read-only view of the canonical Windows character JSON.
- `DidCompanionSheet.kt` — Character / Equipment / Notes phone navigation backed by synchronized state.
- `Phase8CompanionRoot.kt` — connection-vs-character root surface.
- `PairingScanner.kt` — QR pairing via Google Code Scanner.
- `GitHubUpdateChecker.kt`, `AndroidUpdateController.kt`, `UpdateNotice.kt` — GitHub update flow.

The first writable synchronized slice is HP, Adversity Tokens and Improvement Points. Improvements, inventory and notes are already transported/displayed from the canonical Windows snapshot but remain read-only until their command contracts are added.

## Compatibility

`updates/android.json` records:

- Android version
- minimum compatible Windows version
- sync protocol version
- published APK/release URLs

The same Android version, minimum Windows version and protocol constants are checked by GitHub Actions so code and manifest values cannot silently drift apart.

## Required Android dependencies

See `phase8/Phase8Dependencies.md`. Phase 8 uses OkHttp WebSockets and Google Code Scanner, plus Android Internet permission. LAN WebSockets use `ws://`, so the final Android project must permit cleartext only for the local companion connection rather than broadly weakening HTTPS behavior.
