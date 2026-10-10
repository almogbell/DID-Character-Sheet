from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path} is missing Phase 9/V8 invariants: {missing}")


def forbid(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    present = [needle for needle in needles if needle in text]
    if present:
        raise SystemExit(f"{path} contains forbidden obsolete UI: {present}")


def require_file(path: str) -> None:
    if not (ROOT / path).is_file():
        raise SystemExit(f"Missing required Phase 9/V8 file: {path}")


def main() -> None:
    require(
        "android/phase8/DidTheme.kt",
        "0xFFCDAA63",
        "FontFamily.Serif",
        "DidTheme",
    )
    require(
        "android/phase8/Phase8CompanionRoot.kt",
        "Phase9CompanionSheetV7(",
        "onSetHp = onSetHp",
        "onSetAt = onSetAt",
        "onAddNote = onAddNote",
        "onPickImages = onPickImages",
        "onEditImprovement = onEditImprovement",
        "onRollAbility = onRollAbility",
        "onRollOtherDice = onRollOtherDice",
    )
    require(
        "android/phase8/Phase9CompanionSheetV7.kt",
        "V7ToolsButton(",
        'DropdownMenuItem(text = { Text("Add Note") }',
        'DropdownMenuItem(text = { Text("Add Character Picture") }',
        'DropdownMenuItem(text = { Text("Adjust Resources") }',
        'DropdownMenuItem(text = { Text("Roll Other Dice…") }',
        "V7PortraitGallery(",
        "onRemoveImage",
        "onSetHp(target)",
        "onSetAt(target)",
        "V7InventoryDialog(",
        "V7NoteDialog(",
        "V7ImprovementEditDialog(",
        "V7QuantityBox(",
        'Text("+",',
        'Text("-",',
        'Text("×"',
        'snapshot.uiIcons["inventory"]',
        'snapshot.uiIcons["notes"]',
        "V7DiceResultDialog(",
        "V7OtherDiceDialog(",
        "V7HistoryDialog(",
        "onDoubleTap",
    )
    forbid(
        "android/phase8/Phase9CompanionSheetV7.kt",
        'Text("${snapshot.adversity.current}/${snapshot.adversity.max}"',
        'Text("Improvement Points"',
    )
    require(
        "android/phase8/DidCompanionViewModel.kt",
        '"resource.set"',
        '"resource.adjust"',
        '"note.add"',
        '"note.update"',
        '"note.remove"',
        '"image.add"',
        '"image.remove"',
        '"improvement.edit"',
        '"dice.roll"',
        "serialized",
    )
    require(
        "android/phase8/DidSyncClient.kt",
        'const val PREFS_NAME = "did_companion_sync"',
        ".putString(KEY_DEVICE_TOKEN, token)",
        ".commit()",
        "connectSaved()",
    )
    require(
        "android/phase8/PairingScanner.kt",
        "ScanContract()",
        "ScanOptions.QR_CODE",
        "DidSyncClient.PairingPayload.fromQrJson",
    )
    require(
        "windows/mobile_sync_v7.py",
        'action == "resource.set"',
        'action == "note.add"',
        'action == "note.update"',
        'action == "image.add"',
        'action == "improvement.edit"',
        'action == "dice.roll"',
    )
    require(
        "windows/mobile_sync_frontend_adapter.py",
        'state["_mobile_ui"]',
        '"inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg")',
        'os.path.join(app_dir, "icons", "notes", "custom.svg")',
        "handle_mobile_v7_action",
        "mark_dirty(auto_save=True)",
    )
    require(
        "windows/mobile_companion_dialog.py",
        "QR_DISPLAY_SIZE = 336",
        "ERROR_CORRECT_Q",
        "Qt.TransformationMode.FastTransformation",
        "box_size=10",
        "border=4",
    )
    require(
        "sync/build_phase9_desktop_delta.py",
        '"mobile_companion_dialog.py"',
        "Phase 9 V8 desktop delta",
    )
    require(
        "android/app/src/main/AndroidManifest.xml",
        'android.permission.CAMERA',
        'android.hardware.camera.any',
        'android:icon="@drawable/did_desktop_icon"',
        'android:roundIcon="@drawable/did_desktop_icon"',
        'android:fullBackupContent="@xml/backup_rules"',
        'android:dataExtractionRules="@xml/data_extraction_rules"',
    )
    require_file("android/app/src/main/res/drawable-nodpi/did_desktop_icon.png")
    require(
        "android/app/src/main/res/xml/backup_rules.xml",
        "did_companion_sync.xml",
    )
    require(
        "android/app/src/main/res/xml/data_extraction_rules.xml",
        "did_companion_sync.xml",
        "cloud-backup",
        "device-transfer",
    )
    require(
        "android/app/build.gradle.kts",
        "com.journeyapps:zxing-android-embedded:4.3.0",
        "com.caverock:androidsvg-aar:1.4",
        "versionCode = 15",
        'versionNameSuffix = "-phase9-test2-v8"',
    )
    print("Phase 9 V8 mobile parity and pairing invariants OK")


if __name__ == "__main__":
    main()
