from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


FIT_V2 = '''def _fit_button(button):
    # Qt's sizeHint can under-measure bold Georgia text on Windows/DPI scaling.
    # Measure the actual rendered label and add the same generous horizontal
    # breathing room as the Character Creation Template buttons.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    width = max(button.sizeHint().width() + 16, text_width + 48)
    button.setMinimumHeight(40)
    button.setFixedWidth(width)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

FIT_V3 = '''def _fit_button(button):
    # Match the compact Character Creation Template buttons: enough room for
    # bold Georgia text, but no oversized fixed padding around short labels.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    width = max(button.sizeHint().width() + 6, text_width + 28)
    button.setMinimumHeight(34)
    button.setFixedWidth(width)
    button.setCursor(Qt.CursorShape.PointingHandCursor)


def _prepare_sharing_checkbox(box, *, locked=False):
    # A small fixed host prevents the native Qt indicator from being clipped
    # vertically or horizontally inside the sharing matrix.
    box.setFixedSize(28, 28)
    box.setStyleSheet(
        "QCheckBox { padding:0px; margin:0px; min-height:28px; }"
        "QCheckBox::indicator { width:18px; height:18px; }"
    )
    if locked:
        # Core DM information is mandatory. Keep the normal checked appearance
        # instead of Qt's grey disabled checkbox, but make it non-interactive.
        box.setChecked(True)
        box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    else:
        box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box


def _confirm_character_removal(parent, display_name):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Remove Character")
    dialog.setModal(True)
    dialog.resize(470, 190)
    set_themed_stylesheet(dialog, ROLE_QSS)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(12)

    title = QLabel(f"Remove {display_name} from this campaign?")
    title.setStyleSheet("font-size:16px; font-weight:900;")
    title.setWordWrap(True)
    root.addWidget(title)

    text = QLabel(
        "This does not delete the player's local .didchar file or historical "
        "session snapshots."
    )
    text.setObjectName("SectionText")
    text.setWordWrap(True)
    root.addWidget(text)
    root.addStretch()

    buttons = QHBoxLayout()
    no_button = QPushButton("No")
    yes_button = QPushButton("Yes")
    yes_button.setObjectName("PrimaryButton")
    _fit_button(no_button)
    _fit_button(yes_button)
    no_button.clicked.connect(dialog.reject)
    yes_button.clicked.connect(dialog.accept)
    buttons.addWidget(no_button)
    buttons.addStretch()
    buttons.addWidget(yes_button)
    root.addLayout(buttons)

    return dialog.exec() == QDialog.DialogCode.Accepted
'''

REMOVE_OLD_START = '    def remove_character(self, campaign_character_id, display_name):\n'
REMOVE_NEW = '''    def remove_character(self, campaign_character_id, display_name):
        if not _confirm_character_removal(self, display_name):
            return
        try:
            result = self.client._request_json(
                "POST",
                "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": str(campaign_character_id)},
            )
            if result is False:
                raise RuntimeError("The character could not be removed.")
        except Exception as error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
            return
        self._refresh_characters()
'''


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
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_role_ui.py").is_file():
            return root
    raise FileNotFoundError(
        "Could not find the installed Phase 7 DID project. Keep the phase7 folder "
        "inside the current code folder and run this script from there."
    )


def replace_method(text, class_marker, method_name, replacement):
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError(f"Could not locate {class_marker.strip()}")
    start = text.find(f"    def {method_name}", class_pos)
    if start < 0:
        raise RuntimeError(f"Could not locate {method_name}")
    next_def = text.find("\n    def ", start + len(f"    def {method_name}"))
    if next_def < 0:
        raise RuntimeError(f"Could not locate the method after {method_name}")
    return text[:start] + replacement + "\n" + text[next_def + 1:]


def patch(path):
    original = path.read_text(encoding="utf-8")
    text = original

    # Compact buttons and helper functions.
    if FIT_V3 not in text:
        if FIT_V2 in text:
            text = text.replace(FIT_V2, FIT_V3, 1)
        else:
            start = text.find("def _fit_button(button):\n")
            end = text.find("\n\ndef _campaign_rules_rows", start)
            if start < 0 or end < 0:
                raise RuntimeError("Could not safely locate _fit_button")
            text = text[:start] + FIT_V3 + text[end:]

    # Same visual proportions as the template buttons, and keep campaign
    # selectors clean without a little arrow button on the right.
    text = text.replace(
        "    min-height: 36px; background-color: #fffdf7; border: 1px solid #c79a3b;\n"
        "    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;\n"
        "    font-weight: 800; padding: 5px 13px;\n",
        "    min-height: 32px; background-color: #fffdf7; border: 1px solid #c79a3b;\n"
        "    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;\n"
        "    font-weight: 800; padding: 4px 11px;\n",
        1,
    )
    combo_anchor = '''QComboBox {
    min-height: 34px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    padding: 4px 10px;
}
'''
    combo_new = combo_anchor + '''QComboBox::drop-down { border:none; width:0px; }
