from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


NEW_INIT = r'''    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.session_service = CampaignSessionService(self.client) if self.client else None
        self.privacy_store = privacy_store_for_window(window)
        self.campaigns: list[dict] = []
        self.current_campaign: dict | None = None

        self.setWindowTitle("Campaign")
        self.resize(980, 590)
        self.setMinimumSize(900, 540)

        workspace_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f3efe7;
        }
        QLabel#WindowTitle {
            color: #201a14;
            font-family: Georgia;
            font-size: 25px;
            font-weight: 900;
        }
        QLabel#WindowSubtitle,
        QLabel#Muted,
        QLabel#CardHint {
            color: #776b5c;
            font-family: Georgia;
            font-size: 11px;
        }
        QLabel#CardTitle {
            color: #201a14;
            font-family: Georgia;
            font-size: 18px;
            font-weight: 900;
        }
        QLabel#CharacterName {
            color: #201a14;
            font-family: Georgia;
            font-size: 20px;
            font-weight: 900;
        }
        QLabel#Meta {
            color: #665846;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 700;
        }
        QLabel#StatusPill {
            background-color: #eef6f8;
            border: 1px solid #b8d5de;
            border-radius: 10px;
            color: #285c6e;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
            padding: 5px 9px;
        }
        QFrame#Toolbar,
        QFrame#ContentCard,
        QFrame#PrivacyPane {
            background-color: #fffdf9;
            border: 1px solid #ded4c2;
            border-radius: 12px;
        }
        QFrame#AccentLine {
            background-color: #2f718c;
            border: none;
            min-height: 3px;
            max-height: 3px;
            border-radius: 1px;
        }
        QComboBox {
            min-height: 32px;
            background-color: #ffffff;
            border: 1px solid #cfc5b4;
            border-radius: 8px;
            padding: 3px 9px;
            color: #201a14;
            font-family: Georgia;
            font-size: 12px;
        }
        QComboBox:hover,
        QComboBox:focus {
            border-color: #8eb9c7;
        }
        QPushButton {
            min-height: 31px;
            padding: 4px 12px;
            border-radius: 8px;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
        }
        QPushButton#PrimaryButton {
            background-color: #2f718c;
            color: #ffffff;
            border: 1px solid #285f75;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #3c839d;
        }
        QPushButton#SecondaryButton {
            background-color: #ffffff;
            color: #3a3026;
            border: 1px solid #cfc5b4;
        }
        QPushButton#SecondaryButton:hover {
            background-color: #f8f4ec;
            border-color: #b8aa93;
        }
        QPushButton#DashboardButton {
            background-color: #263d49;
            color: #ffffff;
            border: 1px solid #1d313a;
        }
        QPushButton#DashboardButton:hover {
            background-color: #34515f;
        }
        QPushButton#TextButton {
            background-color: transparent;
            color: #55707a;
            border: none;
            padding-left: 5px;
            padding-right: 5px;
        }
        QPushButton#TextButton:hover {
            color: #2f718c;
            text-decoration: underline;
        }
        QPushButton#DangerButton {
            background-color: transparent;
            color: #984b43;
            border: 1px solid #d7bcb7;
        }
        QPushButton#DangerButton:hover {
            background-color: #fff4f2;
        }
        QTextEdit#RulesView {
            background-color: transparent;
            border: none;
            color: #201a14;
            font-family: Georgia;
            font-size: 12px;
            padding: 0px;
        }
        QCheckBox {
            color: #4f4438;
            font-family: Georgia;
            font-size: 11px;
            spacing: 6px;
        }
        """
        set_themed_stylesheet(self, workspace_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(11)

        # Header -----------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("Campaign")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Characters, creation rules and live play")
        subtitle.setObjectName("WindowSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.dashboard_btn = QPushButton("DM Dashboard")
        self.dashboard_btn.setObjectName("DashboardButton")
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        header.addWidget(self.dashboard_btn)
        root.addLayout(header)

        # Campaign toolbar -------------------------------------------------
        toolbar = QFrame()
        toolbar.setObjectName("Toolbar")
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 10, 12, 9)
        toolbar_layout.setSpacing(6)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(7)
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        selector_row.addWidget(self.campaign_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("SecondaryButton")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        selector_row.addWidget(self.refresh_btn)

        self.create_btn = QPushButton("New Campaign")
        self.create_btn.setObjectName("SecondaryButton")
        self.create_btn.clicked.connect(self.create_campaign)
        selector_row.addWidget(self.create_btn)

        self.join_btn = QPushButton("Join")
        self.join_btn.setObjectName("SecondaryButton")
        self.join_btn.clicked.connect(self.join_campaign)
        selector_row.addWidget(self.join_btn)
        toolbar_layout.addLayout(selector_row)

        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("Meta")
        self.meta_label.setWordWrap(False)
        toolbar_layout.addWidget(self.meta_label)
        root.addWidget(toolbar)

        # Main workspace ---------------------------------------------------
        content = QHBoxLayout()
        content.setSpacing(12)

        # Character card
        character_card = QFrame()
        character_card.setObjectName("ContentCard")
        character_card.setMinimumWidth(365)
        character_card.setMaximumWidth(430)
        character_layout = QVBoxLayout(character_card)
        character_layout.setContentsMargins(18, 16, 18, 16)
        character_layout.setSpacing(10)

        character_heading = QLabel("Current Character")
        character_heading.setObjectName("CardTitle")
        character_layout.addWidget(character_heading)

        self.character_name_label = QLabel("")
        self.character_name_label.setObjectName("CharacterName")
        self.character_name_label.setWordWrap(True)
        character_layout.addWidget(self.character_name_label)

        self.character_hint_label = QLabel("")
        self.character_hint_label.setObjectName("CardHint")
        self.character_hint_label.setWordWrap(True)
        character_layout.addWidget(self.character_hint_label)

        accent = QFrame()
        accent.setObjectName("AccentLine")
        character_layout.addWidget(accent)

        self.sync_label = QLabel("")
        self.sync_label.setObjectName("StatusPill")
        character_layout.addWidget(self.sync_label)

        character_layout.addSpacing(4)

        self.create_character_btn = QPushButton("Create New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        character_layout.addWidget(self.create_character_btn)

        self.share_btn = QPushButton("Share Current Character")
        self.share_btn.setObjectName("SecondaryButton")
        self.share_btn.clicked.connect(self.share_current_character)
        character_layout.addWidget(self.share_btn)

        self.unlink_btn = QPushButton("Unlink from Campaign")
        self.unlink_btn.setObjectName("DangerButton")
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        character_layout.addWidget(self.unlink_btn)

        self.privacy_pane = QFrame()
        self.privacy_pane.setObjectName("PrivacyPane")
        self.privacy_pane.setVisible(False)
        privacy_layout = QVBoxLayout(self.privacy_pane)
        privacy_layout.setContentsMargins(11, 9, 11, 9)
        privacy_layout.setSpacing(6)

        privacy_top = QHBoxLayout()
        sharing_label = QLabel("Sharing")
        sharing_label.setObjectName("Meta")
        privacy_top.addWidget(sharing_label)
        privacy_top.addStretch()
        self.privacy_btn = QPushButton("Edit")
        self.privacy_btn.setObjectName("TextButton")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        privacy_top.addWidget(self.privacy_btn)
        privacy_layout.addLayout(privacy_top)

        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("Muted")
        self.privacy_summary_label.setWordWrap(True)
        privacy_layout.addWidget(self.privacy_summary_label)

        self.roll_share_checkbox = QCheckBox(
            "Share dice rolls during active sessions"
        )
        self.roll_share_checkbox.setToolTip(
            "When off, rolls made while a campaign session is active are not "
            "stored in the DM session log. Rolls outside sessions are unchanged."
        )
        self.roll_share_checkbox.setVisible(False)
        self.roll_share_checkbox.toggled.connect(
            self._session_roll_sharing_changed
        )
        privacy_layout.addWidget(self.roll_share_checkbox)
        character_layout.addWidget(self.privacy_pane)
        character_layout.addStretch()
        content.addWidget(character_card)

        # Rules card
        rules_card = QFrame()
        rules_card.setObjectName("ContentCard")
        rules_layout = QVBoxLayout(rules_card)
        rules_layout.setContentsMargins(18, 16, 18, 16)
        rules_layout.setSpacing(9)

        rules_header = QHBoxLayout()
        rules_title_box = QVBoxLayout()
        rules_title_box.setSpacing(0)
        rules_title = QLabel("Creation Rules")
        rules_title.setObjectName("CardTitle")
        rules_hint = QLabel("Used automatically for every new campaign character")
        rules_hint.setObjectName("CardHint")
        rules_title_box.addWidget(rules_title)
        rules_title_box.addWidget(rules_hint)
        rules_header.addLayout(rules_title_box, 1)

        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.setObjectName("SecondaryButton")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        rules_header.addWidget(self.edit_rules_btn)
        rules_layout.addLayout(rules_header)

        rules_accent = QFrame()
        rules_accent.setObjectName("AccentLine")
        rules_layout.addWidget(rules_accent)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        rules_layout.addWidget(self.rules_view, 1)
        content.addWidget(rules_card, 1)

        root.addLayout(content, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close = QPushButton("Close")
        close.setObjectName("SecondaryButton")
        close.setFixedWidth(84)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)

        for button in (
            self.dashboard_btn,
            self.refresh_btn,
            self.create_btn,
            self.join_btn,
            self.create_character_btn,
            self.share_btn,
            self.unlink_btn,
            self.privacy_btn,
            self.edit_rules_btn,
            close,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(700)
        self.status_timer.timeout.connect(self._refresh_sync_label)
        self.status_timer.start()

        self.reload_campaigns()

'''

