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
        self.resize(980, 760)
        self.setMinimumSize(860, 660)

        wizard_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f5efe1;
        }
        QLabel#PageTitle {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 28px;
            font-weight: 900;
        }
        QLabel#PageSubtitle {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 13px;
            font-weight: 700;
        }
        QLabel#StepBar {
            background-color: #fffaf0;
            border: 1px solid #d8ad58;
            border-radius: 11px;
            color: #76521e;
            font-family: Georgia;
            font-size: 13px;
            font-weight: 800;
            padding: 7px 10px;
        }
        QLabel#SectionTitle {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 22px;
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
        QLabel#FieldLabel {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
        }
        QLabel#CharacterName {
            background: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 18px;
            font-weight: 900;
        }
        QLabel#Muted,
        QLabel#CampaignMeta,
        QLabel#SyncStatus,
        QLabel#PrivacySummary {
            background: transparent;
            border: none;
            color: #765d34;
            font-family: Georgia;
            font-size: 11px;
        }
        QLabel#CampaignMeta,
        QLabel#SyncStatus {
            font-weight: 800;
        }
        QFrame#FieldBox,
        QFrame#CharacterBox,
        QFrame#SharingBox {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 11px;
        }
        QComboBox {
            min-height: 38px;
            background-color: #fffaf0;
            border: 1px solid #d2a650;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 4px 10px;
        }
        QTextEdit#RulesView {
            background-color: #fffaf0;
            border: 1px solid #d8b56d;
            border-radius: 11px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 12px 15px;
        }
        QPushButton {
            min-height: 38px;
            background-color: #fffaf0;
            border: 1px solid #c99836;
            border-radius: 10px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 800;
            padding: 5px 15px;
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
        set_themed_stylesheet(self, wizard_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        root.setSpacing(10)

        title = QLabel("Campaign")
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(title)

        subtitle = QLabel(
            "Manage the campaign, its character, creation rules, and live play."
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
        page1.setContentsMargins(22, 18, 22, 8)
        page1.setSpacing(11)

        heading = QLabel("Campaign")
        heading.setObjectName("SectionTitle")
        page1.addWidget(heading)

        intro = QLabel(
            "Choose the campaign you want to manage, create a new one, or join an existing campaign."
        )
        intro.setObjectName("SectionText")
        intro.setWordWrap(True)
        page1.addWidget(intro)

        campaign_label = QLabel("Selected Campaign")
        campaign_label.setObjectName("FieldLabel")
        page1.addWidget(campaign_label)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(9)
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        selector_row.addWidget(self.campaign_combo, 1)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        self.refresh_btn.setFixedWidth(105)
        selector_row.addWidget(self.refresh_btn)
        page1.addLayout(selector_row)

        info_box = QFrame()
        info_box.setObjectName("FieldBox")
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(15, 12, 15, 12)
        info_layout.setSpacing(5)
        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("CampaignMeta")
        self.meta_label.setWordWrap(True)
        info_layout.addWidget(self.meta_label)
        page1.addWidget(info_box)

        manage_title = QLabel("Campaign Actions")
        manage_title.setObjectName("FieldLabel")
        page1.addWidget(manage_title)

        manage_row = QHBoxLayout()
        manage_row.setSpacing(9)
        self.create_btn = QPushButton("New Campaign")
        self.join_btn = QPushButton("Join Campaign")
        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        manage_row.addWidget(self.create_btn)
        manage_row.addWidget(self.join_btn)
        manage_row.addStretch()
        manage_row.addWidget(self.dashboard_btn)
        page1.addLayout(manage_row)
        page1.addStretch()
        self.campaign_pages.addWidget(campaign_page)

        # ==============================================================
        # PAGE 2 — CHARACTER
        # ============================================================== 
        character_page = QFrame()
        character_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page2 = QVBoxLayout(character_page)
        page2.setContentsMargins(22, 18, 22, 8)
        page2.setSpacing(11)

        character_title = QLabel("Current Character")
        character_title.setObjectName("SectionTitle")
        page2.addWidget(character_title)

        character_text = QLabel(
            "Create a new character with this campaign's rules, or connect the character already open on your sheet."
        )
        character_text.setObjectName("SectionText")
        character_text.setWordWrap(True)
        page2.addWidget(character_text)

        character_box = QFrame()
        character_box.setObjectName("CharacterBox")
        character_box_layout = QHBoxLayout(character_box)
        character_box_layout.setContentsMargins(15, 13, 15, 13)
        character_box_layout.setSpacing(12)

        identity = QVBoxLayout()
        identity.setSpacing(2)
        self.character_name_label = QLabel("")
        self.character_name_label.setObjectName("CharacterName")
        self.character_hint_label = QLabel("")
        self.character_hint_label.setObjectName("Muted")
        self.character_hint_label.setWordWrap(True)
        identity.addWidget(self.character_name_label)
        identity.addWidget(self.character_hint_label)
        character_box_layout.addLayout(identity, 1)

        self.sync_label = QLabel("")
        self.sync_label.setObjectName("SyncStatus")
        self.sync_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        character_box_layout.addWidget(self.sync_label)
        page2.addWidget(character_box)

        action_row = QHBoxLayout()
        action_row.setSpacing(9)
        self.create_character_btn = QPushButton("Create New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Share Current Character")
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        action_row.addWidget(self.create_character_btn)
        action_row.addWidget(self.share_btn)
        action_row.addStretch()
        action_row.addWidget(self.unlink_btn)
        page2.addLayout(action_row)

        self.privacy_pane = QFrame()
        self.privacy_pane.setObjectName("SharingBox")
        self.privacy_pane.setVisible(False)
        sharing_layout = QVBoxLayout(self.privacy_pane)
        sharing_layout.setContentsMargins(15, 11, 15, 11)
        sharing_layout.setSpacing(7)

        sharing_top = QHBoxLayout()
        sharing_title = QLabel("Sharing with the DM")
        sharing_title.setObjectName("FieldLabel")
        sharing_top.addWidget(sharing_title)
        sharing_top.addStretch()
        self.privacy_btn = QPushButton("Sharing & Privacy")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        sharing_top.addWidget(self.privacy_btn)
        sharing_layout.addLayout(sharing_top)

        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("PrivacySummary")
        self.privacy_summary_label.setWordWrap(True)
        sharing_layout.addWidget(self.privacy_summary_label)

        self.roll_share_checkbox = QCheckBox(
            "Share my dice rolls during active sessions"
        )
        self.roll_share_checkbox.setToolTip(
            "When off, rolls made while a campaign session is active are not stored in the DM session log. Rolls outside sessions are unchanged."
        )
        self.roll_share_checkbox.setVisible(False)
        self.roll_share_checkbox.toggled.connect(self._session_roll_sharing_changed)
        sharing_layout.addWidget(self.roll_share_checkbox)
        page2.addWidget(self.privacy_pane)
        page2.addStretch()
        self.campaign_pages.addWidget(character_page)

        # ==============================================================
        # PAGE 3 — CREATION RULES
        # ============================================================== 
        rules_page = QFrame()
        rules_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page3 = QVBoxLayout(rules_page)
        page3.setContentsMargins(22, 18, 22, 8)
        page3.setSpacing(11)

        rules_header = QHBoxLayout()
        rules_titles = QVBoxLayout()
        rules_titles.setSpacing(2)
        rules_title = QLabel("Creation Rules")
        rules_title.setObjectName("SectionTitle")
        rules_description = QLabel(
            "These rules are applied automatically whenever a new campaign character is created."
        )
        rules_description.setObjectName("SectionText")
        rules_description.setWordWrap(True)
        rules_titles.addWidget(rules_title)
        rules_titles.addWidget(rules_description)
        rules_header.addLayout(rules_titles, 1)

        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        rules_header.addWidget(self.edit_rules_btn)
        page3.addLayout(rules_header)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        self.rules_view.setMinimumHeight(330)
        page3.addWidget(self.rules_view, 1)
        self.campaign_pages.addWidget(rules_page)

        # ==============================================================
        # BOTTOM NAVIGATION — mirrors the Creation Rules wizard.
        # ============================================================== 
        bottom = QHBoxLayout()
        bottom.setSpacing(9)

        self.campaign_back_btn = QPushButton("← Back")
        self.campaign_back_btn.clicked.connect(
            lambda: self._campaign_show_page(self._campaign_page_index - 1)
        )
        bottom.addWidget(self.campaign_back_btn)
        bottom.addStretch()

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        bottom.addWidget(close)

        self.campaign_next_btn = QPushButton("Next →")
        self.campaign_next_btn.setObjectName("PrimaryButton")
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
        "Could not find the Phase 6 DID project. Put this script in the phase6 folder inside your current code folder and run it from there."
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
    if "def _campaign_show_page" in current and "Step {index + 1} of 3" in current:
        return text, False
    return text[:start] + NEW_INIT + text[end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original
    text = ensure_import(text, "QFrame")
    text = ensure_import(text, "QStackedWidget")

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

    text, changed = replace_constructor(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_redesign_v6")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign Creation-Rules-style redesign: PASS" if changed else "Campaign Creation-Rules-style redesign: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