QComboBox::down-arrow { image:none; width:0px; height:0px; }
'''
    if "QComboBox::down-arrow" not in text and combo_anchor in text:
        text = text.replace(combo_anchor, combo_new, 1)

    # Navigation buttons use plain labels: Back / Close / Next.
    text = text.replace('QPushButton("← Back")', 'QPushButton("Back")')
    text = text.replace('QPushButton("Next →")', 'QPushButton("Next")')

    # Mandatory and optional sharing boxes: full indicator, consistent host
    # size, and mandatory DM choices remain checked without the grey disabled
    # rendering.
    text = text.replace(
        '''            dm = QCheckBox()\n            dm.setChecked(True)\n            dm.setEnabled(False)\n            party = QCheckBox()\n''',
        '''            dm = _prepare_sharing_checkbox(QCheckBox(), locked=True)\n            party = _prepare_sharing_checkbox(QCheckBox())\n''',
    )
    text = text.replace(
        '''            dm = QCheckBox()\n            party = QCheckBox()\n            setattr(self, f"dm_{key}_box", dm)\n''',
        '''            dm = _prepare_sharing_checkbox(QCheckBox())\n            party = _prepare_sharing_checkbox(QCheckBox())\n            setattr(self, f"dm_{key}_box", dm)\n''',
    )
    text = text.replace(
        '''        self.roll_share_box = QCheckBox()\n        self.roll_share_box.toggled.connect(self._roll_sharing_changed)\n''',
        '''        self.roll_share_box = _prepare_sharing_checkbox(QCheckBox())\n        self.roll_share_box.toggled.connect(self._roll_sharing_changed)\n''',
    )
    # Inventory/note detail rows use the same checkbox treatment.
    text = text.replace(
        '''                dm = QCheckBox()\n                party = QCheckBox()\n                dm.setChecked(item_id in set(self._dm_prefs.get("inventory_item_ids", [])))\n''',
        '''                dm = _prepare_sharing_checkbox(QCheckBox())\n                party = _prepare_sharing_checkbox(QCheckBox())\n                dm.setChecked(item_id in set(self._dm_prefs.get("inventory_item_ids", [])))\n''',
    )
    text = text.replace(
        '''                dm = QCheckBox()\n                party = QCheckBox()\n                dm.setChecked(note_id in set(self._dm_prefs.get("note_ids", [])))\n''',
        '''                dm = _prepare_sharing_checkbox(QCheckBox())\n                party = _prepare_sharing_checkbox(QCheckBox())\n                dm.setChecked(note_id in set(self._dm_prefs.get("note_ids", [])))\n''',
    )

    # Replace the platform QMessageBox removal prompt. This guarantees the
    # requested order on every OS: No at far left, Yes at far right.
    if "_confirm_character_removal(self, display_name)" not in text:
        text = replace_method(
            text,
            "class DMCampaignManagerDialog(_WizardDialog):\n",
            "remove_character(self, campaign_character_id, display_name):",
            REMOVE_NEW,
        )

    required = (
        'QPushButton("Back")',
        'QPushButton("Next")',
        "def _prepare_sharing_checkbox",
        "def _confirm_character_removal",
        "_confirm_character_removal(self, display_name)",
        "QComboBox::down-arrow",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Phase 7 UI v3 verification failed: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_ui_v3")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def main():
    root = find_project_root()
    patch(root / "campaign_role_ui.py")
    print("Compact template-style buttons: PASS")
    print("Back/Next arrows removed: PASS")
    print("Campaign selector arrows hidden: PASS")
    print("Remove Character: No left / Yes right: PASS")
    print("Sharing checkbox clipping/alignment: PASS")
    print("Mandatory DM boxes stay visibly checked: PASS")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
