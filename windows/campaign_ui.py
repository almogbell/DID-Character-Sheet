from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QStackedWidget,
    QFrame,
    QTabWidget,
    QWidget,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from backend_2_1 import Character
from campaign_cloud import CampaignCloudError
from campaign_join_flow import join_campaign_and_publish, JoinedButCharacterNotPublished
from campaign_join_ui import offer_create_character_after_join
from campaign_admission import admit_character
from campaign_dashboard_bridge import open_dm_dashboard as launch_dm_dashboard
from campaign_session import CampaignSessionService
from campaign_privacy import (
    build_window_shared_state,
    privacy_store_for_window,
    sharing_summary,
)
from campaign_privacy_ui import open_sharing_privacy_dialog
from campaign_runtime import (
    campaign_client,
    campaign_sync_status,
    restore_campaign_connection,
    schedule_campaign_state_sync,
    sync_current_character_now,
)
from campaign_template import (
    CampaignTemplateService,
    campaign_template,
    character_rule_mismatches,
)
from character_template import (
    CharacterTemplate,
    CharacterTemplateDialog,
    apply_template_to_character,
    load_template_from_file,
)
from dialogs import ask_yes_no
from ui_theme import set_themed_stylesheet


DIALOG_QSS = """
QDialog { background-color: #fffdf7; }
QLabel { background: transparent; border: none; color: #25190f; font-family: Georgia; }
QPushButton {
    background-color: #fffdf7; border: 1px solid #c79a3b; border-radius: 9px;
    color: #25190f; font-family: Georgia; font-size: 12px; font-weight: 800;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #fff4df; border-color: #a87824; }
QPushButton:disabled { color: #9b9388; border-color: #d8ccb5; background-color: #eee9df; }
QComboBox, QTextEdit {
    background-color: #fffaf0; border: 1px solid #d9bd82; border-radius: 8px;
    color: #25190f; font-family: Georgia; padding: 5px;
}
"""


class CampaignRulesEditorDialog(CharacterTemplateDialog):
    """The existing Creation Rules editor, but save directly into a campaign."""

    def __init__(self, parent=None, template=None):
        super().__init__(parent=parent, template=template or CharacterTemplate())
        self.setWindowTitle("Campaign Creation Rules")
        self.saved_filepath = None

    def save_template_from_ui(self):
        try:
            template = self.read_template_from_ui()
        except Exception as error:
            QMessageBox.warning(self, "Invalid Campaign Rules", str(error))
            return

        if (
            template.rules.improvement_mode in {"allow_only", "ban"}
            and not template.rules.improvement_ids
        ):
            QMessageBox.warning(
                self,
                "Invalid Improvement Rules",
                "Select at least one Improvement for this restriction mode.",
            )
            try:
                self.show_page(3)
            except Exception:
                pass
            return

        self.template = template
        self.saved_filepath = None
        self.accept()


def _rules_html(campaign: dict) -> str:
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


def _replace_current_character(window, template: CharacterTemplate) -> bool:
    discard_old_recovery = False

    if getattr(window, "unsaved_changes", False):
        save_first = ask_yes_no(
            window,
            "New Campaign Character",
            "Creating a new campaign character will replace the current character.\n"
            "Save the current character first?",
            yes_text="Save",
            no_text="Don't Save",
        )
        if save_first:
            window.save_current_character()
            if getattr(window, "unsaved_changes", False):
                return False
        else:
            discard_old_recovery = True

    character = Character.create_new_character()
    apply_template_to_character(character, template)
    character.validate()

    if discard_old_recovery:
        try:
            window.discard_current_recovery()
        except Exception:
            pass

    window.character = character
    window.current_character_filepath = None
    window.saved_character_name = None
    window.character_access_mode = "editable"
    window.active_character_template = template
    window._silently_recovered = False
    window._recovered_state_edited = False
    window._history_restore_pending = False

    window.reconnect_character_references()
    window.refresh_all()
    window.reset_undo_history()
    window.mark_dirty()

    if hasattr(window, "save_status_label"):
        window.save_status_label.setText("Unsaved")

    if hasattr(window, "start_guided_tutorial"):
        QTimer.singleShot(0, window.start_guided_tutorial)

    return True


