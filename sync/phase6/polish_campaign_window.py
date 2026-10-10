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

        self.setWindowTitle("Campaign & Creation Rules")
        self.resize(820, 720)
        self.setMinimumSize(760, 650)

        polished_qss = DIALOG_QSS + """
        QDialog { background-color: #f7f0df; }
        QFrame#CampaignCard, QFrame#StatusCard, QFrame#ActionCard {
            background-color: #fffaf0;
            border: 1px solid #d9bd82;
            border-radius: 13px;
        }
        QLabel#SectionTitle {
            color: #8b6320;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 900;
            letter-spacing: 1px;
        }
        QLabel#CampaignMeta {
            color: #5e4a2d;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
        }
        QLabel#SyncStatus {
            color: #5e4a2d;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
        }
        QTextEdit#RulesView {
            background-color: #fffdf7;
            border: 1px solid #dcc79f;
            border-radius: 10px;
            padding: 10px 12px;
        }
        QPushButton {
            min-height: 34px;
            padding: 5px 14px;
        }
        QPushButton#PrimaryButton {
            background-color: #2f718c;
            color: white;
            border: 1px solid #245b70;
        }
        QPushButton#PrimaryButton:hover { background-color: #3b86a3; }
        QPushButton#DashboardButton {
            background-color: #f2e2b9;
            border: 1px solid #b88935;
        }
        QPushButton#DashboardButton:hover { background-color: #f7e9c6; }
        QPushButton#DangerButton {
            color: #8b3932;
        }
        QCheckBox {
            color: #3b332a;
            font-family: Georgia;
            font-size: 12px;
            spacing: 7px;
        }
        """
        set_themed_stylesheet(self, polished_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        title = QLabel("Campaign & Creation Rules")
        title.setStyleSheet(
            "font-family: Georgia; font-size: 25px; font-weight: 900; color:#25190f;"
        )
        root.addWidget(title)

        explanation = QLabel(
            "Campaigns keep the creation rules, shared characters, live play and DM dashboard together."
        )
        explanation.setWordWrap(True)
        explanation.setStyleSheet(
            "color:#6f5a3b; font-family:Georgia; font-size:12px; padding-bottom:2px;"
        )
        root.addWidget(explanation)

        campaign_card = QFrame()
        campaign_card.setObjectName("CampaignCard")
        campaign_layout = QVBoxLayout(campaign_card)
        campaign_layout.setContentsMargins(14, 12, 14, 12)
        campaign_layout.setSpacing(8)

        campaign_caption = QLabel("CAMPAIGN")
        campaign_caption.setObjectName("SectionTitle")
        campaign_layout.addWidget(campaign_caption)

        top = QHBoxLayout()
        top.setSpacing(9)
        self.campaign_combo = QComboBox()
        self.campaign_combo.setMinimumHeight(36)
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        top.addWidget(self.campaign_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        top.addWidget(self.refresh_btn)
        campaign_layout.addLayout(top)

        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("CampaignMeta")
        self.meta_label.setWordWrap(True)
        campaign_layout.addWidget(self.meta_label)
        root.addWidget(campaign_card)

        rules_heading = QHBoxLayout()
        rules_heading.setContentsMargins(2, 0, 2, 0)
        rules_title = QLabel("CREATION RULES")
        rules_title.setObjectName("SectionTitle")
        rules_heading.addWidget(rules_title)
        rules_heading.addStretch()

        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        rules_heading.addWidget(self.edit_rules_btn)
        root.addLayout(rules_heading)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        self.rules_view.setMinimumHeight(190)
        self.rules_view.setMaximumHeight(230)
        root.addWidget(self.rules_view)

        status_card = QFrame()
        status_card.setObjectName("StatusCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(14, 10, 14, 10)
        status_layout.setSpacing(7)

        self.sync_label = QLabel("")
        self.sync_label.setObjectName("SyncStatus")
        status_layout.addWidget(self.sync_label)

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
        status_layout.addWidget(self.roll_share_checkbox)

        privacy_row = QHBoxLayout()
        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setWordWrap(True)
        self.privacy_summary_label.setStyleSheet(
            "color:#7c6a52; font-family:Georgia; font-size:11px;"
        )
        self.privacy_btn = QPushButton("Sharing & Privacy...")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        privacy_row.addWidget(self.privacy_summary_label, 1)
        privacy_row.addWidget(self.privacy_btn)
        status_layout.addLayout(privacy_row)
        root.addWidget(status_card)

        campaign_actions = QFrame()
        campaign_actions.setObjectName("ActionCard")
        campaign_actions_layout = QVBoxLayout(campaign_actions)
        campaign_actions_layout.setContentsMargins(14, 10, 14, 12)
        campaign_actions_layout.setSpacing(8)

        campaign_actions_title = QLabel("CAMPAIGN ACTIONS")
        campaign_actions_title.setObjectName("SectionTitle")
        campaign_actions_layout.addWidget(campaign_actions_title)

        first_row = QHBoxLayout()
        first_row.setSpacing(8)
        self.create_btn = QPushButton("Create Campaign")
        self.join_btn = QPushButton("Join Campaign")
        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.dashboard_btn.setObjectName("DashboardButton")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        first_row.addWidget(self.create_btn)
        first_row.addWidget(self.join_btn)
        first_row.addStretch()
        first_row.addWidget(self.dashboard_btn)
        campaign_actions_layout.addLayout(first_row)
        root.addWidget(campaign_actions)

        character_actions = QFrame()
        character_actions.setObjectName("ActionCard")
        character_actions_layout = QVBoxLayout(character_actions)
        character_actions_layout.setContentsMargins(14, 10, 14, 12)
        character_actions_layout.setSpacing(8)

        character_actions_title = QLabel("CHARACTER")
        character_actions_title.setObjectName("SectionTitle")
        character_actions_layout.addWidget(character_actions_title)

        second_row = QHBoxLayout()
        second_row.setSpacing(8)
        self.create_character_btn = QPushButton("Create & Share New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Share Current Character")
        self.unlink_btn = QPushButton("Unlink Current Character")
        self.unlink_btn.setObjectName("DangerButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        second_row.addWidget(self.create_character_btn, 2)
        second_row.addWidget(self.share_btn, 2)
        second_row.addWidget(self.unlink_btn, 2)
        character_actions_layout.addLayout(second_row)
        root.addWidget(character_actions)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        close = QPushButton("Close")
        close.setMinimumWidth(96)
        close.clicked.connect(self.accept)
        bottom_row.addWidget(close)
        root.addLayout(bottom_row)

        for button in (
            self.refresh_btn,
            self.edit_rules_btn,
            self.create_btn,
            self.join_btn,
            self.dashboard_btn,
            self.create_character_btn,
            self.share_btn,
            self.unlink_btn,
            self.privacy_btn,
            close,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(700)
        self.status_timer.timeout.connect(self._refresh_sync_label)
        self.status_timer.start()

        self.reload_campaigns()

'''


OLD_CREATE = r'''    def create_and_share_character(self):
        if not self.current_campaign:
            return
        template = campaign_template(self.current_campaign)
        try:
            if not _replace_current_character(self.window, template):
                return
        except Exception as error:
            self._show_error("Create Campaign Character Failed", error)
            return
        self.share_current_character(skip_compliance=True)
'''

NEW_CREATE = r'''    def create_and_share_character(self):
        if not self.current_campaign:
            return
        template = campaign_template(self.current_campaign)
        try:
            if not _replace_current_character(self.window, template):
                return
        except Exception as error:
            self._show_error("Create Campaign Character Failed", error)
            return

        # Campaign-created characters are normal local characters too. Save
        # them before linking so they immediately appear in Load Character and
        # receive the same history/autosave behavior as every other character.
        self.window.save_current_character()
        if not getattr(self.window, "current_character_filepath", None):
            QMessageBox.information(
                self,
                "Character Not Shared Yet",
                "The new character is still open, but it was not linked to the "
                "campaign because it was not saved locally. Save it, then use "
                "Share Current Character.",
            )
            return

        self.share_current_character(skip_compliance=True)
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


def ensure_qframe_import(text):
    if "    QFrame,\n" in text:
        return text
    needle = "    QDialog,\n"
    if needle not in text:
        raise RuntimeError("Could not find the PySide6 widget import block.")
    return text.replace(needle, needle + "    QFrame,\n", 1)


def replace_init(text):
    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    start_marker = "    def __init__(self, window):\n"
    start = text.find(start_marker, class_pos)
    end_marker = "    def _show_error(self, title, error):\n"
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise RuntimeError("Could not safely locate the CampaignManagerDialog constructor.")

    current = text[start:end]
    if "QFrame#CampaignCard" in current and 'self.rules_view.setMaximumHeight(230)' in current:
        return text, False

    return text[:start] + NEW_INIT + text[end:], True


def replace_create_method(text):
    if "Campaign-created characters are normal local characters too" in text:
        return text, False
    if OLD_CREATE not in text:
        raise RuntimeError(
            "Could not safely locate create_and_share_character. The local file "
            "has changed in an unexpected way."
        )
    return text.replace(OLD_CREATE, NEW_CREATE, 1), True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = ensure_qframe_import(original)

    required_markers = (
        "CampaignSessionService",
        "privacy_store_for_window",
        "open_sharing_privacy",
        "open_dm_dashboard",
    )
    missing = [marker for marker in required_markers if marker not in text]
    if missing:
        raise RuntimeError(
            "Phase 6 is not fully installed yet. Missing campaign UI pieces: "
            + ", ".join(missing)
        )

    text, ui_changed = replace_init(text)
    text, save_changed = replace_create_method(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_polish")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign UI polish: PASS" if ui_changed else "Campaign UI polish: already installed")
    print("Campaign-character local save fix: PASS" if save_changed else "Campaign-character local save fix: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py to see the redesigned Campaign window.")
    print("New campaign-created characters will now be saved locally before sharing.")


if __name__ == "__main__":
    main()
