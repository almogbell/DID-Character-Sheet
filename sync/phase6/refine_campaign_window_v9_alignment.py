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
    changed = []

    # 1) Keep the Campaign window compact. The wizard no longer needs to fill
    # the entire available desktop height when a page only has three rows.
    text, did = replace_once(
        text,
        '        self.resize(900, 650)\n        self.setMinimumSize(840, 610)\n',
        '        self.resize(900, 565)\n        self.setMinimumSize(840, 535)\n',
        "Campaign window size",
    )
    changed.append(("Compact window height", did))

    # 2) The whole Selected Campaign field remains clickable, but remove the
    # visual dropdown arrow to match the requested clean template field look.
    qss_anchor = '''        QComboBox {\n            min-height: 32px;\n            background-color: #fffaf0;\n            border: 1px solid #d2a650;\n            border-radius: 9px;\n            color: #25190f;\n            font-family: Georgia;\n            font-size: 12px;\n            padding: 3px 9px;\n        }\n'''
    qss_new = qss_anchor + '''        QComboBox::drop-down {\n            border: none;\n            width: 0px;\n        }\n        QComboBox::down-arrow {\n            image: none;\n            width: 0px;\n            height: 0px;\n        }\n'''
    text, did = replace_once(text, qss_anchor, qss_new, "Selected Campaign arrow style")
    changed.append(("Selected Campaign arrow removed", did))

    # 3) Match the compact label/control spacing of the original template.
    # Apply to Campaign, Character, Sharing, and Creation Rules grids.
    old_grid = '''        form1.setHorizontalSpacing(16)\n        form1.setVerticalSpacing(10)\n        form1.setColumnMinimumWidth(0, 190)\n'''
    new_grid = '''        form1.setHorizontalSpacing(10)\n        form1.setVerticalSpacing(10)\n        form1.setColumnMinimumWidth(0, 132)\n'''
    text, did = replace_once(text, old_grid, new_grid, "Campaign form spacing")
    changed.append(("Campaign field spacing", did))

    old_grid = '''        form2.setHorizontalSpacing(16)\n        form2.setVerticalSpacing(10)\n        form2.setColumnMinimumWidth(0, 190)\n'''
    new_grid = '''        form2.setHorizontalSpacing(10)\n        form2.setVerticalSpacing(10)\n        form2.setColumnMinimumWidth(0, 132)\n'''
    text, did = replace_once(text, old_grid, new_grid, "Character form spacing")
    changed.append(("Character field spacing", did))

    old_grid = '''        sharing_grid.setHorizontalSpacing(16)\n        sharing_grid.setVerticalSpacing(7)\n        sharing_grid.setColumnMinimumWidth(0, 190)\n'''
    new_grid = '''        sharing_grid.setHorizontalSpacing(10)\n        sharing_grid.setVerticalSpacing(7)\n        sharing_grid.setColumnMinimumWidth(0, 132)\n'''
    text, did = replace_once(text, old_grid, new_grid, "Sharing form spacing")
    changed.append(("Sharing field spacing", did))

    old_grid = '''        form3.setHorizontalSpacing(16)\n        form3.setVerticalSpacing(10)\n        form3.setColumnMinimumWidth(0, 190)\n'''
    new_grid = '''        form3.setHorizontalSpacing(10)\n        form3.setVerticalSpacing(10)\n        form3.setColumnMinimumWidth(0, 132)\n'''
    text, did = replace_once(text, old_grid, new_grid, "Creation Rules form spacing")
    changed.append(("Creation Rules field spacing", did))

    # 4) Don't stretch the sparse wizard pages vertically. This is what caused
    # the giant gap between the normal page controls and the bottom buttons.
    text = text.replace("        page1.addStretch()\n", "", 1)
    text = text.replace("        page2.addStretch()\n", "", 1)
    text = text.replace("        page3.addStretch()\n", "", 1)
    text, did = replace_once(
        text,
        "        root.addWidget(self.campaign_pages, 1)\n",
        "        root.addWidget(self.campaign_pages, 0)\n",
        "Campaign page stretch",
    )
    changed.append(("Bottom controls moved closer", did))

    # 5) Slightly smaller normal action buttons. Keep text readable and let the
    # layout determine position rather than making the controls dominate.
    width_replacements = {
        '        self.refresh_btn.setFixedWidth(95)\n': '        self.refresh_btn.setFixedWidth(82)\n',
        '        self.create_btn.setFixedWidth(125)\n': '        self.create_btn.setFixedWidth(112)\n',
        '        self.join_btn.setFixedWidth(125)\n': '        self.join_btn.setFixedWidth(112)\n',
        '        self.dashboard_btn.setFixedWidth(165)\n': '        self.dashboard_btn.setFixedWidth(150)\n',
        '        self.create_character_btn.setFixedWidth(165)\n': '        self.create_character_btn.setFixedWidth(150)\n',
        '        self.share_btn.setFixedWidth(175)\n': '        self.share_btn.setFixedWidth(158)\n',
        '        self.unlink_btn.setFixedWidth(90)\n': '        self.unlink_btn.setFixedWidth(78)\n',
        '        self.privacy_btn.setFixedWidth(145)\n': '        self.privacy_btn.setFixedWidth(132)\n',
        '        self.edit_rules_btn.setFixedWidth(105)\n': '        self.edit_rules_btn.setFixedWidth(92)\n',
    }
    width_changed = False
    for old, new in width_replacements.items():
        if old in text:
            text = text.replace(old, new, 1)
            width_changed = True
    changed.append(("Normal button sizing", width_changed))

    # 6) Cancel is always at the far LEFT. Navigation stays grouped on the
    # right: Back / Next, exactly where the user expects it.
    old_bottom = '''        bottom = QHBoxLayout()\n        bottom.setSpacing(8)\n        bottom.addStretch()\n\n        self.campaign_back_btn = QPushButton("← Back")\n        self.campaign_back_btn.setFixedWidth(95)\n        self.campaign_back_btn.clicked.connect(\n            lambda: self._campaign_show_page(self._campaign_page_index - 1)\n        )\n        bottom.addWidget(self.campaign_back_btn)\n\n        close = QPushButton("Close")\n        close.setFixedWidth(82)\n        close.clicked.connect(self.accept)\n        bottom.addWidget(close)\n\n        self.campaign_next_btn = QPushButton("Next →")\n        self.campaign_next_btn.setObjectName("PrimaryButton")\n        self.campaign_next_btn.setFixedWidth(95)\n        self.campaign_next_btn.clicked.connect(\n            lambda: self._campaign_show_page(self._campaign_page_index + 1)\n        )\n        bottom.addWidget(self.campaign_next_btn)\n        root.addLayout(bottom)\n'''
    new_bottom = '''        bottom = QHBoxLayout()\n        bottom.setSpacing(8)\n\n        cancel = QPushButton("Cancel")\n        cancel.setFixedWidth(82)\n        cancel.clicked.connect(self.reject)\n        bottom.addWidget(cancel)\n        bottom.addStretch()\n\n        self.campaign_back_btn = QPushButton("← Back")\n        self.campaign_back_btn.setFixedWidth(90)\n        self.campaign_back_btn.clicked.connect(\n            lambda: self._campaign_show_page(self._campaign_page_index - 1)\n        )\n        bottom.addWidget(self.campaign_back_btn)\n\n        self.campaign_next_btn = QPushButton("Next →")\n        self.campaign_next_btn.setObjectName("PrimaryButton")\n        self.campaign_next_btn.setFixedWidth(90)\n        self.campaign_next_btn.clicked.connect(\n            lambda: self._campaign_show_page(self._campaign_page_index + 1)\n        )\n        bottom.addWidget(self.campaign_next_btn)\n        root.addLayout(bottom)\n'''
    text, did = replace_once(text, old_bottom, new_bottom, "bottom navigation")
    changed.append(("Cancel moved left", did))

    # Update cursor list from the old Close variable to the new Cancel variable.
    text, did = replace_once(
        text,
        "            self.campaign_next_btn,\n            close,\n",
        "            self.campaign_next_btn,\n            cancel,\n",
        "bottom button cursor list",
    )

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v9_alignment")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    for label, did in changed:
        print(f"{label}: {'PASS' if did else 'already installed'}")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