class CampaignManagerDialog(QDialog):
    def __init__(self, window):
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
        self.resize(900, 610)
        self.setMinimumSize(820, 580)

        # Keep the Campaign manager in the same visual language as the ORIGINAL
        # CharacterTemplateDialog: parchment, Georgia, thin gold borders,
        # compact normal-size buttons, one label/value form per page.
        campaign_qss = DIALOG_QSS + """
        QDialog {
            background-color: #f7f1e5;
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
            border: 1px solid #d9bd82;
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
            border: 1px solid #d9bd82;
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
            border: 1px solid #d9bd82;
            border-radius: 9px;
        }
        QComboBox {
            min-height: 32px;
            background-color: #fffaf0;
            border: 1px solid #d9bd82;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 3px 9px;
        }
        QComboBox::drop-down {
            border: none;
            width: 0px;
        }
        QComboBox::down-arrow {
            image: none;
            width: 0px;
            height: 0px;
        }
        QTextEdit#RulesView {
            background-color: #fffaf0;
            border: 1px solid #d9bd82;
            border-radius: 9px;
            color: #25190f;
            font-family: Georgia;
            font-size: 12px;
            padding: 8px 11px;
        }
        QPushButton {
            background-color: #fffdf7;
            border: 1px solid #c79a3b;
            border-radius: 9px;
            color: #4f3b18;
            font-family: Georgia;
            font-size: 12px;
            font-weight: 800;
            padding: 5px 13px;
            margin: 0px;
        }
        QPushButton:hover {
            background-color: #fff4df;
            border-color: #a87824;
            color: #25190f;
        }
        QPushButton:pressed {
            background-color: #f5ead2;
        }
        QPushButton#PrimaryButton {
            background-color: #d8edf7;
            border: 1px solid #c79a3b;
            color: #25190f;
        }
        QPushButton#PrimaryButton:hover {
            background-color: #e8f5fb;
            border-color: #a87824;
        }
        QPushButton#PrimaryButton:pressed {
            background-color: #c9e3ef;
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
        root.addWidget(self.campaign_pages, 0)

        # ==============================================================
        # PAGE 1 — CAMPAIGN
        # ============================================================== 
        campaign_page = QFrame()
        campaign_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page1 = QVBoxLayout(campaign_page)
        page1.setContentsMargins(18, 10, 18, 2)
        page1.setSpacing(7)
        page1.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel("Campaign Setup")
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
        form1.setHorizontalSpacing(10)
        form1.setVerticalSpacing(10)
        form1.setColumnMinimumWidth(0, 112)
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
        self.join_btn = QPushButton("Join Campaign")
        self.dashboard_btn = QPushButton("Open DM Dashboard")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        self.dashboard_btn.clicked.connect(self.open_dm_dashboard)
        action_box.addWidget(self.create_btn)
        action_box.addWidget(self.join_btn)
        action_box.addWidget(self.dashboard_btn)
        action_box.addStretch()
        form1.addLayout(action_box, 2, 1)

        page1.addLayout(form1)
        self.campaign_pages.addWidget(campaign_page)

        # ==============================================================
        # PAGE 2 — CHARACTER
        # ============================================================== 
        character_page = QFrame()
        character_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page2 = QVBoxLayout(character_page)
        page2.setContentsMargins(18, 10, 18, 2)
        page2.setSpacing(7)
        page2.setAlignment(Qt.AlignmentFlag.AlignTop)

        character_title = QLabel("Current Character")
        character_title.setObjectName("SectionTitle")
        page2.addWidget(character_title)

        character_text = QLabel(
            "Create with this campaign's rules, edit normally on the sheet, "
            "then return here and choose Save to Campaign."
        )
        character_text.setObjectName("SectionText")
        character_text.setWordWrap(True)
        page2.addWidget(character_text)
        page2.addSpacing(5)

        form2 = QGridLayout()
        form2.setContentsMargins(0, 0, 0, 0)
        form2.setHorizontalSpacing(10)
        form2.setVerticalSpacing(10)
        form2.setColumnMinimumWidth(0, 112)
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
        self.create_character_btn = QPushButton("Create Character")
        self.create_character_btn.setObjectName("PrimaryButton")
        self.share_btn = QPushButton("Save to Campaign")
        self.unlink_btn = QPushButton("Unlink")
        self.unlink_btn.setObjectName("DangerButton")
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
        sharing_grid.setHorizontalSpacing(10)
        sharing_grid.setVerticalSpacing(7)
        sharing_grid.setColumnMinimumWidth(0, 112)
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
        self.campaign_pages.addWidget(character_page)

        # ==============================================================
        # PAGE 3 — CREATION RULES
        # ============================================================== 
        rules_page = QFrame()
        rules_page.setStyleSheet("QFrame { background: transparent; border: none; }")
        page3 = QVBoxLayout(rules_page)
        page3.setContentsMargins(18, 10, 18, 2)
        page3.setSpacing(7)
        page3.setAlignment(Qt.AlignmentFlag.AlignTop)

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
        form3.setHorizontalSpacing(10)
        form3.setVerticalSpacing(10)
        form3.setColumnMinimumWidth(0, 112)
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
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        edit_row.addWidget(self.edit_rules_btn)
        edit_row.addStretch()
        form3.addLayout(edit_row, 1, 1)

        page3.addLayout(form3)
        self.campaign_pages.addWidget(rules_page)

        # ==============================================================
        # BOTTOM NAVIGATION — same organization as the original template.
        # ============================================================== 
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        bottom.addWidget(cancel)
        bottom.addStretch()

        self.campaign_back_btn = QPushButton("← Back")
        self.campaign_back_btn.clicked.connect(
            lambda: self._campaign_show_page(self._campaign_page_index - 1)
        )
        bottom.addWidget(self.campaign_back_btn)

        self.campaign_next_btn = QPushButton("Next →")
        self.campaign_next_btn.setObjectName("PrimaryButton")
        self.campaign_next_btn.clicked.connect(
            lambda: self._campaign_show_page(self._campaign_page_index + 1)
        )
        bottom.addWidget(self.campaign_next_btn)
        root.addLayout(bottom)

        # Fit Campaign buttons to their text like CharacterTemplateDialog.
        # No arbitrary fixed widths: the border hugs the label plus template padding.
        for fitted_button in (
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
            cancel,
        ):
            fitted_button.setMinimumHeight(36)
            fitted_button.adjustSize()
            fitted_button.setFixedWidth(fitted_button.sizeHint().width())

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
            cancel,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(700)
        self.status_timer.timeout.connect(self._refresh_sync_label)
        self.status_timer.start()

        self.reload_campaigns()

        pending = getattr(self.window, "_pending_campaign_character", None)
        current_character_id = str(
            getattr(self.window.character, "id", "") or ""
        )
        if (
            isinstance(pending, dict)
            and str(pending.get("character_id") or "") == current_character_id
            and str(pending.get("campaign_id") or "")
        ):
            self._select_campaign_id(pending.get("campaign_id"))
            self._campaign_show_page(1)
        else:
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

        # Keep one stable wizard size on every step. Changing pages must not
        # resize the window or move the navigation controls.
        self.campaign_pages.setFixedHeight(385)
        if self.height() != 610:
            self.resize(self.width(), 610)

    def _show_error(self, title, error):
        QMessageBox.warning(self, title, str(error))

    def _refresh_sync_label(self):
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

    def reload_campaigns(self):
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaigns = []

        if self.service is None:
            error = getattr(self.window, "_campaign_runtime_error", "Campaign cloud is unavailable")
            self.meta_label.setText(str(error))
            self.rules_view.setPlainText("")
            self.campaign_combo.blockSignals(False)
            self._update_buttons()
            return

        try:
            self.campaigns = self.service.list_campaigns()
        except Exception as error:
            self.meta_label.setText(f"Could not load campaigns: {error}")
            self.campaign_combo.blockSignals(False)
            self._update_buttons()
            return

        for campaign in self.campaigns:
            self.campaign_combo.addItem(
                str(campaign.get("name") or "Unnamed Campaign"),
                campaign.get("id"),
            )

        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self.campaign_combo.setCurrentIndex(0)
            self._campaign_changed(0)
        else:
            self.current_campaign = None
            self.meta_label.setText("No campaigns yet.")
            self.rules_view.setPlainText("")
            self._update_buttons()

    def _campaign_changed(self, index):
        if index < 0 or index >= len(self.campaigns):
            self.current_campaign = None
            self._update_buttons()
            return

        self.current_campaign = self.campaigns[index]
        try:
            role = self.service.role_for_campaign(self.current_campaign["id"])
        except Exception:
            role = ""

        role = str(role or "").strip().lower()
        self.current_campaign["role"] = role

        # DM-only information stays DM-only in the desktop manager too.
        # Players know they are members, but do not need the reusable invite
        # code or DM-dashboard controls.
        if role == "dm":
            invite = self.current_campaign.get("invite_code") or ""
            self.meta_label.setText(
                f"Role: DM    •    Invite code: {invite}"
            )
        elif role == "player":
            self.meta_label.setText("Role: Player")
        else:
            self.meta_label.setText("Role: Member")

        try:
            self.rules_view.setHtml(_rules_html(self.current_campaign))
        except Exception as error:
            self.rules_view.setPlainText(f"Could not read campaign rules: {error}")

        self._update_buttons()

    def _update_buttons(self):
        has_campaign = isinstance(self.current_campaign, dict)
        role = str((self.current_campaign or {}).get("role") or "").strip().lower()
        is_dm = bool(has_campaign and role == "dm")

        # Everyone can create/join campaigns of their own. Controls belonging
        # to the selected campaign are role-aware.
        self.edit_rules_btn.setVisible(is_dm)
        self.edit_rules_btn.setEnabled(is_dm)

        self.dashboard_btn.setVisible(is_dm)
        self.dashboard_btn.setEnabled(is_dm)

        self.create_character_btn.setEnabled(has_campaign)
        self.share_btn.setEnabled(has_campaign)
        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))

        self._refresh_roll_share_checkbox()
        self._refresh_privacy_controls()

    def _current_campaign_character_link(self):
        if self.client is None or not isinstance(self.current_campaign, dict):
            return None

        character_id = str(
            getattr(self.window.character, "id", "") or ""
        ).strip()
        if not character_id:
            return None

        try:
            link = self.client.get_character_link(character_id)
        except Exception:
            return None

        if not isinstance(link, dict):
            return None

        if str(link.get("campaign_id") or "") != str(
            self.current_campaign.get("id") or ""
        ):
            return None

        return link

    def _refresh_roll_share_checkbox(self):
        checkbox = getattr(self, "roll_share_checkbox", None)
        if checkbox is None:
            return

        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or self.session_service is None:
            checkbox.blockSignals(True)
            checkbox.setVisible(False)
            checkbox.blockSignals(False)
            return

        campaign_character_id = str(
            link.get("campaign_character_id") or ""
        ).strip()
        if not campaign_character_id:
            checkbox.setVisible(False)
            return

        checked = True
        try:
            checked = self.session_service.get_roll_sharing(
                campaign_character_id
            )
        except Exception:
            checked = True

        checkbox.blockSignals(True)
        checkbox.setChecked(bool(checked))
        checkbox.setVisible(True)
        checkbox.setEnabled(True)
        checkbox.blockSignals(False)

    def _session_roll_sharing_changed(self, enabled):
        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or self.session_service is None:
            return

        campaign_character_id = str(
            link.get("campaign_character_id") or ""
        ).strip()
        if not campaign_character_id:
            return

        try:
            self.session_service.set_roll_sharing(
                campaign_character_id,
                bool(enabled),
            )
        except Exception as error:
            self._show_error("Update Roll Sharing Failed", error)
            self._refresh_roll_share_checkbox()

    def _refresh_privacy_controls(self):
        button = getattr(self, "privacy_btn", None)
        label = getattr(self, "privacy_summary_label", None)
        pane = getattr(self, "privacy_pane", None)
        if button is None or label is None:
            return

        link = self._current_campaign_character_link()
        visible = isinstance(link, dict) and isinstance(self.current_campaign, dict)
        button.setVisible(visible)
        label.setVisible(visible)
        if pane is not None:
            pane.setVisible(visible)
        if not visible:
            label.setText("")
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        preferences = self.privacy_store.get(campaign_id, character_id)
        label.setText(sharing_summary(preferences))

    def open_sharing_privacy(self):
        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or not isinstance(self.current_campaign, dict):
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        if not campaign_id or not character_id:
            return

        current = self.privacy_store.get(campaign_id, character_id)
        updated = open_sharing_privacy_dialog(
            self,
            self.window.character,
            current,
        )
        if updated is None:
            return

        try:
            self.privacy_store.set(campaign_id, character_id, updated)
            sync_current_character_now(self.window)
        except Exception as error:
            self._show_error("Update Sharing & Privacy Failed", error)
            return

        self._refresh_privacy_controls()

    def open_dm_dashboard(self):
        if (
            not self.current_campaign
            or self.current_campaign.get("role") != "dm"
            or self.client is None
        ):
            return

        try:
            result = launch_dm_dashboard(
                self.client,
                self.current_campaign["id"],
                app_dir=Path(__file__).resolve().parent,
            )
        except Exception as error:
            self._show_error("Open DM Dashboard Failed", error)
            return

        QMessageBox.information(
            self,
            "DM Dashboard",
            "The live DM dashboard has been opened in your browser.\n\n"
            "If the browser does not connect automatically, enter this one-time "
            f"code within 10 minutes:\n\n{result.get('code', '')}",
        )

    def _choose_rules_for_new_campaign(self, campaign_name):
        box = QMessageBox(self)
        box.setWindowTitle("Campaign Creation Rules")
        box.setText(
            "Create the campaign's rules now, or start from an existing .didtemplate file."
        )
        design = box.addButton("Design Rules", QMessageBox.ButtonRole.AcceptRole)
        load_existing = box.addButton("Use Existing Template", QMessageBox.ButtonRole.ActionRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == cancel:
            return None
        if clicked == load_existing:
            return load_template_from_file(parent=self)

        template = CharacterTemplate(name=f"{campaign_name} Rules")
        editor = CampaignRulesEditorDialog(self, template=template)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        return editor.template

    def create_campaign(self):
        if self.service is None:
            error = getattr(self.window, "_campaign_runtime_error", "")
            QMessageBox.warning(
                self, "Create Campaign Unavailable",
                "Campaign connection could not initialize.\n\n"
                + (str(error) if error else "Check the campaign configuration and restart the application."),
            )
            return
        name, ok = QInputDialog.getText(self, "Create Campaign", "Campaign name:")
        name = str(name or "").strip()
        if not ok or not name:
            return

        template = self._choose_rules_for_new_campaign(name)
        if template is None:
            return

        try:
            campaign = self.service.create_campaign(name, template)
        except Exception as error:
            self._show_error("Create Campaign Failed", error)
            return

        QMessageBox.information(
            self,
            "Campaign Created",
            f"Campaign created.\n\nInvite code: {campaign.get('invite_code', '')}",
        )
        self.reload_campaigns()
        self._select_campaign_id(campaign.get("id"))

    def join_campaign(self):
        if self.service is None:
            return
        code, ok = QInputDialog.getText(self, "Join Campaign", "Invite code:")
        code = str(code or "").strip()
        if not ok or not code:
            return

        display_name, ok = QInputDialog.getText(
            self,
            "Join Campaign",
            "Your display name:",
            text=str(getattr(self.window.character, "name", "") or "Player"),
        )
        if not ok:
            return

        try:
            publication = join_campaign_and_publish(
                self.window, self.service, self.client, code, display_name
            )
            campaign = publication.campaign
        except JoinedButCharacterNotPublished as error:
            campaign = error.campaign
            publication = None
            self._show_error("Campaign Joined — Upload Failed", error)
        except Exception as error:
            self._show_error("Join Campaign Failed", error)
            return

        self.reload_campaigns()
        self._select_campaign_id(campaign.get("id"))
        if publication is not None:
            if publication.status == "linked":
                message = f"{publication.character_name} was automatically sent to the DM."
                if publication.warning:
                    message += "\n\n" + publication.warning
                QMessageBox.information(self, "Campaign Joined", message)
            elif publication.status == "approval_pending":
                QMessageBox.warning(
                    self, "DM Approval Required",
                    f"{publication.character_name} does not meet the campaign creation rules:\n\n"
                    + "\n".join("• " + detail for detail in publication.mismatches)
                    + "\n\nYour request was sent to the DM. The character will not "
                      "be admitted until the DM approves it."
                )
            elif publication.status == "needs_character":
                offer_create_character_after_join(
                    self, self.window, publication.campaign,
                    on_created=self.accept,
                )
            else:
                QMessageBox.warning(
                    self, "Campaign Joined — Character Not Sent",
                    "The character is connected to another campaign. It was not reassigned."
                )

    def _select_campaign_id(self, campaign_id):
        for index, campaign in enumerate(self.campaigns):
            if str(campaign.get("id")) == str(campaign_id):
                self.campaign_combo.setCurrentIndex(index)
                self._campaign_changed(index)
                return

    def edit_campaign_rules(self):
        if not self.current_campaign or self.current_campaign.get("role") != "dm":
            return
        template = campaign_template(self.current_campaign)
        editor = CampaignRulesEditorDialog(self, template=template)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = self.service.update_campaign_template(
                self.current_campaign["id"],
                editor.template,
            )
        except Exception as error:
            self._show_error("Update Rules Failed", error)
            return

        QMessageBox.information(
            self,
            "Campaign Rules Updated",
            "The campaign now uses the new Creation Rules. Existing characters were not silently changed.",
        )
        self.reload_campaigns()
        self._select_campaign_id(updated.get("id"))

    def create_and_share_character(self):
        """Create a campaign-rules character, then return to the sheet to edit it.

        Saving/linking is deliberately a separate action.  Creating a character
        should never force the user through a Save dialog before they have had a
        chance to actually build the character.
        """
        if not self.current_campaign:
            return

        template = campaign_template(self.current_campaign)
        try:
            if not _replace_current_character(self.window, template):
                return
        except Exception as error:
            self._show_error("Create Campaign Character Failed", error)
            return

        # Remember the campaign only for this running app/session.  The
        # character itself remains a completely normal .didchar character once
        # the user saves it.  This marker just lets Campaign reopen directly on
        # the useful Character step and skip a pointless compliance warning.
        self.window._pending_campaign_character = {
            "campaign_id": str(self.current_campaign.get("id") or ""),
            "campaign_name": str(self.current_campaign.get("name") or "Campaign"),
            "character_id": str(getattr(self.window.character, "id", "") or ""),
        }

        # The Campaign dialog is modal.  Close it so the user can immediately
        # edit the newly-created character on the normal character sheet.
        self.accept()

    def share_current_character(self, skip_compliance=False):
        """Save the current character locally, then save/link it to Campaign.

        This is the single simple Campaign save action.  A new campaign
        character is edited normally on the sheet first; when the user chooses
        Save to Campaign, the normal local .didchar save happens first and only
        then is the safe shared state linked/uploaded to the selected campaign.
        """
        if not self.current_campaign or self.client is None:
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        campaign_name = str(self.current_campaign.get("name") or "Campaign")
        if not campaign_id:
            return

        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        pending = getattr(self.window, "_pending_campaign_character", None)
        pending_matches = (
            isinstance(pending, dict)
            and str(pending.get("campaign_id") or "") == campaign_id
            and str(pending.get("character_id") or "") == character_id
        )

        # The admission service below checks campaign rules even for characters
        # originating in the wizard. No "Save Anyway" bypass is permitted.

        window = self.window
        client = self.client

        # Close the modal Campaign dialog before invoking the normal character
        # Save flow.  This prevents the file/name dialog from fighting a modal
        # parent and makes the sequence feel exactly like normal character save.
        self.accept()

        def save_and_link():
            had_wizard_marker = isinstance(getattr(window, "_pending_campaign_character", None), dict)
            try:
                window.save_current_character()
            except Exception as error:
                QMessageBox.warning(
                    window,
                    "Save Character Failed",
                    str(error),
                )
                return

            # Cancelling the normal Save dialog is a clean cancellation: do not
            # create a cloud-only character that cannot be found in Load Character.
            filepath = getattr(window, "current_character_filepath", None)
            if not filepath or getattr(window, "unsaved_changes", False):
                QMessageBox.information(
                    window,
                    "Character Not Saved to Campaign",
                    "Nothing was uploaded. The character is still open on your "
                    "sheet. Save it when you are ready, then choose Save to "
                    "Campaign again.",
                )
                return

            if had_wizard_marker and not getattr(window, "_pending_campaign_character", None):
                return  # First-save hook already submitted and reported the result.
            try:
                state = build_window_shared_state(window, campaign_id=campaign_id)
                admission = admit_character(window, self.current_campaign, client, state)
                if admission.status == "approval_pending":
                    QMessageBox.warning(
                        window, "DM Approval Required",
                        "This character does not meet the campaign's creation rules:\n\n"
                        + "\n".join("• " + item for item in admission.mismatches)
                        + "\n\nA request has been sent to the DM. The character "
                          "is not linked until approved."
                    )
                    return
                if admission.status == "linked_elsewhere":
                    QMessageBox.warning(window, "Character Not Linked", "This character is linked to another campaign.")
                    return
                restore_campaign_connection(window)
                schedule_campaign_state_sync(window)
                sync_current_character_now(window)
            except Exception as error:
                QMessageBox.warning(
                    window,
                    "Save to Campaign Failed",
                    str(error),
                )
                return

            current_pending = getattr(window, "_pending_campaign_character", None)
            if (
                isinstance(current_pending, dict)
                and str(current_pending.get("campaign_id") or "") == campaign_id
                and str(current_pending.get("character_id") or "")
                == str(getattr(window.character, "id", "") or "")
            ):
                try:
                    delattr(window, "_pending_campaign_character")
                except Exception:
                    window._pending_campaign_character = None

            QMessageBox.information(
                window,
                "Saved to Campaign",
                f"The character was saved locally and connected to {campaign_name}. "
                "It will now appear in Load Character, and its allowed shared "
                "campaign data will stay in sync while connected.",
            )

        QTimer.singleShot(0, save_and_link)

    def unlink_current_character(self):
        if self.client is None:
            return
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        if not character_id:
            return
        if not self.client.unlink_local_character(character_id):
            return
        restore_campaign_connection(self.window)
        self._update_buttons()
        QMessageBox.information(
            self,
            "Character Unlinked",
            "This computer will stop syncing the current character. The existing campaign record is not deleted.",
        )


def open_campaign_manager(window):
    # Phase 7 separates DM campaign management from the player experience.
    from campaign_role_ui import open_dm_campaign_manager
    return open_dm_campaign_manager(window)
