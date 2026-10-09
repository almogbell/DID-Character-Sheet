# Phase 8 Android project integration

## Runtime dependencies

The buildable `android/app` module already includes the Phase 8 runtime dependencies:

```kotlin
implementation("com.squareup.okhttp3:okhttp:4.12.0")
implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
```

- OkHttp provides the authenticated companion WebSocket.
- Google Code Scanner provides the QR scanner UI without a custom camera preview or app-level CAMERA permission.
- `CompanionConnectionScreen` also supports pasting the pairing JSON when Google Play services/scanning is unavailable.

## Manifest networking

The application has the `INTERNET` permission and enables cleartext transport because Phase 8 connects to a dynamic private IPv4 address such as `192.168.1.20` using `ws://`.

Android Network Security Configuration cannot practically enumerate the user's LAN computer address in advance. The transport code therefore applies the restriction in code: pairing and saved reconnect hosts must be private/link-local IPv4 addresses. Internet update traffic remains HTTPS-only and `AndroidUpdateController` refuses update links which are not HTTPS GitHub/GitHubusercontent links.

Do not add a public hostname or port-forward TCP 8765 for Phase 8.

## Debug validation

`.github/workflows/phase8-validation.yml` uses JDK 17 and Gradle 8.11.1 to build `:app:assembleDebug` on every Android/Phase 8 change and publishes the APK as a workflow artifact. This catches real Kotlin/Compose/Gradle integration failures in addition to the static protocol checks.

## Release signing for GitHub Actions

`.github/workflows/android-release.yml` expects these repository secrets:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

The workflow restores the keystore only inside the temporary GitHub Actions runner and supplies these environment variables to `android/app/build.gradle.kts`:

- `DID_RELEASE_STORE_FILE`
- `DID_RELEASE_STORE_PASSWORD`
- `DID_RELEASE_KEY_ALIAS`
- `DID_RELEASE_KEY_PASSWORD`

The keystore itself must never be committed to GitHub. The same signing key must be retained for every future APK update; Android will reject an update signed by a different key.

## Release flow

Once the matching sync-enabled Windows build is published and the signing secrets exist:

1. Set the new Android version in code, `android/app/build.gradle.kts`, and `updates/android.json`.
2. Put the release notes in `updates/android.json`.
3. Make sure `updates/windows.json` advertises at least the Android build's `minimum_desktop_version` and matching sync protocol.
4. Push a tag such as `android-v0.8.0`.

The GitHub workflow then builds the signed APK, creates the Android GitHub Release, and updates `updates/android.json` on `main` with the final APK/release URLs. Future installed Android builds read that manifest to find updates.
