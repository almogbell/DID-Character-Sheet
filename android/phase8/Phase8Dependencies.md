# Phase 8 Android dependencies

Add these to the Android app module when the Phase 8 companion code is merged into the full Android Studio project:

```kotlin
dependencies {
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.google.android.gms:play-services-code-scanner:16.1.0")
}
```

The sync client uses OkHttp WebSockets.

The QR pairing scanner uses Google Code Scanner. It provides its own scanner UI and avoids adding a custom camera preview or requesting the Android CAMERA permission. The connection screen should also keep a manual/paste pairing-code fallback for devices without compatible Google Play services.

The application manifest must allow network access:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

Phase 8 LAN sync uses `ws://` on the local network. If the app's target Android configuration blocks cleartext traffic, add a Network Security Configuration which permits cleartext only for the local companion connection rather than globally enabling arbitrary cleartext internet traffic.

The update checker uses HTTPS to read `updates/android.json` from GitHub.
