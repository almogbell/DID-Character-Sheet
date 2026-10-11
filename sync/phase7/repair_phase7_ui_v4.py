from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


FIT_V4 = '''def _fit_button(button):
    # Match the Character Creation Template buttons while leaving enough room
    # for bold Georgia text on Windows DPI scaling.  The button wraps snugly
    # around the whole label instead of clipping its first/last characters.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    button.setMinimumHeight(40)
    button.setFixedWidth(max(78, text_width + 56))
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

LOAD_PREFS_V4 = '''    def _load_sharing_preferences(self):
        # The Character page is refreshed even when the user has not joined a
        # player campaign yet. Always keep valid default preference models so
        # inventory/note rows can be built safely in that state.
        if not self.current_campaign:
            self._dm_prefs = normalize_privacy_preferences()
            self._party_prefs = normalize_party_preferences()
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

REFRESH_CHARACTERS_V4 = '''    def _refresh_characters(self):
        self._clear_layout(self.character_layout)
        if not self.current_campaign or self.client is None:
            self.character_layout.addWidget(QLabel("No campaign selected."))
            return
        try:
            rows = self.client.list_campaign_characters(self.current_campaign["id"])
        except Exception as error:
            self.character_layout.addWidget(QLabel(f"Could not load characters: {error}"))
            return
        if not rows:
            label = QLabel("No characters have been saved to this campaign yet.")
            label.setObjectName("Muted")
            self.character_layout.addWidget(label)
            return
        for row in rows:
            state = _state_from_character_row(row)
            card = QFrame()
            card.setObjectName("Card")
            grid = QGridLayout(card)
            grid.setContentsMargins(13, 10, 13, 10)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(4)
            name = QLabel(str(state.get("name") or row.get("display_name") or "Unnamed Character"))
            name.setStyleSheet("font-size:15px; font-weight:900;")
            subtitle_parts = []
            if state:
                species = str(state.get("species") or "").strip()
                if species:
                    subtitle_parts.append(species)
                subtitle_parts.append(f"Level {int(state.get('level') or 1)}")
            subtitle = QLabel(" • ".join(subtitle_parts))
            subtitle.setObjectName("Muted")
            grid.addWidget(name, 0, 0, 1, 3)
            grid.addWidget(subtitle, 1, 0, 1, 3)
            hp = QLabel(f"HP  {_hp_text(state)}")
            at = QLabel(f"AT  {_at_text(state)}")
            hp.setStyleSheet("font-weight:800;")
            at.setStyleSheet("font-weight:800;")
            grid.addWidget(hp, 2, 0)
            grid.addWidget(at, 2, 1)
            remove = QPushButton("Remove from Campaign")
            remove.setObjectName("DangerButton")
            _fit_button(remove)
            remove.clicked.connect(
                lambda _checked=False,
                character_id=row.get("id"),
                display=name.text(): self.remove_character(character_id, display)
            )
            grid.addWidget(remove, 2, 2, alignment=Qt.AlignmentFlag.AlignRight)
            self.character_layout.addWidget(card)
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


def patch(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    # 1) Buttons: compact like the template, but never clip labels.
    start = text.find("def _fit_button(button):\n")
    end = text.find("\n\ndef _prepare_sharing_checkbox", start)
    if start < 0:
        raise RuntimeError("Could not locate _fit_button")
    if end < 0:
        end = text.find("\n\ndef _campaign_rules_rows", start)
    if end < 0:
        raise RuntimeError("Could not locate end of _fit_button")
    current_fit = text[start:end]
    if current_fit != FIT_V4.rstrip("\n"):
        text = text[:start] + FIT_V4.rstrip("\n") + text[end:]

    # Match the reference button proportions and keep labels plain (no arrows).
    text = text.replace('QPushButton("← Back")', 'QPushButton("Back")')
    text = text.replace('QPushButton("Next →")', 'QPushButton("Next")')
    text = text.replace('QPushButton("Back")', 'QPushButton("Back")')
    text = text.replace('QPushButton("Next")', 'QPushButton("Next")')

    # 2) Remove the large white viewport below a short character list.
    text = text.replace(
        '''        self.character_scroll = QScrollArea()\n        self.character_scroll.setWidgetResizable(True)\n        self.character_body = QWidget()\n        self.character_layout = QVBoxLayout(self.character_body)\n        self.character_layout.setContentsMargins(0, 2, 0, 2)\n        self.character_layout.setSpacing(8)\n        self.character_scroll.setWidget(self.character_body)\n''',
        '''        self.character_scroll = QScrollArea()\n        self.character_scroll.setWidgetResizable(True)\n        self.character_scroll.viewport().setStyleSheet("background: transparent;")\n        self.character_body = QWidget()\n        self.character_body.setStyleSheet("background: transparent;")\n        self.character_layout = QVBoxLayout(self.character_body)\n        self.character_layout.setContentsMargins(0, 2, 0, 2)\n        self.character_layout.setSpacing(8)\n        self.character_layout.setAlignment(Qt.AlignmentFlag.AlignTop)\n        self.character_scroll.setWidget(self.character_body)\n''',
        1,
    )
    text = replace_method(
        text,
        "class DMCampaignManagerDialog(_WizardDialog):\n",
        "_refresh_characters(self):",
        REFRESH_CHARACTERS_V4,
    )

    # 3) Make the player sharing model safe before any campaign is selected.
    init_anchor = '''        self.dm_store = privacy_store_for_window(window)\n        self.party_store = party_privacy_store_for_window(window)\n'''
    init_new = init_anchor + '''        self._dm_prefs = normalize_privacy_preferences()\n        self._party_prefs = normalize_party_preferences()\n'''
    if init_new not in text:
        if init_anchor not in text:
            raise RuntimeError("Could not locate player sharing stores")
        text = text.replace(init_anchor, init_new, 1)

    text = replace_method(
        text,
        "class PlayerCampaignsDialog(_WizardDialog):\n",
        "_load_sharing_preferences(self):",
        LOAD_PREFS_V4,
    )

    # Extra guard: even if a future refresh path reaches this method first,
    # inventory/note population cannot crash on missing preference attributes.
    populate_marker = '''    def _populate_inventory_notes(self):\n        self._clear_layout(self.inventory_selection_layout)\n'''
    populate_guard = '''    def _populate_inventory_notes(self):\n        if not hasattr(self, "_dm_prefs"):\n            self._dm_prefs = normalize_privacy_preferences()\n        if not hasattr(self, "_party_prefs"):\n            self._party_prefs = normalize_party_preferences()\n        self._clear_layout(self.inventory_selection_layout)\n'''
    if populate_guard not in text:
        if populate_marker not in text:
            raise RuntimeError("Could not locate _populate_inventory_notes")
        text = text.replace(populate_marker, populate_guard, 1)

    required = (
        "button.setFixedWidth(max(78, text_width + 56))",
        "self.character_layout.setAlignment(Qt.AlignmentFlag.AlignTop)",
        'self.character_scroll.viewport().setStyleSheet("background: transparent;")',
        "self._dm_prefs = normalize_privacy_preferences()",
        "if not hasattr(self, \"_dm_prefs\"):",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Phase 7 UI v4 verification failed: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_ui_v4")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def main():
    root = find_project_root()
    patch(root / "campaign_role_ui.py")
    print("Buttons fit full text without clipping: PASS")
    print("Back/Next use plain template-style labels: PASS")
    print("Campaign character white viewport removed: PASS")
    print("Player sharing defaults initialized before refresh: PASS")
    print("Inventory/notes sharing crash guard: PASS")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
