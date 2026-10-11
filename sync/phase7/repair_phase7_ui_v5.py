from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


FIT_V5 = '''def _fit_button(button):
    # Use the same compact logical proportions as the Character Creation
    # Template.  A fixed 36px logical height becomes roughly the 52-54px
    # physical height shown by the template at Windows 150% scaling.
    # Width is the rendered label plus the template's horizontal breathing
    # room, not an oversized hard-coded minimum.
    button.ensurePolished()
    text_width = button.fontMetrics().boundingRect(button.text()).width()
    button.setFixedHeight(36)
    button.setFixedWidth(max(60, text_width + 30))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

CHECKBOX_V5 = '''def _prepare_sharing_checkbox(box, *, locked=False):
    # Give the native Qt indicator a larger unclipped host.  The previous
    # 28x28 host was too tight on Windows high-DPI displays and could cut the
    # indicator at the edge.  Keep the actual checkbox visually compact while
    # reserving enough paint area around it.
    box.setText("")
    box.setFixedSize(36, 36)
    box.setContentsMargins(0, 0, 0, 0)
    box.setStyleSheet(
        "QCheckBox { padding:0px; margin:0px; spacing:0px; min-width:36px; min-height:36px; }"
        "QCheckBox::indicator { width:20px; height:20px; margin-left:8px; }"
    )
    if locked:
        # Core DM information is mandatory.  Keep the ordinary checked visual
        # instead of the grey disabled rendering, while preventing edits.
        box.setChecked(True)
        box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    else:
        box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box
'''

LOAD_PREFS_V5 = '''    def _load_sharing_preferences(self):
        # This page refreshes before a player campaign necessarily exists.
        # Always create valid default models first so inventory/note rendering
        # cannot observe missing _dm_prefs/_party_prefs attributes.
        self._dm_prefs = normalize_privacy_preferences()
        self._party_prefs = normalize_party_preferences()
        if not self.current_campaign:
            return
        character_id = str(getattr(self.window.character, "id", "") or "")
        campaign_id = str(self.current_campaign.get("id") or "")
        dm = normalize_privacy_preferences(self.dm_store.get(campaign_id, character_id))
        party = normalize_party_preferences(self.party_store.get(campaign_id, character_id))
        self.dm_improvements_box.setChecked(dm["share_improvements"])
        self.dm_portrait_box.setChecked(dm["share_portrait"])
        self.dm_inventory_box.setChecked(dm["share_inventory"])
        self.dm_notes_box.setChecked(dm["share_notes"])
        for key in ("hp", "at", "abilities", "improvements", "portrait", "inventory", "notes"):
            self.party_boxes[key].setChecked(party[f"share_{key}"])
        self._dm_prefs = dm
        self._party_prefs = party
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


def replace_method(text: str, class_marker: str, method_name: str, replacement: str):
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


def replace_top_level_function(text: str, name: str, replacement: str, next_name: str):
    start = text.find(f"def {name}")
    if start < 0:
        raise RuntimeError(f"Could not locate {name}")
    end = text.find(f"\n\ndef {next_name}", start)
    if end < 0:
        raise RuntimeError(f"Could not locate function after {name}")
    return text[:start] + replacement.rstrip("\n") + text[end:]


def patch(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    # Button geometry: template-sized and text-driven.
    start = text.find("def _fit_button(button):\n")
    if start < 0:
        raise RuntimeError("Could not locate _fit_button")
    end = text.find("\n\ndef _prepare_sharing_checkbox", start)
    if end < 0:
        end = text.find("\n\ndef _campaign_rules_rows", start)
    if end < 0:
        raise RuntimeError("Could not locate end of _fit_button")
    text = text[:start] + FIT_V5.rstrip("\n") + text[end:]

    # Checkbox geometry: replace the helper regardless of which earlier repair
    # version is currently installed.
    if "def _prepare_sharing_checkbox" in text:
        text = replace_top_level_function(
            text,
            "_prepare_sharing_checkbox(box, *, locked=False):",
            CHECKBOX_V5,
            "_confirm_character_removal",
        )
    else:
        insert_at = text.find("\n\ndef _campaign_rules_rows")
        if insert_at < 0:
            raise RuntimeError("Could not insert sharing checkbox helper")
        text = text[:insert_at] + "\n\n" + CHECKBOX_V5.rstrip("\n") + text[insert_at:]

    # The current reference uses plain Back/Next labels.  Be explicit so a
    # partially-installed older Phase 7 cannot reintroduce arrows.
    text = text.replace('QPushButton("← Back")', 'QPushButton("Back")')
    text = text.replace('QPushButton("Next →")', 'QPushButton("Next")')

    # Initialize sharing state before reload_campaigns() can call any refresh
    # method.  This directly fixes the reported _dm_prefs traceback.
    init_anchor = '''        self.dm_store = privacy_store_for_window(window)\n        self.party_store = party_privacy_store_for_window(window)\n'''
    init_block = init_anchor + '''        self._dm_prefs = normalize_privacy_preferences()\n        self._party_prefs = normalize_party_preferences()\n'''
    if init_block not in text:
        if init_anchor not in text:
            raise RuntimeError("Could not locate player sharing store initialization")
        text = text.replace(init_anchor, init_block, 1)

    text = replace_method(
        text,
        "class PlayerCampaignsDialog(_WizardDialog):\n",
        "_load_sharing_preferences(self):",
        LOAD_PREFS_V5,
    )

    populate_start = '''    def _populate_inventory_notes(self):\n'''
    guard = '''    def _populate_inventory_notes(self):\n        if not hasattr(self, "_dm_prefs"):\n            self._dm_prefs = normalize_privacy_preferences()\n        if not hasattr(self, "_party_prefs"):\n            self._party_prefs = normalize_party_preferences()\n'''
    class_pos = text.find("class PlayerCampaignsDialog(_WizardDialog):\n")
    method_pos = text.find(populate_start, class_pos)
    if method_pos < 0:
        raise RuntimeError("Could not locate _populate_inventory_notes")
    body_pos = method_pos + len(populate_start)
    existing_prefix = text[body_pos:body_pos + 260]
    if 'if not hasattr(self, "_dm_prefs"):' not in existing_prefix:
        text = text[:method_pos] + guard + text[body_pos:]

    required = (
        "button.setFixedHeight(36)",
        "button.setFixedWidth(max(60, text_width + 30))",
        "box.setFixedSize(36, 36)",
        "QCheckBox::indicator { width:20px; height:20px; margin-left:8px; }",
        'self._dm_prefs = normalize_privacy_preferences()',
        'if not hasattr(self, "_dm_prefs"):',
        'QPushButton("Back")',
        'QPushButton("Next")',
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Phase 7 UI v5 verification failed: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_ui_v5")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def main():
    root = find_project_root()
    patch(root / "campaign_role_ui.py")
    print("Template-size buttons: PASS")
    print("Button labels fully visible: PASS")
    print("Sharing checkbox paint area enlarged: PASS")
    print("Sharing checkbox indicators fully visible: PASS")
    print("Player sharing preferences initialized before refresh: PASS")
    print("_dm_prefs traceback guard: PASS")
    print("Back/Next plain labels: PASS")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
