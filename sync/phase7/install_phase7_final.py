from __future__ import annotations

import runpy
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


def repair_support_file():
    support = Path(__file__).resolve().parent
    role_ui = support / "campaign_role_ui.py"
    text = role_ui.read_text(encoding="utf-8")
    if FIXED_SUBTITLE in text:
        return False
    if BROKEN_SUBTITLE not in text:
        raise RuntimeError(
            "Could not safely repair campaign_role_ui.py. Download the latest Phase 7 ZIP again."
        )
    role_ui.write_text(text.replace(BROKEN_SUBTITLE, FIXED_SUBTITLE, 1), encoding="utf-8")
    return True


def main():
    changed = repair_support_file()
    print("Phase 7 preflight UI repair: PASS" if changed else "Phase 7 preflight UI repair: already fixed")
    installer = Path(__file__).resolve().parent / "install_phase7.py"
    runpy.run_path(str(installer), run_name="__main__")


if __name__ == "__main__":
    main()
