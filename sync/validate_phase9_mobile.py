from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path} is missing Phase 9 invariants: {missing}")


def forbid(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    present = [needle for needle in needles if needle in text]
    if present:
        raise SystemExit(f"{path} contains forbidden V4 leftovers: {present}")


def main() -> None:
    require(
        "android/phase8/DidTheme.kt",
        "0xFFCDAA63",
        "FontFamily.Serif",
        "DidTheme",
    )
    require(
        "android/phase8/Phase8CompanionRoot.kt",
        "Phase9CompanionSheetV4(",
        "onSetName = onSetName",
        "onAddInventoryItem = onAddInventoryItem",
    )
    require(
        "android/phase8/Phase9CompanionSheetV4.kt",
        "V4NameHeader(",
        "V4PortraitGallery(",
        "snapshot.portrait.images.indices.toList()",
        "V4Hearts(",
        "onQuarterTap",
        "V4Adversity(",
        "index < at.current",
        "V4DesktopSvg",
        'snapshot.uiIcons["dr"]',
        'snapshot.uiIcons[stat.key]',
        "ContentScale.Fit",
        "didHtmlToAnnotatedString(improvement.description)",
        "V4NoteDialog(",
        "v4RenderedNoteText(note)",
        "V4InventoryQuantityBox",
        '"×"',
        'V4Heading("Inventory"',
        'V4Heading("Notes")',
        'Character("Character"',
        'Equipment("Equipment"',
        'Notes("Notes"',
        "onRemoveInventoryItem",
        "V4AppNavigationIcon",
        'snapshot.uiIcons["inventory"]',
        'snapshot.uiIcons["notes"]',
        ".scale(1.48f)",
        "onDoubleTap",
        "LaunchedEffect(snapshot.hp.current)",
        "Modifier.size(46.dp, 42.dp)",
        "Modifier.size(31.dp)",
    )
    forbid(
        "android/phase8/Phase9CompanionSheetV4.kt",
        'Text("Improvement Points"',
        '"${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}"',
        'Text("${at.current}/${at.max}"',
        'Text("⋮"',
        "V4QuantityCircle",
    )
    require(
        "android/phase8/DidCharacterSnapshot.kt",
        "uiIcons: Map<String, String>",
        'optJSONObject("_mobile_ui")',
        "didHtmlToAnnotatedString",
        "Html.fromHtml",
        "AnnotatedString",
    )
    require(
        "android/phase8/DidCompanionViewModel.kt",
        '"identity.set"',
        '"inventory.add"',
        '"inventory.update"',
        '"inventory.remove"',
    )
    require(
        "windows/mobile_sync_frontend_adapter.py",
        'state["_mobile_ui"]',
        '"agility": os.path.join(app_dir, "icons", "agility.svg")',
        '"dr": os.path.join(app_dir, "icons", "defenses", "dr.svg")',
        '"inventory": os.path.join(app_dir, "icons", "headers", "inventory.svg")',
        'os.path.join(app_dir, "icons", "notes", "custom.svg")',
        'action == "identity.set"',
        'action == "inventory.add"',
        'action == "inventory.update"',
        'action == "inventory.remove"',
        "mark_dirty(auto_save=True)",
    )
    require(
        "android/app/src/main/AndroidManifest.xml",
        'android:icon="@drawable/did_app_icon"',
        'android:roundIcon="@drawable/did_app_icon"',
    )
    require(
        "android/app/src/main/res/drawable/did_app_icon.xml",
        "#A87824",
        "#2F5F91",
    )
    require(
        "android/app/build.gradle.kts",
        "com.caverock:androidsvg-aar:1.4",
        "versionCode = 13",
    )
    print("Phase 9 mobile parity invariants OK")


if __name__ == "__main__":
    main()
