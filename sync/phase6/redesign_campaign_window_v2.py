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
        self.resize(860, 610)
        self.setMinimumSize(800, 570)

        compact_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f6f0e4;
        }
        QFrame#Panel {
            background-color: #fffaf0;
            border: 1px solid #d8bd82;
            border-radius: 12px;
        }
        QLabel#Eyebrow {
            color: #9a6c1c;
            font-family: Georgia;
            font-size: 10px;
            font-weight: 900;
        }
        QLabel#BigTitle {
            color: #25190f;
            font-family: Georgia;
            font-size: 22px;
            font-weight: 900;
        }
        QLabel#Muted {
            color: #765d34;
            font-family: Georgia;
            font-size: 11px;
        }
        QLabel#Meta {
            color: #4c3924;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 700;
        }
        QLabel#StatusPill {
            background-color: #fff7e7;
            border: 1px solid #dfc48b;
            border-radius: 8px;
            color: #5a452a;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 700;
            padding: 6px 9px;
        }
        QTextEdit#RulesView {
            background-color: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 0px;
        }
        QComboBox {
            min-height: 31px;
            background-color: #fffdf7;
            border: 1px solid #d2ae62;
            border-radius: 8px;
            padding: 3px 8px;
        }
        QPushButton {
            min-height: 29px;
            padding: 3px 11px;
            border-radius: 8px;
        }
        QPushButton#PrimaryButton {
            background-color: #2f718c;
            color: #ffffff;
            border: 1px solid #245b70;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #3b86a3;
        }
        QPushButton#DashboardButton {
            background-color: #f0deb0;
            border: 1px solid #bd8b2d;
            color: #3f2d16;
        }
        QPushButton#DashboardButton:hover {
            background-color: #f6e8c6;
        }
        QPushButton#QuietButton {
            background-color: transparent;
            border: 1px solid #cfb47e;
        }
        QPushButton#DangerButton {
            background-color: transparent;
            border: 1px solid #d3b6aa;
            color: #8b3932;
        }
        QCheckBox {
            color: #3b332a;
            font-family: Georgia;
            font-size: 11px;
            spacing: 6px;
        }
        """
        set_themed_stylesheet(self, compact_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(11)

        # Header: intentionally compact; the content should be the focus.
        header = QHBoxLayout()
        header.setSpacing(12)
        header_text = QVBoxLayout()
        header_text.setSpacing(1)
        title = QLabel("Campaign")
        title.setObjectName("BigTitle")
        subtitle = QLabel(
            "Creation rules, shared characters and live play in one place."
        )
        subtitle.setObjectName("Muted")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)
        root.addLayout(header)

        # Main area: campaign controls on the left, rules on the right.
        body = QHBoxLayout()
        body.setSpacing(11)

        campaign_panel = QFrame()
        campaign_panel.setObjectName("Panel")
        campaign_panel.setMinimumWidth(275)
        campaign_panel.setMaximumWidth(310)
        campaign_layout = QVBoxLayout(campaign_panel)
        campaign_layout.setContentsMargins(14, 13, 14, 13)
        campaign_layout.setSpacing(8)

        campaign_eyebrow = QLabel("CAMPAIGN")
        campaign_eyebrow.setObjectName("Eyebrow")
        campaign_layout.addWidget(campaign_eyebrow)

        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        campaign_layout.addWidget(self.campaign_combo)

        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("Meta")
        self.meta_label.setWordWrap(True)
        campaign_layout.addWidget(self.meta_label)

        self.refresh_btn = QPushButton("Refresh campaigns")
        self.refresh_btn.setObjectName("QuietButton")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        campaign_layout.addWidget(self.refresh_btn)

        campaign_layout.addSpacing(5)
        campaign_action_label = QLabel("MANAGE")
        campaign_action_label.setObjectName("Eyebrow")
        campaign_layout.addWidget(campaign_action_label)

        self.create_btn = QPushButton("Create Campaign")
        self.join_btn = QPushButton("Join Campaign")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        campaign_layout.addWidget(self.create_btn)
        campaign_layout.addWidget(self.join_btn)

        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.dashboard_btn.setObjectName("DashboardButton")
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        campaign_layout.addWidget(self.dashboard_btn)
        campaign_layout.addStretch()
        body.addWidget(campaign_panel)

        rules_panel = QFrame()
        rules_panel.setObjectName("Panel")
        rules_layout = QVBoxLayout(rules_panel)
        rules_layout.setContentsMargins(15, 13, 15, 13)
        rules_layout.setSpacing(8)

        rules_head = QHBoxLayout()
        rules_title_box = QVBoxLayout()
        rules_title_box.setSpacing(1)
        rules_eyebrow = QLabel("CREATION RULES")
        rules_eyebrow.setObjectName("Eyebrow")
        rules_hint = QLabel("Applied automatically to new campaign characters")
        rules_hint.setObjectName("Muted")
        rules_title_box.addWidget(rules_eyebrow)
        rules_title_box.addWidget(rules_hint)
        rules_head.addLayout(rules_title_box, 1)

        self.edit_rules_btn = QPushButton("Edit")
        self.edit_rules_btn.setObjectName("QuietButton")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        self.edit_rules_btn.setFixedWidth(78)
        rules_head.addWidget(self.edit_rules_btn)
        rules_layout.addLayout(rules_head)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        self.rules_view.setMinimumHeight(185)
        self.rules_view.setMaximumHeight(225)
        rules_layout.addWidget(self.rules_view, 1)

        rules_layout.addStretch()
        body.addWidget(rules_panel, 1)
        root.addLayout(body, 1)

        # Connection / privacy appears only when relevant and stays visually light.
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.sync_label = QLabel("")
        self.sync_label.setObjectName("StatusPill")
        status_row.addWidget(self.sync_label, 1)

        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("Muted")
        self.privacy_summary_label.setWordWrap(False)
        self.privacy_summary_label.setVisible(False)
        status_row.addWidget(self.privacy_summary_label, 1)

        self.privacy_btn = QPushButton("Sharing & Privacy")
        self.privacy_btn.setObjectName("QuietButton")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        self.privacy_btn.setVisible(False)
        status_row.addWidget(self.privacy_btn)
        root.addLayout(status_row)

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
        root.addWidget(self.roll_share_checkbox)

        # Character actions: one clear primary action, secondary actions beside it.
        character_panel = QFrame()
        character_panel.setObjectName("Panel")
        character_layout = QHBoxLayout(character_panel)
        character_layout.setContentsMargins(12, 10, 12, 10)
        character_layout.setSpacing(8)

        character_text = QVBoxLayout()
        character_text.setSpacing(0)
        character_label = QLabel("CHARACTER")
        character_label.setObjectName("Eyebrow")
        character_hint = QLabel("Use the selected campaign's rules")
        character_hint.setObjectName("Muted")
        character_text.addWidget(character_label)
        character_text.addWidget(character_hint)
        character_layout.addLayout(character_text, 1)

        self.create_character_btn = QPushButton("Create New")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Share Current")
        self.share_btn.setObjectName("QuietButton")
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        character_layout.addWidget(self.create_character_btn)
        character_layout.addWidget(self.share_btn)
        character_layout.addWidget(self.unlink_btn)
        root.addWidget(character_panel)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close = QPushButton("Close")
        close.setObjectName("QuietButton")
        close.setFixedWidth(86)
        close.clicked.connect(self.accept)
        bottom.addWidget(close)
        root.addLayout(bottom)

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
    if 'self.setWindowTitle("Campaign")' in current and 'Create New' in current:
        return text, False

    return text[:start] + NEW_INIT + text[end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = ensure_qframe_import(original)

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

    text, changed = replace_init(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_redesign_v2")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign redesign v2: PASS" if changed else "Campaign redesign v2: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py to see the compact Campaign window.")


if __name__ == "__main__":
    main()
