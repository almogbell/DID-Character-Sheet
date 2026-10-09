# DID Character Sheet — Android Companion

The Android app is a mobile companion to the Windows DID Character Sheet.

It is designed to feel like the desktop character sheet adapted for a phone, while keeping the Windows application authoritative for character rules and saved character data.

## Releases

Android releases use tags such as:

`android-v0.8.0`

The Android updater reads:

`updates/android.json`

Android and Windows use independent version numbers and may be released separately.

## Synchronization

The Android app should connect directly to the running Windows application. Normal use should not require copying `.didchar` files to the phone.

The update manifest also records the minimum compatible desktop version and the synchronization protocol version so incompatible versions can fail with a clear message instead of silently misbehaving.
