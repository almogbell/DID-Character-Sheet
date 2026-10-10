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
        self._campaign_page_index = 0

        self.setWindowTitle("Campaign")
        self.resize(900, 650)
        self.setMinimumSize(840, 610)

        # Keep the Campaign manager in the same visual language as the ORIGINAL
        # CharacterTemplateDialog: parchment, Georgia, thin gold borders,
        # compact normal-size buttons, one label/value form per page.
        campaign_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f5efe1;
        }
        QLabel#PageTitle {
            color: #25190f;
            font-family: Georgia;
            font-size: 27px;
            font-weight: 900;
            background: transparent;
            border: none;
        }
        QLabel#PageSubtitle,
        QLabel#SectionText {
            color: #765d34;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
            background: transparent;
            border: none;
        }
        QLabel#StepBar {
            background-color: #fffaf0;
            border: 1px solid #d8ad58;
            border-radius: 10px;
            color: #76521e;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 800;
            padding: 5px 9px;
        }
        QLabel#SectionTitle {
            color: #25190f;
            font-family: Georgia;
            font-size: 21px;
            font-weight: 900;
            background: transparent;
            border: none;
        }
        QLabel#FieldLabel {
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            background: transparent;
            border: none;
        }
        QLabel#ReadField,
        QLabel#SyncStatus {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 8px 11px;
        }
        QLabel#CharacterName {
            color: #25190f;
            font-family: Georgia;
            font-size: 15px;
            font-weight: 900;
            background: transparent;
            border: none;
        }
        QLabel#Muted,
        QLabel#PrivacySummary {
            color: #765d34;
            font-family: Georgia;
            font-size: 11px;
            background: transparent;
            border: none;
        }
        QFrame#CharacterField,
        QFrame#SharingField {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 9px;
        }
        QComboBox {
            min-height: 32px;
            background-color: #fffaf0;
            border: 1px solid #d2a650;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 3px 9px;
        }
        QTextEdit#RulesView {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 8px 11px;
        }
        QPushButton {
            min-height: 31px;
            max-height: 38px;
            background-color: #fffaf0;
            border: 1px solid #c99836;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
            padding: 3px 11px;
        }
        QPushButton:hover {
            background-color: #fff5df;
            border-color: #ad7820;
        }
        QPushButton#PrimaryButton {
            background-color: #dcecf3;
            border: 1px solid #3d819d;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #cde5ef;
        }
        QPushButton#DangerButton {
            color: #8b3932;
            border-color: #cba79d;
        }
        QCheckBox {
            color: #25190f;
            font-family: Georgia;
            font-size: 11px;
            spacing: 6px;
        }
        """
        set_themed_stylesheet(self, campaign_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)

        title = QLabel("Campaign")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Manage the campaign, its characters, creation rules, and live play."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(subtitle)

        self.campaign_step_label = QLabel("")
        self.campaign_step_label.setObjectName("StepBar")
        self.campaign_step_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.campaign_step_label)

        self.campaign_pages = QStackedWidget()
        root.addWidget(self.campaign_pages, 1)

        # ==============================================================
        # PAGE 1 — CAMPAIGN
        # ============================================================== 
        campaign_page = QFrame()
        campaign_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page1 = QVBoxLayout(campaign_page)
        page1.setContentsMargins(18, 14, 18, 6)
        page1.setSpacing(7)

        heading = QLabel("Campaign")
        heading.setObjectName("SectionTitle")
        page1.addWidget(heading)

        intro = QLabel(
            "Choose the campaign you want to manage, create a new one, or join an existing campaign."
        )
        intro.setObjectName("SectionText")
        intro.setWordWrap(True)
        page1.addWidget(intro)
        page1.addSpacing(5)

        form1 = QGridLayout()
        form1.setContentsMargins(0, 0, 0, 0)
        form1.setHorizontalSpacing(16)
        form1.setVerticalSpacing(10)
        form1.setColumnMinimumWidth(0, 190)
        form1.setColumnStretch(1, 1)

        selected_label = QLabel("Selected Campaign")
        selected_label.setObjectName("FieldLabel")
        form1.addWidget(selected_label, 0, 0)

        selector = QHBoxLayout()
        selector.setSpacing(8)
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        selector.addWidget(self.campaign_combo, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(95)
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        selector.addWidget(self.refresh_btn)
        form1.addLayout(selector, 0, 1)

        details_label = QLabel("Campaign Details")
        details_label.setObjectName("FieldLabel")
        form1.addWidget(details_label, 1, 0)
        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("ReadField")
        self.meta_label.setWordWrap(True)
        form1.addWidget(self.meta_label, 1, 1)

        actions_label = QLabel("Campaign Actions")
        actions_label.setObjectName("FieldLabel")
        form1.addWidget(actions_label, 2, 0)
        action_box = QHBoxLayout()
        action_box.setSpacing(8)
        self.create_btn = QPushButton("New Campaign")
        self.create_btn.setFixedWidth(125)
        self.join_btn = QPushButton("Join Campaign")
        self.join_btn.setFixedWidth(125)
        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.dashboard_btn.setFixedWidth(165)
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        action_box.addWidget(self.create_btn)
        action_box.addWidget(self.join_btn)
        action_box.addWidget(self.dashboard_btn)
        action_box.addStretch()
        form1.addLayout(action_box, 2, 1)

        page1.addLayout(form1)
        page1.addStretch()
        self.campaign_pages.addWidget(campaign_page)

        # ==============================================================
        # PAGE 2 — CHARACTER
        # ============================================================== 
        character_page = QFrame()
        character_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page2 = QVBoxLayout(character_page)
        page2.setContentsMargins(18, 14, 18, 6)
        page2.setSpacing(7)

        character_title = QLabel("Current Character")
        character_title.setObjectName("SectionTitle")
        page2.addWidget(character_title)

        character_text = QLabel(
            "Create a new character with this campaign's rules, or connect the character already open on your sheet."
        )
        character_text.setObjectName("SectionText")
        character_text.setWordWrap(True)
        page2.addWidget(character_text)
        page2.addSpacing(5)

        form2 = QGridLayout()
        form2.setContentsMargins(0, 0, 0, 0)
        form2.setHorizontalSpacing(16)
        form2.setVerticalSpacing(10)
        form2.setColumnMinimumWidth(0, 190)
        form2.setColumnStretch(1, 1)

        character_label = QLabel("Character")
        character_label.setObjectName("FieldLabel")
        form2.addWidget(character_label, 0, 0)

        character_field = QFrame()
        character_field.setObjectName("CharacterField")
        identity = QVBoxLayout(character_field)
        identity.setContentsMargins(11, 7, 11, 7)
        identity.setSpacing(1)
        self.character_name_label = QLabel("")
        self.character_name_label.setObjectName("CharacterName")
        self.character_hint_label = QLabel("")
        self.character_hint_label.setObjectName("Muted")
        self.character_hint_label.setWordWrap(True)
        identity.addWidget(self.character_name_label)
        identity.addWidget(self.character_hint_label)
        form2.addWidget(character_field, 0, 1)

        sync_label = QLabel("Campaign Sync")
        sync_label.setObjectName("FieldLabel")
        form2.addWidget(sync_label, 1, 0)
        self.sync_label = QLabel("")
        self.sync_label.setObjectName("SyncStatus")
        form2.addWidget(self.sync_label, 1, 1)

        character_actions_label = QLabel("Character Actions")
        character_actions_label.setObjectName("FieldLabel")
        form2.addWidget(character_actions_label, 2, 0)
        character_actions = QHBoxLayout()
        character_actions.setSpacing(8)
        self.create_character_btn = QPushButton("Create New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.create_character_btn.setFixedWidth(165)
        self.share_btn = QPushButton("Share Current Character")
        self.share_btn.setFixedWidth(175)
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.unlink_btn.setFixedWidth(90)
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        character_actions.addWidget(self.create_character_btn)
        character_actions.addWidget(self.share_btn)
        character_actions.addWidget(self.unlink_btn)
        character_actions.addStretch()
        form2.addLayout(character_actions, 2, 1)

        self.privacy_pane = QFrame()
        self.privacy_pane.setObjectName("SharingField")
        self.privacy_pane.setVisible(False)
        sharing_grid = QGridLayout(self.privacy_pane)
        sharing_grid.setContentsMargins(0, 4, 0, 0)
        sharing_grid.setHorizontalSpacing(16)
        sharing_grid.setVerticalSpacing(7)
        sharing_grid.setColumnMinimumWidth(0, 190)
        sharing_grid.setColumnStretch(1, 1)

        sharing_label = QLabel("Sharing with the DM")
        sharing_label.setObjectName("FieldLabel")
        sharing_grid.addWidget(sharing_label, 0, 0)
        sharing_content = QHBoxLayout()
        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("PrivacySummary")
        self.privacy_summary_label.setWordWrap(True)
        sharing_content.addWidget(self.privacy_summary_label, 1)
        self.privacy_btn = QPushButton("Sharing & Privacy")
        self.privacy_btn.setFixedWidth(145)
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        sharing_content.addWidget(self.privacy_btn)
        sharing_grid.addLayout(sharing_content, 0, 1)

        rolls_label = QLabel("Session Rolls")
        rolls_label.setObjectName("FieldLabel")
        sharing_grid.addWidget(rolls_label, 1, 0)
        self.roll_share_checkbox = QCheckBox(
            "Share my dice rolls during active sessions"
        )
        self.roll_share_checkbox.setToolTip(
            "When off, rolls made while a campaign session is active are not stored in the DM session log. Rolls outside sessions are unchanged."
        )
        self.roll_share_checkbox.setVisible(False)
        self.roll_share_checkbox.toggled.connect(self._session_roll_sharing_changed)
        sharing_grid.addWidget(self.roll_share_checkbox, 1, 1)

        page2.addLayout(form2)
        page2.addWidget(self.privacy_pane)
        page2.addStretch()
        self.campaign_pages.addWidget(character_page)

        # ==============================================================
        # PAGE 3 — CREATION RULES
        # ============================================================== 
        rules_page = QFrame()
        rules_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page3 = QVBoxLayout(rules_page)
        page3.setContentsMargins(18, 14, 18, 6)
        page3.setSpacing(7)

        rules_title = QLabel("Creation Rules")
        rules_title.setObjectName("SectionTitle")
        page3.addWidget(rules_title)

        rules_description = QLabel(
            "These are the same rules used by the normal Character Creation Template."
        )
        rules_description.setObjectName("SectionText")
        rules_description.setWordWrap(True)
        page3.addWidget(rules_description)
        page3.addSpacing(5)

        form3 = QGridLayout()
        form3.setContentsMargins(0, 0, 0, 0)
        form3.setHorizontalSpacing(16)
        form3.setVerticalSpacing(10)
        form3.setColumnMinimumWidth(0, 190)
        form3.setColumnStretch(1, 1)

        summary_label = QLabel("Rules Summary")
        summary_label.setObjectName("FieldLabel")
        summary_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        form3.addWidget(summary_label, 0, 0)
        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        self.rules_view.setMinimumHeight(255)
        self.rules_view.setMaximumHeight(295)
        form3.addWidget(self.rules_view, 0, 1)

        edit_label = QLabel("Change Rules")
        edit_label.setObjectName("FieldLabel")
        form3.addWidget(edit_label, 1, 0)
        edit_row = QHBoxLayout()
        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.setFixedWidth(105)
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        edit_row.addWidget(self.edit_rules_btn)
        edit_row.addStretch()
        form3.addLayout(edit_row, 1, 1)

        page3.addLayout(form3)
        page3.addStretch()
        self.campaign_pages.addWidget(rules_page)

        # ==============================================================
        # BOTTOM NAVIGATION — same organization as the original template.
        # ============================================================== 
        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.addStretch()

        self.campaign_back_btn = QPushButton("← Back")
        self.campaign_back_btn.setFixedWidth(95)
        self.campaign_back_btn.clicked.connect(
            lambda: self._campaign_show_page(self._campaign_page_index - 1)
        )
        bottom.addWidget(self.campaign_back_btn)

        close = QPushButton("Close")
        close.setFixedWidth(82)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)

        self.campaign_next_btn = QPushButton("Next →")
        self.campaign_next_btn.setObjectName("PrimaryButton")
        self.campaign_next_btn.setFixedWidth(95)
        self.campaign_next_btn.clicked.connect(
            lambda: self._campaign_show_page(self._campaign_page_index + 1)
        )
        bottom.addWidget(self.campaign_next_btn)
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
            self.campaign_back_btn,
            self.campaign_next_btn,
            close,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(700)
        self.status_timer.timeout.connect(self._refresh_sync_label)
        self.status_timer.start()

        self.reload_campaigns()
        self._campaign_show_page(0)

    def _campaign_show_page(self, index):
        index = max(0, min(2, int(index)))
        self._campaign_page_index = index
        self.campaign_pages.setCurrentIndex(index)

        names = ("Campaign", "Character", "Creation Rules")
        self.campaign_step_label.setText(
            f"Step {index + 1} of 3  •  {names[index]}"
        )
        self.campaign_back_btn.setVisible(index > 0)
        self.campaign_next_btn.setVisible(index < 2)

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
        "Could not find the Phase 6 DID project. Put this script in the phase6 "
        "folder inside your current code folder and run it from there."
    )


def ensure_import(text, widget_name):
    token = f"    {widget_name},\n"
    if token in text:
        return text
    needle = "    QDialog,\n"
    if needle not in text:
        raise RuntimeError("Could not locate the PySide6 widget import block.")
    return text.replace(needle, needle + token, 1)


def replace_campaign_constructor(text):
    marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    start = text.find("    def __init__(self, window):\n", class_pos)
    end = text.find("    def _show_error(self, title, error):\n", start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the Campaign constructor.")

    current = text[start:end]
    if "Campaign Details" in current and "form1 = QGridLayout()" in current:
        return text, False

    return text[:start] + NEW_INIT + text[end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original

    # Campaign only. Do NOT patch CharacterTemplateDialog or its stylesheet.
    text = ensure_import(text, "QFrame")
    text = ensure_import(text, "QStackedWidget")
    text = ensure_import(text, "QGridLayout")

    required = (
        "CampaignSessionService",
        "privacy_store_for_window",
        "open_sharing_privacy",
        "open_dm_dashboard",
        "Campaign-created characters are normal local characters too",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError(
            "The Phase 6 Campaign features are not fully installed. Missing: "
            + ", ".join(missing)
        )

    text, changed = replace_campaign_constructor(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v8")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign original-template layout: PASS" if changed else "Campaign original-template layout: already installed")
    print("Original Character Creation Template: UNTOUCHED")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
