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
        "#CDAA63".replace("#", "0xFF"),
        "FontFamily.Serif",
        "DidTheme",
    )
    require(
        "android/phase8/DidCompanionSheet.kt",
        "Portrait(snapshot",
        'DefenseBox("BDV"',
        'DefenseBox("DR"',
        "compareByDescending<StatSnapshot>",
        "noteColors(note.color)",
        'Character("Character"',
        'Equipment("Equipment"',
        'Notes("Notes"',
    )
    require(
        "android/phase8/DidCompanionDirectEditBridge.kt",
        "SingleTextEditDialog",
        "InventoryManagerDialog",
        "onSetName",
        "onSetBackstory",
        "onAddInventoryItem",
        "onUpdateInventoryItem",
        "onRemoveInventoryItem",
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
