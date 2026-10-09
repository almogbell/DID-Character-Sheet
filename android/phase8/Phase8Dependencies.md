# Phase 8 Android project integration

## Runtime dependencies

Add these to the Android app module when Phase 8 is merged into the full Android Studio project:

```kotlin
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}
```

- OkHttp provides the authenticated companion WebSocket.
- Google Code Scanner provides the QR scanner UI without a custom camera preview or app-level CAMERA permission.
- `CompanionConnectionScreen` also supports pasting the pairing JSON when Google Play services/scanning is unavailable.

## Manifest networking

The application manifest needs:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

Phase 8 connects to a dynamic private IPv4 address such as `192.168.1.20`, so Android Network Security Configuration cannot practically enumerate the computer address in advance. The final app therefore needs cleartext LAN WebSocket support, normally:

```xml
<application
    android:usesCleartextTraffic="true"
    ... />
```

The transport code compensates by refusing pairing/reconnect hosts outside private/link-local IPv4 ranges. Internet update traffic remains HTTPS-only and `AndroidUpdateController` refuses update links which are not HTTPS GitHub links.

Do not add a public hostname or port-forward TCP 8765 for Phase 8.

## Release signing for GitHub Actions

`.github/workflows/android-release.yml` expects the Android Gradle project under `android/` and these repository secrets:

- `ANDROID_KEYSTORE_BASE64`
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

The app module's `build.gradle.kts` should consume the environment variables supplied by the workflow:

```kotlin
android {
    signingConfigs {
        create("release") {
            val storePath = System.getenv("DID_RELEASE_STORE_FILE")
            if (!storePath.isNullOrBlank()) {
                storeFile = file(storePath)
                storePassword = System.getenv("DID_RELEASE_STORE_PASSWORD")
                keyAlias = System.getenv("DID_RELEASE_KEY_ALIAS")
                keyPassword = System.getenv("DID_RELEASE_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        getByName("release") {
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

The keystore itself must never be committed to GitHub.

## Release flow

When the full project is integrated and signing secrets exist, publishing Android is intentionally small:

1. Set the new Android version in code and `updates/android.json`.
2. Put the release notes in `updates/android.json`.
3. Make sure `updates/windows.json` advertises at least the Android build's `minimum_desktop_version`.
4. Push a tag such as `android-v0.8.0`.

The GitHub workflow then builds the signed APK, creates the Android GitHub Release, and updates `updates/android.json` on `main` with the final APK/release URLs. Future installed Android builds read that manifest to find updates.
