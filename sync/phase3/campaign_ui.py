from __future__ import annotations

import html
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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

    return (
        f"<h3 style='margin:0 0 8px 0'>{html.escape(template.name)}</h3>"
        f"<b>Starting level:</b> {int(rules.level)}<br>"
        f"<b>Extra starting IP:</b> {int(rules.extra_ip)}<br>"
        f"<b>Starting Hearts:</b> {html.escape(str(hearts))}<br>"
        f"<b>Starting AT:</b> {html.escape(str(at))}<br>"
        f"<b>Species:</b> {html.escape(str(rules.species_mode))}<br>"
        f"<b>Free Heightened:</b> {int(getattr(rules, 'free_heightened_ability_slots', 2))}<br>"
        f"<b>Ability arrays:</b> {html.escape(arrays)}<br>"
        f"<b>Improvement rules:</b> {html.escape(improvement_mode)}<br>"
        f"<b>Custom Improvements:</b> {'Allowed' if rules.allow_custom_improvements else 'Disabled'}"
        + (
            f"<br><br>{template.description}"
            if template.description
            else ""
        )
        + (
            f"<br><br><b>Instructions for players</b><br>{template.player_instructions}"
            if template.player_instructions
            else ""
        )
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
        self.campaigns: list[dict] = []
        self.current_campaign: dict | None = None

        self.setWindowTitle("Campaign & Creation Rules")
        self.resize(700, 610)
        self.setMinimumSize(620, 520)
        set_themed_stylesheet(self, DIALOG_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)

        title = QLabel("Campaign & Creation Rules")
        title.setStyleSheet(
            "font-family: Georgia; font-size: 21px; font-weight: 900; color:#25190f;"
        )
        root.addWidget(title)

        explanation = QLabel(
            "A campaign now contains its character-creation template. Players join "
            "the campaign once; the same rules are then used to create campaign characters."
        )
        explanation.setWordWrap(True)
        root.addWidget(explanation)

        top = QHBoxLayout()
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        top.addWidget(self.campaign_combo, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        top.addWidget(self.refresh_btn)
        root.addLayout(top)

        self.meta_label = QLabel("Not connected to a campaign")
        self.meta_label.setWordWrap(True)
        root.addWidget(self.meta_label)

        self.rules_view = QTextEdit()
        self.rules_view.setReadOnly(True)
        self.rules_view.setAcceptRichText(True)
        root.addWidget(self.rules_view, 1)

        self.sync_label = QLabel("")
        root.addWidget(self.sync_label)

        first_row = QHBoxLayout()
        self.create_btn = QPushButton("Create Campaign")
        self.join_btn = QPushButton("Join Campaign")
        self.edit_rules_btn = QPushButton("Edit Campaign Rules")
        self.create_btn.clicked.connect(self.create_campaign)
        self.join_btn.clicked.connect(self.join_campaign)
        self.edit_rules_btn.clicked.connect(self.edit_campaign_rules)
        first_row.addWidget(self.create_btn)
        first_row.addWidget(self.join_btn)
        first_row.addStretch()
        first_row.addWidget(self.edit_rules_btn)
        root.addLayout(first_row)

        second_row = QHBoxLayout()
        self.create_character_btn = QPushButton("Create & Share New Character")
        self.share_btn = QPushButton("Share Current Character")
        self.unlink_btn = QPushButton("Unlink Current Character")
        self.create_character_btn.clicked.connect(self.create_and_share_character)
        self.share_btn.clicked.connect(self.share_current_character)
        self.unlink_btn.clicked.connect(self.unlink_current_character)
        second_row.addWidget(self.create_character_btn)
        second_row.addWidget(self.share_btn)
        second_row.addWidget(self.unlink_btn)
        root.addLayout(second_row)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        close_row.addWidget(close)
        root.addLayout(close_row)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(700)
        self.status_timer.timeout.connect(self._refresh_sync_label)
        self.status_timer.start()

        self.reload_campaigns()

    def _show_error(self, title, error):
        QMessageBox.warning(self, title, str(error))

    def _refresh_sync_label(self):
        self.sync_label.setText(f"Current character sync: {campaign_sync_status(self.window)}")

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
        self.current_campaign["role"] = role

        invite = self.current_campaign.get("invite_code") or ""
        role_text = role.upper() if role else "MEMBER"
        self.meta_label.setText(
            f"Role: {role_text}    •    Invite code: {invite}"
        )
        try:
            self.rules_view.setHtml(_rules_html(self.current_campaign))
        except Exception as error:
            self.rules_view.setPlainText(f"Could not read campaign rules: {error}")
        self._update_buttons()

    def _update_buttons(self):
        has_campaign = isinstance(self.current_campaign, dict)
        role = str((self.current_campaign or {}).get("role") or "")
        self.edit_rules_btn.setEnabled(has_campaign and role == "dm")
        self.create_character_btn.setEnabled(has_campaign)
        self.share_btn.setEnabled(has_campaign)
        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))

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
            campaign = self.service.join_campaign(code, display_name)
        except Exception as error:
            self._show_error("Join Campaign Failed", error)
            return

        self.reload_campaigns()
        self._select_campaign_id(campaign.get("id"))

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

    def share_current_character(self, skip_compliance=False):
        if not self.current_campaign or self.client is None:
            return

        template = campaign_template(self.current_campaign)
        if not skip_compliance:
            mismatches = character_rule_mismatches(self.window.character, template)
            if mismatches:
                details = "\n".join(f"• {item}" for item in mismatches)
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Character Does Not Fully Match Campaign Rules")
                box.setText(
                    "This existing character does not fully match the campaign's Creation Rules:\n\n"
                    + details
                    + "\n\nYou can still share it; the app will not silently rewrite the character."
                )
                share_anyway = box.addButton(
                    "Share Anyway", QMessageBox.ButtonRole.AcceptRole
                )
                cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
                box.exec()
                if box.clickedButton() != share_anyway:
                    return

        try:
            state = self.window.build_dm_shared_character_state()
            self.client.link_character(
                self.current_campaign["id"],
                state,
                remember=True,
            )
            restore_campaign_connection(self.window)
            schedule_campaign_state_sync(self.window)
            sync_current_character_now(self.window)
        except Exception as error:
            self._show_error("Share Character Failed", error)
            return

        self._update_buttons()
        QMessageBox.information(
            self,
            "Character Shared",
            "This character is now linked to the campaign. Character changes and dice rolls will sync automatically while connected.",
        )

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
    dialog = CampaignManagerDialog(window)
    dialog.exec()
    return dialog
