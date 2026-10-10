from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


NEW_RULES_HTML = r'''def _rules_html(campaign: dict) -> str:
    template = campaign_template(campaign)
    rules = template.rules

    improvement_mode = {
        "all": "All normal Improvements",
        "allow_only": "Only selected Improvements",
        "ban": "All except selected Improvements",
    }.get(rules.improvement_mode, rules.improvement_mode)

    arrays = ", ".join(rules.allowed_ability_array_ids) or "All normal arrays"
    hearts = rules.starting_hearts if rules.starting_hearts is not None else "Normal default"
    at = rules.starting_at if rules.starting_at is not None else "Normal default"

    rows = [
        ("Starting level", str(int(rules.level))),
        ("Extra starting IP", str(int(rules.extra_ip))),
        ("Starting Hearts", str(hearts)),
        ("Starting AT", str(at)),
        ("Species", str(rules.species_mode)),
        ("Free Heightened", str(int(getattr(rules, "free_heightened_ability_slots", 2)))),
        ("Ability arrays", arrays),
        ("Improvement rules", improvement_mode),
        ("Custom Improvements", "Allowed" if rules.allow_custom_improvements else "Disabled"),
    ]

    row_html = "".join(
        "<tr>"
        f"<td style='padding:4px 26px 4px 0; color:#6d4d1b; font-weight:700; white-space:nowrap;'>{html.escape(label)}</td>"
        f"<td style='padding:4px 0; color:#25190f;'>{html.escape(value)}</td>"
        "</tr>"
        for label, value in rows
    )

    extra = ""
    if template.description:
        extra += (
            "<div style='margin-top:14px; padding-top:11px; border-top:1px solid #e5c98f;'>"
            f"{html.escape(template.description)}"
            "</div>"
        )
    if template.player_instructions:
        extra += (
            "<div style='margin-top:12px;'>"
            "<b style='color:#6d4d1b;'>Instructions for Players</b><br>"
            f"{html.escape(template.player_instructions)}"
            "</div>"
        )

    return (
        "<div style='font-family:Georgia; color:#25190f; font-size:12px;'>"
        f"<div style='font-size:17px; font-weight:700; margin-bottom:7px;'>{html.escape(template.name)}</div>"
        f"<table cellspacing='0' cellpadding='0'>{row_html}</table>"
        f"{extra}"
        "</div>"
    )


'''


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
        self.resize(980, 760)
        self.setMinimumSize(900, 680)

        template_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f5efe1;
        }
        QLabel#PageTitle {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 27px;
            font-weight: 900;
        }
        QLabel#PageSubtitle {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
        }
        QLabel#SectionTitle {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 21px;
            font-weight: 900;
        }
        QLabel#SectionText {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
        }
        QLabel#CharacterName {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 17px;
            font-weight: 900;
        }
        QLabel#CharacterDetails,
        QLabel#PrivacySummary {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 11px;
        }
        QLabel#SyncStatus {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
        }
        QLabel#CampaignMeta {
            background: transparent;
            border: none;
            color: #6d4d1b;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
        }
        QFrame#CampaignStrip {
            background-color: #fffaf0;
            border: 1px solid #d4aa55;
            border-radius: 17px;
        }
        QFrame#CharacterField,
        QFrame#SharingField {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 10px;
        }
        QComboBox {
            min-height: 34px;
            background-color: #fffaf0;
            border: 1px solid #d2a650;
            border-radius: 8px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 4px 9px;
        }
        QComboBox:hover,
        QComboBox:focus {
            border-color: #b98525;
        }
        QTextEdit#RulesView {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 10px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 10px 13px;
        }
        QPushButton {
            min-height: 34px;
            background-color: #fffaf0;
            border: 1px solid #c99836;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
            padding: 5px 13px;
        }
        QPushButton:hover {
            background-color: #fff5df;
            border-color: #ad7820;
        }
        QPushButton#PrimaryButton {
            background-color: #dcecf3;
            border: 1px solid #3d819d;
            color: #25190f;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #cde5ef;
        }
        QPushButton#DangerButton {
            color: #8b3932;
            border-color: #cba79d;
        }
        QPushButton#DangerButton:hover {
            background-color: #fff1ed;
        }
        QCheckBox {
            color: #4b3826;
            font-family: Georgia;
            font-size: 11px;
            spacing: 6px;
        }
        """
        set_themed_stylesheet(self, template_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        # --------------------------------------------------------------
        # Page header — deliberately mirrors Character Creation Template.
        # --------------------------------------------------------------
        title = QLabel("Campaign")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Manage the selected campaign, its characters, creation rules, and live play."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(subtitle)

        # Campaign selector strip --------------------------------------
        campaign_strip = QFrame()
        campaign_strip.setObjectName("CampaignStrip")
        strip_layout = QVBoxLayout(campaign_strip)
        strip_layout.setContentsMargins(12, 8, 12, 8)
        strip_layout.setSpacing(5)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        selector_row.addWidget(self.campaign_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        self.refresh_btn.setFixedWidth(92)
        selector_row.addWidget(self.refresh_btn)
        strip_layout.addLayout(selector_row)

        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("CampaignMeta")
        self.meta_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        strip_layout.addWidget(self.meta_label)
        root.addWidget(campaign_strip)

        # --------------------------------------------------------------
        # Current Character section
        # --------------------------------------------------------------
        character_title = QLabel("Current Character")
        character_title.setObjectName("SectionTitle")
        root.addWidget(character_title)

        character_text = QLabel(
            "Create a new character with this campaign's rules, or connect the character already open on your sheet."
        )
        character_text.setObjectName("SectionText")
        character_text.setWordWrap(True)
        root.addWidget(character_text)

        character_field = QFrame()
        character_field.setObjectName("CharacterField")
        character_field_layout = QHBoxLayout(character_field)
        character_field_layout.setContentsMargins(14, 10, 14, 10)
        character_field_layout.setSpacing(12)

        character_identity = QVBoxLayout()
        character_identity.setSpacing(1)
        self.character_name_label = QLabel("")
        self.character_name_label.setObjectName("CharacterName")
        self.character_name_label.setWordWrap(True)
        self.character_hint_label = QLabel("")
        self.character_hint_label.setObjectName("CharacterDetails")
        self.character_hint_label.setWordWrap(True)
        character_identity.addWidget(self.character_name_label)
        character_identity.addWidget(self.character_hint_label)
        character_field_layout.addLayout(character_identity, 1)

        self.sync_label = QLabel("")
        self.sync_label.setObjectName("SyncStatus")
        self.sync_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        character_field_layout.addWidget(self.sync_label)
        root.addWidget(character_field)

        character_actions = QHBoxLayout()
        character_actions.setSpacing(8)
        self.create_character_btn = QPushButton("Create New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Share Current Character")
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        character_actions.addWidget(self.create_character_btn)
        character_actions.addWidget(self.share_btn)
        character_actions.addStretch()
        character_actions.addWidget(self.unlink_btn)
        root.addLayout(character_actions)

        # Sharing stays hidden until this character is actually linked.
        self.privacy_pane = QFrame()
        self.privacy_pane.setObjectName("SharingField")
        self.privacy_pane.setVisible(False)
        privacy_layout = QVBoxLayout(self.privacy_pane)
        privacy_layout.setContentsMargins(13, 9, 13, 9)
        privacy_layout.setSpacing(6)

        privacy_top = QHBoxLayout()
        privacy_heading = QLabel("Sharing")
        privacy_heading.setObjectName("SectionText")
        privacy_top.addWidget(privacy_heading)
        privacy_top.addStretch()
        self.privacy_btn = QPushButton("Sharing & Privacy")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        privacy_top.addWidget(self.privacy_btn)
        privacy_layout.addLayout(privacy_top)

        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("PrivacySummary")
        self.privacy_summary_label.setWordWrap(True)
        privacy_layout.addWidget(self.privacy_summary_label)

        self.roll_share_checkbox = QCheckBox(
            "Share my dice rolls during active sessions"
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
        root.addWidget(self.privacy_pane)

        # --------------------------------------------------------------
        # Creation Rules section
        # --------------------------------------------------------------
        rules_heading_row = QHBoxLayout()
        rules_heading_box = QVBoxLayout()
        rules_heading_box.setSpacing(1)
        rules_title = QLabel("Creation Rules")
        rules_title.setObjectName("SectionTitle")
        rules_text = QLabel(
            "These rules are applied automatically when a new campaign character is created."
        )
        rules_text.setObjectName("SectionText")
        rules_text.setWordWrap(True)
        rules_heading_box.addWidget(rules_title)
        rules_heading_box.addWidget(rules_text)
        rules_heading_row.addLayout(rules_heading_box, 1)

        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        rules_heading_row.addWidget(self.edit_rules_btn)
        root.addLayout(rules_heading_row)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        self.rules_view.setMinimumHeight(185)
        self.rules_view.setMaximumHeight(215)
        root.addWidget(self.rules_view)

        root.addStretch()

        # --------------------------------------------------------------
        # Bottom actions — same visual rhythm as the template wizard.
        # --------------------------------------------------------------
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self.create_btn = QPushButton("New Campaign")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn = QPushButton("Join Campaign")
        self.join_btn.clicked.connect(self.join_campaign)
        bottom.addWidget(self.create_btn)
        bottom.addWidget(self.join_btn)
        bottom.addStretch()

        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        bottom.addWidget(self.dashboard_btn)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)

        for button in (
            self.refresh_btn,
            self.create_btn,
            self.join_btn,
            self.dashboard_btn,
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
                "Character currently open on your sheet"
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
    if 'title = QLabel("Campaign")' in current and 'Bottom actions — same visual rhythm as the template wizard.' in current:
        return text, False
    return text[:start] + NEW_INIT + text[end:], True


def replace_rules_html(text):
    start_marker = "def _rules_html(campaign: dict) -> str:\n"
    end_marker = "def _replace_current_character(window, template: CharacterTemplate) -> bool:\n"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the Creation Rules formatter.")
    current = text[start:end]
    if "Improvement rules" in current and "Instructions for Players" in current:
        return text, False
    return text[:start] + NEW_RULES_HTML + text[end:], True


def replace_refresh_sync(text):
    start_marker = "    def _refresh_sync_label(self):\n"
    end_marker = "    def reload_campaigns(self):\n"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate _refresh_sync_label.")
    current = text[start:end]
    if "self.character_name_label.setText" in current and 'self.sync_label.setText(f"Sync: {status}")' in current:
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

    needle = (
        '        button = getattr(self, "privacy_btn", None)\n'
        '        label = getattr(self, "privacy_summary_label", None)\n'
    )
    if needle not in block:
        raise RuntimeError("The privacy-control method has an unexpected shape.")
    block = block.replace(
        needle,
        needle + '        privacy_pane = getattr(self, "privacy_pane", None)\n',
        1,
    )

    visible_line = (
        "        visible = isinstance(link, dict) and isinstance(self.current_campaign, dict)\n"
    )
    if visible_line not in block:
        raise RuntimeError("Could not add privacy-pane visibility handling.")
    block = block.replace(
        visible_line,
        visible_line
        + "        if privacy_pane is not None:\n"
        + "            privacy_pane.setVisible(visible)\n",
        1,
    )

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

    text, rules_changed = replace_rules_html(text)
    text, constructor_changed = replace_constructor(text)
    text, sync_changed = replace_refresh_sync(text)
    text, privacy_changed = patch_privacy_visibility(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_redesign_v5")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign template-style redesign: PASS" if constructor_changed else "Campaign template-style redesign: already installed")
    print("Creation Rules formatting: PASS" if rules_changed else "Creation Rules formatting: already installed")
    print("Character status refresh: PASS" if sync_changed else "Character status refresh: already installed")
    print("Sharing visibility: PASS" if privacy_changed else "Sharing visibility: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
