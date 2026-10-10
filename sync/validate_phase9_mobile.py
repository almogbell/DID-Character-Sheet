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
        "V4QuantityCircle",
        'Text("⋮"',
        'V4Heading("Inventory"',
        'V4Heading("Notes")',
        'Character("Character"',
        'Equipment("Equipment"',
        'Notes("Notes"',
        "onRemoveInventoryItem",
    )
    forbid(
        "android/phase8/Phase9CompanionSheetV4.kt",
        'Text("Improvement Points"',
        '"${snapshot.progression.currentIp} IP  •  Level ${snapshot.progression.level}"',
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
        'action == "identity.set"',
        'action == "inventory.add"',
        'action == "inventory.update"',
        'action == "inventory.remove"',
        "mark_dirty(auto_save=True)",
    )
    require(
        "android/app/build.gradle.kts",
        "com.caverock:androidsvg-aar:1.4",
        "versionCode = 11",
    )
    print("Phase 9 mobile parity invariants OK")


if __name__ == "__main__":
    main()
