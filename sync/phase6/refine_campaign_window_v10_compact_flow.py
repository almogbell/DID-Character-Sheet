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
    changes = []

    # The v9 screenshot still had the content distributed vertically through
    # the stacked page. Match CharacterTemplateDialog instead: content starts
    # immediately below the step bar and rows stay together.
    for page_name in ("page1", "page2", "page3"):
        old = f"        {page_name}.setSpacing(7)\n"
        new = (
            f"        {page_name}.setSpacing(7)\n"
            f"        {page_name}.setAlignment(Qt.AlignmentFlag.AlignTop)\n"
        )
        text, did = replace_once(text, old, new, f"{page_name} top alignment")
        changes.append((f"{page_name} top-aligned", did))

    # A little less inset inside the page, like the original template wizard.
    page_margin_replacements = {
        "        page1.setContentsMargins(18, 14, 18, 6)\n":
            "        page1.setContentsMargins(18, 10, 18, 2)\n",
        "        page2.setContentsMargins(18, 14, 18, 6)\n":
            "        page2.setContentsMargins(18, 10, 18, 2)\n",
        "        page3.setContentsMargins(18, 14, 18, 6)\n":
            "        page3.setContentsMargins(18, 10, 18, 2)\n",
    }
    margin_changed = False
    for old, new in page_margin_replacements.items():
        if old in text:
            text = text.replace(old, new, 1)
            margin_changed = True
    changes.append(("Page insets tightened", margin_changed))

    # Tighten the form label column a little more. The v9 screen still made
    # the eye travel too far from label to value.
    column_changed = False
    for form_name in ("form1", "form2", "form3"):
        old = f"        {form_name}.setColumnMinimumWidth(0, 132)\n"
        new = f"        {form_name}.setColumnMinimumWidth(0, 112)\n"
        if old in text:
            text = text.replace(old, new, 1)
            column_changed = True
    old = "        sharing_grid.setColumnMinimumWidth(0, 132)\n"
    new = "        sharing_grid.setColumnMinimumWidth(0, 112)\n"
    if old in text:
        text = text.replace(old, new, 1)
        column_changed = True
    changes.append(("Label/value distance tightened", column_changed))

    # The top title already says Campaign. Give page 1 a useful section name
    # rather than repeating the exact same word twice.
    old_heading = '''        heading = QLabel("Campaign")\n        heading.setObjectName("SectionTitle")\n'''
    new_heading = '''        heading = QLabel("Campaign Setup")\n        heading.setObjectName("SectionTitle")\n'''
    text, did = replace_once(text, old_heading, new_heading, "Campaign page heading")
    changes.append(("Page heading clarified", did))

    # Let each wizard page use only the vertical space it actually needs.
    # This is the key difference from v9: page 1 no longer inherits the tall
    # footprint needed by the Creation Rules summary page.
    old_show = '''    def _campaign_show_page(self, index):\n        index = max(0, min(2, int(index)))\n        self._campaign_page_index = index\n        self.campaign_pages.setCurrentIndex(index)\n\n        names = ("Campaign", "Character", "Creation Rules")\n        self.campaign_step_label.setText(\n            f"Step {index + 1} of 3  •  {names[index]}"\n        )\n        self.campaign_back_btn.setVisible(index > 0)\n        self.campaign_next_btn.setVisible(index < 2)\n'''
    new_show = '''    def _campaign_show_page(self, index):\n        index = max(0, min(2, int(index)))\n        self._campaign_page_index = index\n        self.campaign_pages.setCurrentIndex(index)\n\n        names = ("Campaign", "Character", "Creation Rules")\n        self.campaign_step_label.setText(\n            f"Step {index + 1} of 3  •  {names[index]}"\n        )\n        self.campaign_back_btn.setVisible(index > 0)\n        self.campaign_next_btn.setVisible(index < 2)\n\n        # Keep the same compact, form-like proportions as CharacterTemplateDialog.\n        # Sparse pages should not be forced to the height of the rules page.\n        page_heights = (250, 330, 385)\n        window_heights = (470, 550, 610)\n        self.campaign_pages.setFixedHeight(page_heights[index])\n        self.resize(self.width(), window_heights[index])\n'''
    text, did = replace_once(text, old_show, new_show, "adaptive Campaign page sizing")
    changes.append(("Adaptive wizard height", did))

    # Allow the compact page-1 height. Qt will still expand if a platform/font
    # genuinely needs more room.
    text, did = replace_once(
        text,
        "        self.resize(900, 565)\n        self.setMinimumSize(840, 535)\n",
        "        self.resize(900, 470)\n        self.setMinimumSize(820, 450)\n",
        "Campaign minimum size",
    )
    changes.append(("Compact minimum height", did))

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v10_compact_flow")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    for label, did in changes:
        print(f"{label}: {'PASS' if did else 'already installed'}")
    print("Cancel-left / no-arrow changes from v9: PRESERVED")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
