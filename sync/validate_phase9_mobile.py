from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(path: str, *needles: str) -> None:
    text = (ROOT / path).read_text(encoding="utf-8")
    missing = [needle for needle in needles if needle not in text]
    if missing:
        raise SystemExit(f"{path} is missing Phase 9 invariants: {missing}")


def main() -> None:
    require(
        "android/phase8/DidTheme.kt",
        "0xFFCDAA63",
        "FontFamily.Serif",
        "DidTheme",
    )
    require(
        "android/phase8/Phase8CompanionRoot.kt",
        "Phase9CompanionSheetV3(",
        "onSetName = onSetName",
        "onAddInventoryItem = onAddInventoryItem",
    )
    require(
        "android/phase8/Phase9CompanionSheetV3.kt",
        "V3Hearts(",
        "onQuarterTap",
        "V3Adversity(",
        "index < at.current",
        "V3DesktopSvg",
        'snapshot.uiIcons["dr"]',
        'snapshot.uiIcons[stat.key]',
        "ContentScale.Fit",
        "didHtmlToAnnotatedString(improvement.description)",
        "didHtmlToAnnotatedString(note.text.text)",
        "V3QuantityCircle",
        'Text("⋮"',
        'V3Heading("Inventory"',
        'V3Heading("Notes")',
        'Character("Character"',
        'Equipment("Equipment"',
        'Notes("Notes"',
        "onRemoveInventoryItem",
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
    )
    print("Phase 9 mobile parity invariants OK")


if __name__ == "__main__":
    main()
