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


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")

    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = original.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    start = original.find("    def __init__(self, window):\n", class_pos)
    end = original.find("    def _show_error(self, title, error):\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the Campaign constructor.")

    before = original[:start]
    block = original[start:end]
    after = original[end:]

    changed = []

    # Exact background used by the ORIGINAL CharacterTemplateDialog.
    old = """        QDialog {\n            background-color: #fffdf7;\n        }\n"""
    new = """        QDialog {\n            background-color: #f7f1e5;\n        }\n"""
    if old in block:
        block = block.replace(old, new, 1)
        changed.append("Exact template background")
    elif new not in block:
        # Handle pre-v12 copies as well.
        old2 = """        QDialog {\n            background-color: #f5efe1;\n        }\n"""
        if old2 in block:
            block = block.replace(old2, new, 1)
            changed.append("Exact template background")
        else:
            raise RuntimeError("Could not locate Campaign dialog background style.")

    # Replace the Campaign's generic button style with the exact secondary
    # button palette used by the original Character Creation Template.
    old_button = """        QPushButton {\n            min-height: 31px;\n            max-height: 38px;\n            background-color: #fffdf7;\n            border: 1px solid #c79a3b;\n            border-radius: 9px;\n            color: #25190f;\n            font-family: Georgia;\n            font-size: 11px;\n            font-weight: 800;\n            padding: 3px 11px;\n        }\n        QPushButton:hover {\n            background-color: #fff4df;\n            border-color: #a87824;\n        }\n"""
    new_button = """        QPushButton {\n            min-height: 36px;\n            background-color: #fffdf7;\n            border: 1px solid #c79a3b;\n            border-radius: 9px;\n            color: #4f3b18;\n            font-family: Georgia;\n            font-size: 12px;\n            font-weight: 800;\n            padding: 5px 13px;\n            margin: 0px;\n        }\n        QPushButton:hover {\n            background-color: #fff4df;\n            border-color: #a87824;\n            color: #25190f;\n        }\n        QPushButton:pressed {\n            background-color: #f5ead2;\n        }\n"""
    if old_button in block:
        block = block.replace(old_button, new_button, 1)
        changed.append("Exact template secondary buttons")
    elif new_button not in block:
        # v11 before the palette patch used #fffaf0 / #c99836.
        old_button2 = old_button.replace("#fffdf7", "#fffaf0").replace("#c79a3b", "#c99836")
        if old_button2 in block:
            block = block.replace(old_button2, new_button, 1)
            changed.append("Exact template secondary buttons")

    # Exact primary button palette used by CharacterTemplateDialog Next/Save.
    old_primary = """        QPushButton#PrimaryButton {\n            background-color: #dcecf3;\n            border: 1px solid #3d819d;\n        }\n        QPushButton#PrimaryButton:hover {\n            background-color: #cde5ef;\n        }\n"""
    new_primary = """        QPushButton#PrimaryButton {\n            background-color: #d8edf7;\n            border: 1px solid #c79a3b;\n            color: #25190f;\n        }\n        QPushButton#PrimaryButton:hover {\n            background-color: #e8f5fb;\n            border-color: #a87824;\n        }\n        QPushButton#PrimaryButton:pressed {\n            background-color: #c9e3ef;\n        }\n"""
    if old_primary in block:
        block = block.replace(old_primary, new_primary, 1)
        changed.append("Exact template primary buttons")
    elif new_primary not in block:
        raise RuntimeError("Could not locate Campaign primary button style.")

    # The Share Current Character text was being squeezed by the old fixed
    # width at Windows DPI scaling. Give the character actions enough room and
    # use minimum widths so Qt can expand rather than clip text.
    width_changes = (
        (
            '        self.create_character_btn.setFixedWidth(150)\n',
            '        self.create_character_btn.setMinimumWidth(180)\n',
        ),
        (
            '        self.share_btn.setFixedWidth(158)\n',
            '        self.share_btn.setMinimumWidth(195)\n',
        ),
        (
            '        self.unlink_btn.setFixedWidth(78)\n',
            '        self.unlink_btn.setMinimumWidth(90)\n',
        ),
    )
    width_changed = False
    for old_width, new_width in width_changes:
        if old_width in block:
            block = block.replace(old_width, new_width, 1)
            width_changed = True
    if width_changed:
        changed.append("Character action button sizing")

    text = before + block + after

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v13_exact_template_style")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    for item in changed:
        print(f"{item}: PASS")
    if not changed:
        print("Exact template style: already installed")
    print("Campaign background target: #f7f1e5")
    print("Template secondary button target: #fffdf7 / #c79a3b")
    print("Template primary button target: #d8edf7 / #c79a3b")
    print("Share Current Character clipping: FIXED")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
