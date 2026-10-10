from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "android" / "phase8"
APP = ROOT / "android" / "app"


def read(name: str) -> str:
    return (ANDROID / name).read_text(encoding="utf-8")


def require(text: str, token: str, label: str) -> None:
    if token not in text:
        raise AssertionError(f"{label}: missing {token!r}")


def forbid(text: str, token: str, label: str) -> None:
    if token in text:
        raise AssertionError(f"{label}: forbidden token {token!r}")


def validate() -> None:
    expected = {
        "DidSyncClient.kt",
        "DidCompanionViewModel.kt",
        "DidCharacterSnapshot.kt",
        "CompanionConnectionScreen.kt",
        "DidCompanionSheet.kt",
        "Phase8CompanionRoot.kt",
        "Phase8ActivityBridge.kt",
        "PairingScanner.kt",
        "GitHubUpdateChecker.kt",
        "AndroidUpdateController.kt",
        "UpdateNotice.kt",
        "Phase9CompanionSheetV7.kt",
    }
    missing = sorted(name for name in expected if not (ANDROID / name).exists())
    if missing:
        raise AssertionError(f"Missing Android companion source files: {missing}")

    required_project_files = (
        ROOT / "android" / "settings.gradle.kts",
        ROOT / "android" / "build.gradle.kts",
        APP / "build.gradle.kts",
        APP / "src" / "main" / "AndroidManifest.xml",
        APP / "src" / "main" / "java" / "com" / "did" / "charactersheet" / "MainActivity.kt",
    )
    missing_project = [str(path.relative_to(ROOT)) for path in required_project_files if not path.exists()]
    if missing_project:
        raise AssertionError(f"Missing buildable Android project files: {missing_project}")

    client = read("DidSyncClient.kt")
    require(client, "isAllowedLanIpv4", "DidSyncClient")
    require(client, '"expires_at"', "DidSyncClient")
    require(client, "desktopVersion", "DidSyncClient")
    require(client, "connectSaved()", "DidSyncClient")
    require(client, 'PREFS_NAME = "did_companion_sync"', "DidSyncClient")
    require(client, ".commit()", "DidSyncClient")
    forbid(client, "didchar", "DidSyncClient")

    view_model = read("DidCompanionViewModel.kt")
    require(view_model, 'const val ANDROID_VERSION = "0.8.0"', "DidCompanionViewModel")
    require(view_model, 'const val MINIMUM_DESKTOP_VERSION = "1.0.11"', "DidCompanionViewModel")
    require(view_model, "snapshot: DidCharacterSnapshot?", "DidCompanionViewModel")
    for action in (
        '"resource.set"', '"resource.adjust"', '"inventory.update"',
        '"note.add"', '"note.update"', '"image.add"',
        '"improvement.edit"', '"dice.roll"',
    ):
        require(view_model, action, "DidCompanionViewModel")

    snapshot = read("DidCharacterSnapshot.kt")
    for key in (
        'optJSONObject("HP")',
        'optJSONObject("Adversity")',
        'optJSONObject("progression")',
        'optJSONObject("improvements")',
        'optJSONObject("inventory")',
        'optJSONObject("notes")',
        'optJSONObject("choices")',
    ):
        require(snapshot, key, "DidCharacterSnapshot")

    # Compose's public weight modifier is a RowScope/ColumnScope extension.
    for name in ("DidCompanionSheet.kt", "Phase8CompanionRoot.kt"):
        text = read(name)
        require(text, "Modifier.weight(", name)
        forbid(text, "import androidx.compose.foundation.layout.weight", name)

    root = read("Phase8CompanionRoot.kt")
    require(root, "Phase9CompanionSheetV7", "Phase8CompanionRoot")
    require(root, "onManualPairingCode", "Phase8CompanionRoot")
    require(root, "onRollOtherDice", "Phase8CompanionRoot")

    scanner = read("PairingScanner.kt")
    require(scanner, "com.journeyapps.barcodescanner.ScanContract", "PairingScanner")
    require(scanner, "ScanOptions.QR_CODE", "PairingScanner")
    require(scanner, "DidSyncClient.PairingPayload.fromQrJson", "PairingScanner")

    checker = read("GitHubUpdateChecker.kt")
    require(checker, 'json.optString("platform") == "android"', "GitHubUpdateChecker")
    require(checker, "https://raw.githubusercontent.com/almogbell/DID-Character-Sheet/main/updates/android.json", "GitHubUpdateChecker")

    updater = read("AndroidUpdateController.kt")
    require(updater, 'uri.scheme.equals("https"', "AndroidUpdateController")
    require(updater, 'host == "github.com"', "AndroidUpdateController")

    bridge = read("Phase8ActivityBridge.kt")
    require(bridge, "PairingScanner", "Phase8ActivityBridge")
    require(bridge, "GetMultipleContents", "Phase8ActivityBridge")
    require(bridge, "AndroidUpdateController", "Phase8ActivityBridge")

    main_activity = required_project_files[-1].read_text(encoding="utf-8")
    require(main_activity, "Phase8CompanionRoot", "MainActivity")
    require(main_activity, "Phase8ActivityBridge", "MainActivity")
    require(main_activity, "UpdateNotice", "MainActivity")
    forbid(main_activity, "import androidx.compose.foundation.layout.weight", "MainActivity")

    app_gradle = (APP / "build.gradle.kts").read_text(encoding="utf-8")
    require(app_gradle, 'java.srcDir("../phase8")', "android/app/build.gradle.kts")
    require(app_gradle, 'implementation("com.squareup.okhttp3:okhttp:4.12.0")', "android/app/build.gradle.kts")
    require(app_gradle, 'implementation("com.journeyapps:zxing-android-embedded:4.3.0")', "android/app/build.gradle.kts")

    manifest = (APP / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
    require(manifest, 'android.permission.INTERNET', "AndroidManifest.xml")
    require(manifest, 'android.permission.CAMERA', "AndroidManifest.xml")
    require(manifest, 'android:usesCleartextTraffic="true"', "AndroidManifest.xml")

    # Android never owns the .didchar persistence path; it only sends commands
    # to the authoritative Windows process.
    forbidden_io = ("FileOutputStream", "writeText(", "openFileOutput(")
    for path in ANDROID.glob("*.kt"):
        text = path.read_text(encoding="utf-8")
        if path.name == "GitHubUpdateChecker.kt":
            continue
        for token in forbidden_io:
            if token in text:
                raise AssertionError(f"{path.name}: Android companion unexpectedly contains persistence API {token!r}")

    print("Current Android companion source invariants valid")


if __name__ == "__main__":
    validate()