NEW_REFRESH_SYNC = r'''    def _refresh_sync_label(self):
        status = campaign_sync_status(self.window)
        self.sync_label.setText(f"Sync: {status}")

        character = getattr(self.window, "character", None)
        name = str(getattr(character, "name", "") or "").strip()
        species = str(getattr(character, "species_name", "") or "").strip()
        level = getattr(getattr(character, "progression", None), "level", None)

        if name:
            self.character_name_label.setText(name)
            details = []
            if species:
                details.append(species)
            if level is not None:
                details.append(f"Level {level}")
            self.character_hint_label.setText(
                " • ".join(details) if details else "Character currently open on your sheet"
            )
        else:
            self.character_name_label.setText("Unnamed Character")
            self.character_hint_label.setText(
                "Create a new character from the campaign rules, or share the character currently open."
            )

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
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 6 DID project. Put this script in the "
        "phase6 folder inside your current code folder and run it from there."
    )


def ensure_import(text, widget_name):
    token = f"    {widget_name},\n"
    if token in text:
        return text
    needle = "    QDialog,\n"
    if needle not in text:
        raise RuntimeError("Could not locate the PySide6 widget import block.")
    return text.replace(needle, needle + token, 1)


def replace_constructor(text):
    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    start = text.find("    def __init__(self, window):\n", class_pos)
    end = text.find("    def _show_error(self, title, error):\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the Campaign window constructor.")

    current = text[start:end]
    if 'self.character_name_label = QLabel("")' in current and 'Creation Rules' in current:
        return text, False
    return text[:start] + NEW_INIT + text[end:], True


def replace_refresh_sync(text):
    start_marker = "    def _refresh_sync_label(self):\n"
    end_marker = "    def reload_campaigns(self):\n"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate _refresh_sync_label.")

    current = text[start:end]
    if "self.character_name_label.setText" in current:
        return text, False
    return text[:start] + NEW_REFRESH_SYNC + text[end:], True


def patch_privacy_visibility(text):
    marker = "    def _refresh_privacy_controls(self):\n"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("Could not find _refresh_privacy_controls.")
    end = text.find("    def open_sharing_privacy(self):\n", start)
    if end < 0:
        raise RuntimeError("Could not safely locate the privacy-control method.")

    block = text[start:end]
    if "privacy_pane.setVisible(visible)" in block:
        return text, False

    needle = "        button = getattr(self, \"privacy_btn\", None)\n        label = getattr(self, \"privacy_summary_label\", None)\n"
    replacement = (
        needle
        + "        privacy_pane = getattr(self, \"privacy_pane\", None)\n"
    )
    if needle not in block:
        raise RuntimeError("The privacy-control method has an unexpected shape.")
    block = block.replace(needle, replacement, 1)

    needle2 = "        visible = isinstance(link, dict) and isinstance(self.current_campaign, dict)\n"
    replacement2 = (
        needle2
        + "        if privacy_pane is not None:\n"
        + "            privacy_pane.setVisible(visible)\n"
    )
    if needle2 not in block:
        raise RuntimeError("Could not add privacy pane visibility handling.")
    block = block.replace(needle2, replacement2, 1)

    return text[:start] + block + text[end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original
    text = ensure_import(text, "QFrame")

    required = (
        "CampaignSessionService",
        "privacy_store_for_window",
        "open_sharing_privacy",
        "open_dm_dashboard",
        "Campaign-created characters are normal local characters too",
    )
    missing = [marker for marker in required if marker not in text]
    if missing:
        raise RuntimeError(
            "The previous Phase 6 fixes are not fully installed yet. Missing: "
            + ", ".join(missing)
        )

    text, constructor_changed = replace_constructor(text)
    text, sync_changed = replace_refresh_sync(text)
    text, privacy_changed = patch_privacy_visibility(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_redesign_v4")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign redesign v4: PASS" if constructor_changed else "Campaign redesign v4: already installed")
    print("Character status refresh: PASS" if sync_changed else "Character status refresh: already installed")
    print("Sharing pane visibility: PASS" if privacy_changed else "Sharing pane visibility: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
