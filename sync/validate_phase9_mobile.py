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
        "Phase9CompanionSheetV2(",
        "onSetName = onSetName",
        "onAddInventoryItem = onAddInventoryItem",
    )
    require(
        "android/phase8/Phase9CompanionSheetV2.kt",
        "Phase9V2Heart(",
        "DefenseBadgeKind.BDV",
        "DefenseBadgeKind.DR",
        "Phase9V2Adversity",
        "ContentScale.Fit",
        "phase9V2AbilityColors",
        "Phase9V2AbilityEmblem",
        "didRichText(improvement.description)",
        "didRichText(empowerment.description)",
        "phase9V2LinkedNotes",
        "Phase9V2NoteIcon",
        'Character("Character"',
        'Equipment("Equipment"',
        'Notes("Notes"',
        "Phase9V2InventoryEditDialog",
        "onSetName",
        "onAddInventoryItem",
        "onUpdateInventoryItem",
        "onRemoveInventoryItem",
    )
    require(
        "android/phase8/DidRichText.kt",
        "DID_RICH_NOTE_MARKER",
        "Html.fromHtml",
        "AnnotatedString",
        "UnderlineSpan",
        "Typeface.BOLD_ITALIC",
    )
    require(
        "android/phase8/DidCharacterSnapshot.kt",
        "RICH_NOTE_MARKER",
        "Html.fromHtml",
        "AnnotatedString",
        "UnderlineSpan",
        "Typeface.BOLD_ITALIC",
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
        'action == "identity.set"',
        'action == "inventory.add"',
        'action == "inventory.update"',
        'action == "inventory.remove"',
        "mark_dirty(auto_save=True)",
    )
    print("Phase 9 mobile parity invariants OK")


if __name__ == "__main__":
    main()
