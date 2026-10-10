from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])

    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (
            (root / "frontend_2_8.py").is_file()
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 6 DID project. Put this script in the phase6 "
        "folder inside your current code folder and run it from there."
    )


def replace_once(text: str, old: str, new: str, label: str):
    if new in text:
        return text, False
    if old not in text:
        raise RuntimeError(f"Could not safely locate {label} in campaign_ui.py.")
    return text.replace(old, new, 1), True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original

    # v10 intentionally resized the dialog per page. That made Campaign,
    # Character, and Creation Rules visibly jump to three different sizes.
    # Keep one stable wizard footprint instead, sized for the largest page.
    old_show_tail = '''        # Keep the same compact, form-like proportions as CharacterTemplateDialog.\n        # Sparse pages should not be forced to the height of the rules page.\n        page_heights = (250, 330, 385)\n        window_heights = (470, 550, 610)\n        self.campaign_pages.setFixedHeight(page_heights[index])\n        self.resize(self.width(), window_heights[index])\n'''
    new_show_tail = '''        # Keep one stable wizard size on every step. Changing pages must not\n        # resize the window or move the navigation controls.\n        self.campaign_pages.setFixedHeight(385)\n        if self.height() != 610:\n            self.resize(self.width(), 610)\n'''
    text, page_changed = replace_once(
        text,
        old_show_tail,
        new_show_tail,
        "adaptive per-page sizing",
    )

    # Start at the same final size instead of opening small and growing on the
    # first page switch. Width remains user-resizable; only the initial height
    # is normalized to the size required by the largest step.
    text, init_changed = replace_once(
        text,
        "        self.resize(900, 470)\n        self.setMinimumSize(820, 450)\n",
        "        self.resize(900, 610)\n        self.setMinimumSize(820, 580)\n",
        "Campaign initial size",
    )

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v11_same_size")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    print("Same size on all 3 pages: PASS" if page_changed else "Same size on all 3 pages: already installed")
    print("Stable initial window size: PASS" if init_changed else "Stable initial window size: already installed")
    print("v9 alignment / Cancel-left / hidden-arrow changes: PRESERVED")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
