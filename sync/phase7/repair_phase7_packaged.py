from __future__ import annotations

from pathlib import Path


BROKEN_SUBTITLE = '''            subtitle = QLabel(
                " • ".join(x for x in (str(state.get("species") or ""), f"Level {int(state.get('level') or 1)}") if state else "") if x)
            )
'''

FIXED_SUBTITLE = '''            subtitle_parts = []
            if state:
                species = str(state.get("species") or "").strip()
                if species:
                    subtitle_parts.append(species)
                subtitle_parts.append(f"Level {int(state.get('level') or 1)}")
            subtitle = QLabel(" • ".join(subtitle_parts))
'''


def repair(path=None):
    target = Path(path or (Path(__file__).resolve().parent / "campaign_role_ui.py"))
    text = target.read_text(encoding="utf-8")
    if FIXED_SUBTITLE in text:
        return False
    if BROKEN_SUBTITLE not in text:
        raise RuntimeError("Phase 7 Campaign UI repair target was not found")
    target.write_text(text.replace(BROKEN_SUBTITLE, FIXED_SUBTITLE, 1), encoding="utf-8")
    return True


if __name__ == "__main__":
    print("repaired" if repair() else "already fixed")
