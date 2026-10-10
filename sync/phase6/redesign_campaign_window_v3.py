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
        ("Improvements", improvement_mode),
        ("Custom Improvements", "Allowed" if rules.allow_custom_improvements else "Disabled"),
    ]

    table_rows = "".join(
        "<tr>"
        f"<td style='padding:5px 18px 5px 0;color:#765d34;font-weight:700;'>{html.escape(label)}</td>"
        f"<td style='padding:5px 0;color:#25190f;'>{html.escape(value)}</td>"
        "</tr>"
        for label, value in rows
    )

    extra = ""
    if template.description:
        extra += (
            "<div style='margin-top:14px;padding-top:10px;border-top:1px solid #ead9b5;'>"
            f"{html.escape(template.description)}"
            "</div>"
        )
    if template.player_instructions:
        extra += (
            "<div style='margin-top:12px;'>"
            "<b style='color:#765d34;'>Instructions for players</b><br>"
            f"{html.escape(template.player_instructions)}"
            "</div>"
        )

    return (
        f"<div style='font-family:Georgia;color:#25190f;'>"
        f"<div style='font-size:18px;font-weight:700;margin-bottom:8px;'>{html.escape(template.name)}</div>"
        f"<table cellspacing='0' cellpadding='0'>{table_rows}</table>"
        f"{extra}</div>"
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
        self.resize(900, 610)
        self.setMinimumSize(820, 560)

        modern_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f8f3e8;
        }
        QLabel#WindowTitle {
            color: #25190f;
            font-family: Georgia;
            font-size: 24px;
            font-weight: 900;
        }
        QLabel#Subtitle {
            color: #7a6647;
            font-family: Georgia;
            font-size: 11px;
        }
        QLabel#MetaPill, QLabel#SyncPill {
            background-color: #fffaf0;
            border: 1px solid #dfc58f;
            border-radius: 8px;
            color: #5a452a;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 700;
            padding: 6px 9px;
        }
        QLabel#SectionTitle {
            color: #25190f;
            font-family: Georgia;
            font-size: 16px;
            font-weight: 900;
        }
        QLabel#SectionHint {
            color: #7a6647;
            font-family: Georgia;
            font-size: 11px;
        }
        QFrame#TopBar, QFrame#CharacterPane, QFrame#RulesPane {
            background-color: #fffdf7;
            border: 1px solid #e0c995;
            border-radius: 12px;
        }
        QComboBox {
            min-height: 32px;
            background-color: #fffdf7;
            border: 1px solid #cfaa5a;
            border-radius: 8px;
            padding: 3px 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
        }
        QPushButton {
            min-height: 30px;
            padding: 4px 12px;
            border-radius: 8px;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
        }
        QPushButton#PrimaryButton {
            background-color: #2f718c;
            color: white;
            border: 1px solid #245b70;
        }
        QPushButton#PrimaryButton:hover { background-color: #3b86a3; }
        QPushButton#DashboardButton {
            background-color: #f3e2b8;
            color: #3f2d16;
            border: 1px solid #c08b2d;
        }
        QPushButton#DashboardButton:hover { background-color: #f8eac7; }
        QPushButton#QuietButton {
            background-color: transparent;
            border: 1px solid #d2b77e;
            color: #3f3020;
        }
        QPushButton#QuietButton:hover { background-color: #fff7e8; }
        QPushButton#DangerButton {
            background-color: transparent;
            border: 1px solid #d9b9ad;
            color: #8b3932;
        }
        QTabWidget::pane {
            border: 1px solid #dfc58f;
            border-radius: 10px;
            background-color: #fffdf7;
            top: -1px;
        }
        QTabBar::tab {
            background: transparent;
            color: #765d34;
            border: none;
            padding: 9px 17px;
            margin-right: 3px;
            font-family: Georgia;
            font-size: 11px;
            font-weight: 800;
        }
        QTabBar::tab:selected {
            color: #2f718c;
            border-bottom: 3px solid #2f718c;
        }
        QTabBar::tab:hover { color: #25190f; }
        QTextEdit#RulesView {
            background-color: transparent;
            border: none;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 2px;
        }
        QCheckBox {
            color: #3b332a;
            font-family: Georgia;
            font-size: 11px;
            spacing: 6px;
        }
        """
        set_themed_stylesheet(self, modern_qss)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ------------------------------------------------------------------
        # Header
        # ------------------------------------------------------------------
        header = QHBoxLayout()
        header.setSpacing(12)

        header_text = QVBoxLayout()
        header_text.setSpacing(0)
        title = QLabel("Campaign")
        title.setObjectName("WindowTitle")
        subtitle = QLabel("Manage the campaign, its characters and creation rules.")
        subtitle.setObjectName("Subtitle")
        header_text.addWidget(title)
        header_text.addWidget(subtitle)
        header.addLayout(header_text, 1)

        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.dashboard_btn.setObjectName("DashboardButton")
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        header.addWidget(self.dashboard_btn)
        root.addLayout(header)

        # ------------------------------------------------------------------
        # Selected campaign strip. One compact control area instead of a
        # separate left-hand management column.
        # ------------------------------------------------------------------
        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QVBoxLayout(top_bar)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(7)

        selector_row = QHBoxLayout()
        selector_row.setSpacing(8)
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        selector_row.addWidget(self.campaign_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("QuietButton")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        selector_row.addWidget(self.refresh_btn)

        self.create_btn = QPushButton("New Campaign")
        self.create_btn.setObjectName("QuietButton")
        self.create_btn.clicked.connect(self.create_campaign)
        selector_row.addWidget(self.create_btn)

        self.join_btn = QPushButton("Join")
        self.join_btn.setObjectName("QuietButton")
        self.join_btn.clicked.connect(self.join_campaign)
        selector_row.addWidget(self.join_btn)
        top_layout.addLayout(selector_row)

        info_row = QHBoxLayout()
        info_row.setSpacing(8)
        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setObjectName("MetaPill")
        self.meta_label.setWordWrap(False)
        info_row.addWidget(self.meta_label)
        info_row.addStretch()
        top_layout.addLayout(info_row)
        root.addWidget(top_bar)

        # ------------------------------------------------------------------
        # Tabs keep the two jobs separate. The previous layouts showed every
        # control at once and therefore always felt like a settings form.
        # ------------------------------------------------------------------
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        # Character tab -----------------------------------------------------
        character_page = QWidget()
        character_root = QVBoxLayout(character_page)
        character_root.setContentsMargins(16, 14, 16, 14)
        character_root.setSpacing(11)

        character_head = QHBoxLayout()
        character_titles = QVBoxLayout()
        character_titles.setSpacing(1)
        character_title = QLabel("Current Character")
        character_title.setObjectName("SectionTitle")
        character_hint = QLabel(
            "Create a campaign character or connect the character already open on your sheet."
        )
        character_hint.setObjectName("SectionHint")
        character_titles.addWidget(character_title)
        character_titles.addWidget(character_hint)
        character_head.addLayout(character_titles, 1)
        character_root.addLayout(character_head)

        self.sync_label = QLabel("")
        self.sync_label.setObjectName("SyncPill")
        character_root.addWidget(self.sync_label)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        self.create_character_btn = QPushButton("Create New Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Share Current Character")
        self.share_btn.setObjectName("QuietButton")
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        action_row.addWidget(self.create_character_btn)
        action_row.addWidget(self.share_btn)
        action_row.addStretch()
        action_row.addWidget(self.unlink_btn)
        character_root.addLayout(action_row)

        privacy_pane = QFrame()
        privacy_pane.setObjectName("CharacterPane")
        privacy_layout = QVBoxLayout(privacy_pane)
        privacy_layout.setContentsMargins(12, 10, 12, 10)
        privacy_layout.setSpacing(7)

        privacy_title = QLabel("Sharing")
        privacy_title.setObjectName("SectionTitle")
        privacy_layout.addWidget(privacy_title)

        privacy_row = QHBoxLayout()
        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setObjectName("SectionHint")
        self.privacy_summary_label.setWordWrap(True)
        self.privacy_summary_label.setVisible(False)
        privacy_row.addWidget(self.privacy_summary_label, 1)

        self.privacy_btn = QPushButton("Sharing & Privacy")
        self.privacy_btn.setObjectName("QuietButton")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        self.privacy_btn.setVisible(False)
        privacy_row.addWidget(self.privacy_btn)
        privacy_layout.addLayout(privacy_row)

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
        character_root.addWidget(privacy_pane)
        character_root.addStretch()

        # Rules tab ---------------------------------------------------------
        rules_page = QWidget()
        rules_root = QVBoxLayout(rules_page)
        rules_root.setContentsMargins(16, 14, 16, 14)
        rules_root.setSpacing(9)

        rules_head = QHBoxLayout()
        rules_titles = QVBoxLayout()
        rules_titles.setSpacing(1)
        rules_title = QLabel("Creation Rules")
        rules_title.setObjectName("SectionTitle")
        rules_hint = QLabel("Applied automatically whenever a new campaign character is created.")
        rules_hint.setObjectName("SectionHint")
        rules_titles.addWidget(rules_title)
        rules_titles.addWidget(rules_hint)
        rules_head.addLayout(rules_titles, 1)

        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.setObjectName("QuietButton")
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        rules_head.addWidget(self.edit_rules_btn)
        rules_root.addLayout(rules_head)

        rules_pane = QFrame()
        rules_pane.setObjectName("RulesPane")
        rules_pane_layout = QVBoxLayout(rules_pane)
        rules_pane_layout.setContentsMargins(12, 10, 12, 10)

        self.rules_view = QTextEdit()
        self.rules_view.setObjectName("RulesView")
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        rules_pane_layout.addWidget(self.rules_view)
        rules_root.addWidget(rules_pane, 1)

        self.tabs.addTab(character_page, "Character")
        self.tabs.addTab(rules_page, "Creation Rules")
        root.addWidget(self.tabs, 1)

        bottom = QHBoxLayout()
        bottom.addStretch()
        close = QPushButton("Close")
        close.setObjectName("QuietButton")
        close.setFixedWidth(82)
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
    needle = "    QFrame,\n" if "    QFrame,\n" in text else "    QDialog,\n"
    if needle not in text:
        raise RuntimeError("Could not locate the PySide6 widget import block.")
    return text.replace(needle, needle + token, 1)


def replace_function(text, start_marker, end_marker, replacement, label):
    start = text.find(start_marker)
    end = text.find(end_marker, start + len(start_marker))
    if start < 0 or end < 0:
        raise RuntimeError(f"Could not safely locate {label}.")
    return text[:start] + replacement + text[end:]


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
    if 'self.tabs = QTabWidget()' in current and 'Create New Character' in current:
        return text, False
    return text[:start] + NEW_INIT + text[end:], True


def replace_rules_html(text):
    start = "def _rules_html(campaign: dict) -> str:\n"
    end = "def _replace_current_character(window, template: CharacterTemplate) -> bool:\n"
    current_start = text.find(start)
    current_end = text.find(end, current_start)
    if current_start < 0 or current_end < 0:
        raise RuntimeError("Could not safely locate the Creation Rules formatter.")
    current = text[current_start:current_end]
    if "table_rows" in current and "Starting level" in current:
        return text, False
    return text[:current_start] + NEW_RULES_HTML + text[current_end:], True


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original
    text = ensure_import(text, "QFrame")
    text = ensure_import(text, "QTabWidget")

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
    text, init_changed = replace_init(text)

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_redesign_v3")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)
    print("Campaign redesign v3: PASS" if (rules_changed or init_changed) else "Campaign redesign v3: already installed")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Tools -> Campaign & Templates -> Campaign...")


if __name__ == "__main__":
    main()
