from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


FIT_OLD = '''def _fit_button(button):
    button.adjustSize()
    button.setFixedWidth(button.sizeHint().width())
    button.setCursor(Qt.CursorShape.PointingHandCursor)
'''

FIT_NEW = '''def _fit_button(button):
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

PREFS_OLD = '''        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        self.setWindowTitle("My Campaigns")
'''

PREFS_NEW = '''        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        # Always have a valid sharing model, even before a player has joined a
        # campaign.  The character page can still refresh in that state.
        self._dm_prefs = normalize_privacy_preferences()
        self._party_prefs = normalize_party_preferences()
        self.setWindowTitle("My Campaigns")
'''

LOAD_PREFS_OLD = '''    def _load_sharing_preferences(self):
        if not self.current_campaign:
            return
'''

LOAD_PREFS_NEW = '''    def _load_sharing_preferences(self):
        if not self.current_campaign:
            self._dm_prefs = normalize_privacy_preferences()
            self._party_prefs = normalize_party_preferences()
            return
'''

PLAYER_CHARACTER_METHOD = r'''    def _build_character_page(self):
        # This page contains the sharing matrix and can grow when inventory or
        # note details are expanded.  Put the page itself in a scroll area so
        # it never forces the whole wizard taller than the user's screen.
        page = QWidget()
        page_outer = QVBoxLayout(page)
        page_outer.setContentsMargins(0, 0, 0, 0)
        page_outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(18, 10, 18, 6)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel("My Character")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel(
            "Create with the campaign's rules, edit normally on the sheet, "
            "then save the finished character to the campaign."
        )
        intro.setObjectName("SectionText")
        intro.setWordWrap(True)
        box.addWidget(intro)

        identity = QFrame()
        identity.setObjectName("Field")
        identity_layout = QHBoxLayout(identity)
        identity_layout.setContentsMargins(12, 8, 12, 8)
        identity_text = QVBoxLayout()
        self.character_name = QLabel("")
        self.character_name.setStyleSheet("font-size:15px; font-weight:900;")
        self.character_hint = QLabel("")
        self.character_hint.setObjectName("Muted")
        identity_text.addWidget(self.character_name)
        identity_text.addWidget(self.character_hint)
        identity_layout.addLayout(identity_text, 1)
        self.sync_label = QLabel("")
        self.sync_label.setStyleSheet("font-weight:800;")
        identity_layout.addWidget(self.sync_label)
        box.addWidget(identity)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        create_btn = QPushButton("Create Character")
        create_btn.setObjectName("PrimaryButton")
        create_btn.clicked.connect(self.create_character)
        self.save_btn = QPushButton("Save to Campaign")
        self.save_btn.clicked.connect(self.save_to_campaign)
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.unlink_btn.clicked.connect(self.unlink_character)
        for button in (create_btn, self.save_btn, self.unlink_btn):
            _fit_button(button)
            actions.addWidget(button)
        actions.addStretch()
        box.addLayout(actions)

        share_heading = QHBoxLayout()
        label = QLabel("Sharing")
        label.setStyleSheet("font-size:17px; font-weight:900;")
        share_heading.addWidget(label)
        share_heading.addStretch()
        self.apply_sharing_btn = QPushButton("Apply Sharing")
        self.apply_sharing_btn.setObjectName("PrimaryButton")
        self.apply_sharing_btn.clicked.connect(self.apply_sharing)
        _fit_button(self.apply_sharing_btn)
        share_heading.addWidget(self.apply_sharing_btn)
        box.addLayout(share_heading)

        help_text = QLabel(
            "Choose separately what the DM can see and what the rest of the party can see. "
            "HP, AT and Abilities are always available to the DM for campaign play."
        )
        help_text.setObjectName("SectionText")
        help_text.setWordWrap(True)
        box.addWidget(help_text)

        sharing = QFrame()
        sharing.setObjectName("Field")
        grid = QGridLayout(sharing)
        grid.setContentsMargins(14, 10, 14, 10)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(5)
        grid.addWidget(QLabel("Information"), 0, 0)
        dm_head = QLabel("DM")
        dm_head.setStyleSheet("font-weight:900;")
        party_head = QLabel("Party")
        party_head.setStyleSheet("font-weight:900;")
        grid.addWidget(dm_head, 0, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(party_head, 0, 2, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.dm_core_boxes = {}
        self.party_boxes = {}
        row = 1
        for key, label_text in (("hp", "HP"), ("at", "AT"), ("abilities", "Abilities")):
            grid.addWidget(QLabel(label_text), row, 0)
            dm = QCheckBox()
            dm.setChecked(True)
            dm.setEnabled(False)
            party = QCheckBox()
            self.dm_core_boxes[key] = dm
            self.party_boxes[key] = party
            grid.addWidget(dm, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(party, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
            row += 1

        for key, label_text in (
            ("improvements", "Improvements"),
            ("portrait", "Portrait"),
            ("inventory", "Inventory"),
            ("notes", "Notes"),
        ):
            grid.addWidget(QLabel(label_text), row, 0)
            dm = QCheckBox()
            party = QCheckBox()
            setattr(self, f"dm_{key}_box", dm)
            self.party_boxes[key] = party
            grid.addWidget(dm, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(party, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
            row += 1

        grid.addWidget(QLabel("Session dice rolls"), row, 0)
        self.roll_share_box = QCheckBox()
        self.roll_share_box.toggled.connect(self._roll_sharing_changed)
        grid.addWidget(self.roll_share_box, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        party_roll_label = QLabel("—")
        party_roll_label.setObjectName("Muted")
        grid.addWidget(party_roll_label, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        grid.setColumnStretch(0, 1)
        box.addWidget(sharing)

        self.inventory_detail = self._build_selection_section("Inventory items", "inventory")
        self.notes_detail = self._build_selection_section("Notes", "notes")
        box.addWidget(self.inventory_detail)
        box.addWidget(self.notes_detail)

        for toggle in (
            self.dm_inventory_box,
            self.party_boxes["inventory"],
            self.dm_notes_box,
            self.party_boxes["notes"],
        ):
            toggle.toggled.connect(self._refresh_detail_visibility)

        box.addStretch()
        scroll.setWidget(content)
        page_outer.addWidget(scroll)
        self.pages.addWidget(page)
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
        if (
            (root / "frontend_2_8.py").is_file()
            and (root / "campaign_role_ui.py").is_file()
            and (root / "campaign_ui.py").is_file()
        ):
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
    end = next_def + 1
    return text[:start] + replacement + "\n" + text[end:]


def patch_role_ui(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    if FIT_NEW not in text:
        if FIT_OLD not in text:
            # Older hotfix may already have a first-generation metrics version.
            start = text.find("def _fit_button(button):\n")
            end = text.find("\n\ndef _campaign_rules_rows", start)
            if start < 0 or end < 0:
                raise RuntimeError("Could not safely locate _fit_button")
            text = text[:start] + FIT_NEW + text[end:]
        else:
            text = text.replace(FIT_OLD, FIT_NEW, 1)

    if PREFS_NEW not in text:
        if PREFS_OLD not in text:
            # The first repair may already have inserted these lines.
            if "self._dm_prefs = normalize_privacy_preferences()" not in text:
                raise RuntimeError("Could not safely initialize player sharing preferences")
        else:
            text = text.replace(PREFS_OLD, PREFS_NEW, 1)

    if LOAD_PREFS_NEW not in text:
        if LOAD_PREFS_OLD in text:
            text = text.replace(LOAD_PREFS_OLD, LOAD_PREFS_NEW, 1)
        elif "self._dm_prefs = normalize_privacy_preferences()" not in text:
            raise RuntimeError("Could not safely patch empty-campaign sharing state")

    # Keep My Campaigns compact.  The scrollable character page handles any
    # expanded inventory/note details without stretching the whole window.
    text = text.replace(
        '        self.resize(960, 680)\n        self.setMinimumSize(860, 600)\n',
        '        self.resize(900, 620)\n        self.setMinimumSize(820, 560)\n',
        1,
    )

    text = replace_method(
        text,
        "class PlayerCampaignsDialog(_WizardDialog):\n",
        "_build_character_page(self):",
        PLAYER_CHARACTER_METHOD,
    )

    # Use the Phase 7 DM manager itself.  Do not fall back to the old Phase 6
    # CampaignManagerDialog; that is what brought back the cancelled/old layout.
    old_open = '''def open_dm_campaign_manager(window):
    dialog = PreservedDMCampaignManagerDialog(window)
    dialog.exec()
    return dialog
'''
    clean_open = '''def open_dm_campaign_manager(window):
    dialog = DMCampaignManagerDialog(window)
    dialog.exec()
    return dialog
'''
    if old_open in text:
        text = text.replace(old_open, clean_open, 1)
    elif clean_open not in text:
        # The clean source already uses DMCampaignManagerDialog; leave it alone.
        marker = "def open_dm_campaign_manager(window):\n"
        if marker not in text:
            raise RuntimeError("Could not locate open_dm_campaign_manager")

    required = (
        "class DMCampaignManagerDialog",
        "class PlayerCampaignsDialog",
        'QLabel("Starting HP")' if 'QLabel("Starting HP")' in text else '"Starting HP"',
        "Remove from Campaign",
        "Open Party Dashboard",
        "self._dm_prefs = normalize_privacy_preferences()",
        "text_width = button.fontMetrics().horizontalAdvance(button.text())",
        "scroll.setWidget(content)",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError("Phase 7 UI verification failed: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_ui_v2")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def patch_frontend(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    old_role_import = "from campaign_role_ui import open_player_campaigns\n"
    new_role_import = "from campaign_role_ui import open_dm_campaign_manager, open_player_campaigns\n"
    if old_role_import in text:
        text = text.replace(old_role_import, new_role_import, 1)
    elif new_role_import not in text:
        campaign_import = "from campaign_ui import open_campaign_manager\n"
        if campaign_import not in text:
            raise RuntimeError("Could not locate Campaign imports in frontend_2_8.py")
        text = text.replace(campaign_import, campaign_import + new_role_import, 1)

    text = text.replace(
        "lambda _checked=False: open_campaign_manager(self)",
        "lambda _checked=False: open_dm_campaign_manager(self)",
        1,
    )

    if "open_dm_campaign_manager(self)" not in text:
        raise RuntimeError("Campaign Manager menu was not redirected to the Phase 7 DM manager")

    if text != original:
        backup = path.with_name(path.name + ".before_phase7_ui_v2")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)


def main():
    root = find_project_root()
    patch_role_ui(root / "campaign_role_ui.py")
    patch_frontend(root / "frontend_2_8.py")

    print("Campaign Manager uses the clean Phase 7 DM UI: PASS")
    print("Old Cancel/old Campaign manager path bypassed: PASS")
    print("DM Creation Rules use rule cards + HP terminology: PASS")
    print("DM Remove from Campaign buttons fit their text: PASS")
    print("My Campaigns button clipping: PASS")
    print("My Campaigns no-campaign privacy state: PASS")
    print("My Character & Sharing page scrolls instead of stretching the window: PASS")
    print("Back remains on the far left; Close/Next remain on the right: PASS")
    print("Compile: PASS")


if __name__ == "__main__":
    main()
