from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from campaign_dashboard_bridge import open_dm_dashboard as launch_dm_dashboard
from campaign_party import (
    build_window_party_state,
    normalize_party_preferences,
    party_privacy_store_for_window,
    upload_party_state,
)
from campaign_party_bridge import open_party_dashboard as launch_party_dashboard
from campaign_privacy import (
    build_window_shared_state,
    normalize_privacy_preferences,
    privacy_store_for_window,
)
from campaign_runtime import (
    campaign_client,
    restore_campaign_connection,
    schedule_campaign_state_sync,
    sync_current_character_now,
)
from campaign_session import CampaignSessionService
from campaign_template import CampaignTemplateService, campaign_template
from campaign_ui import CampaignRulesEditorDialog, _replace_current_character
from character_template import CharacterTemplate, load_template_from_file
from ui_theme import set_themed_stylesheet


ROLE_QSS = """
QDialog { background-color: #f7f1e5; }
QLabel { background: transparent; border: none; color: #25190f; font-family: Georgia; }
QLabel#PageTitle { font-size: 27px; font-weight: 900; }
QLabel#PageSubtitle, QLabel#SectionText {
    color: #765d34; font-size: 12px; font-weight: 700;
}
QLabel#StepBar {
    background-color: #fffdf7; border: 1px solid #c79a3b; border-radius: 10px;
    color: #76521e; font-size: 12px; font-weight: 800; padding: 5px 9px;
}
QLabel#SectionTitle { font-size: 21px; font-weight: 900; }
QLabel#FieldLabel { font-size: 12px; }
QLabel#Muted { color: #765d34; font-size: 11px; }
QFrame#Field, QFrame#Card, QFrame#RuleCard {
    background-color: #fffdf7; border: 1px solid #e0c68f; border-radius: 10px;
}
QComboBox {
    min-height: 34px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    padding: 4px 10px;
}
QPushButton {
    min-height: 36px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    font-weight: 800; padding: 5px 13px;
}
QPushButton:hover { background-color: #fff4df; border-color: #a87824; }
QPushButton#PrimaryButton { background-color: #d8edf7; }
QPushButton#PrimaryButton:hover { background-color: #e8f5fb; }
QPushButton#DangerButton { color: #8b3932; border-color: #cba79d; }
QPushButton:disabled { color: #9b9388; border-color: #d8ccb5; background-color: #eee9df; }
QCheckBox {
    color: #25190f; font-family: Georgia; font-size: 12px; spacing: 8px;
    min-height: 28px; padding-top: 2px; padding-bottom: 2px;
}
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { background: transparent; border: none; }
"""


ABILITY_ORDER = ("agility", "strength", "finesse", "instinct", "presence", "knowledge")


def _fit_button(button):
    button.adjustSize()
    button.setFixedWidth(button.sizeHint().width())
    button.setCursor(Qt.CursorShape.PointingHandCursor)


def _campaign_rules_rows(campaign):
    template = campaign_template(campaign)
    rules = template.rules
    hearts = "Normal default" if rules.starting_hearts is None else str(int(rules.starting_hearts) * 4)
    at = "Normal default" if rules.starting_at is None else str(int(rules.starting_at))
    improvement_mode = {
        "all": "All normal Improvements",
        "allow_only": "Only selected Improvements",
        "ban": "All except selected Improvements",
    }.get(rules.improvement_mode, str(rules.improvement_mode))
    arrays = ", ".join(rules.allowed_ability_array_ids) or "All normal arrays"
    return (
        ("Starting Character", (
            ("Starting level", str(int(rules.level))),
            ("Extra starting IP", str(int(rules.extra_ip))),
            ("Free Heightened", str(int(getattr(rules, "free_heightened_ability_slots", 2)))),
            ("Species", str(rules.species_mode)),
        )),
        ("Resources", (
            ("Starting HP", hearts),
            ("Starting AT", at),
        )),
        ("Character Options", (
            ("Ability arrays", arrays),
            ("Improvement rules", improvement_mode),
            ("Custom Improvements", "Allowed" if rules.allow_custom_improvements else "Disabled"),
        )),
    )


def _build_rule_cards(campaign, parent=None):
    wrapper = QWidget(parent)
    layout = QGridLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setHorizontalSpacing(10)
    layout.setVerticalSpacing(10)
    for index, (section, rows) in enumerate(_campaign_rules_rows(campaign)):
        card = QFrame()
        card.setObjectName("RuleCard")
        box = QVBoxLayout(card)
        box.setContentsMargins(14, 11, 14, 11)
        box.setSpacing(6)
        heading = QLabel(section)
        heading.setStyleSheet("font-size:14px; font-weight:900;")
        box.addWidget(heading)
        grid = QGridLayout()
        grid.setContentsMargins(0, 2, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        for row, (label, value) in enumerate(rows):
            left = QLabel(label)
            left.setStyleSheet("color:#765d34; font-size:11px;")
            right = QLabel(value)
            right.setStyleSheet("font-size:12px; font-weight:700;")
            right.setWordWrap(True)
            grid.addWidget(left, row, 0)
            grid.addWidget(right, row, 1)
        grid.setColumnStretch(1, 1)
        box.addLayout(grid)
        layout.addWidget(card, index // 2, index % 2)
    layout.setColumnStretch(0, 1)
    layout.setColumnStretch(1, 1)
    return wrapper


def _state_from_character_row(row):
    nested = row.get("character_state") if isinstance(row, dict) else None
    if isinstance(nested, list):
        nested = nested[0] if nested else None
    if isinstance(nested, dict):
        state = nested.get("state")
        return state if isinstance(state, dict) else {}
    return {}


def _hp_text(state):
    resources = state.get("resources", {}) if isinstance(state, dict) else {}
    hearts = resources.get("hearts", {}) if isinstance(resources, dict) else {}
    try:
        current = max(0, int(hearts.get("current") or 0))
    except Exception:
        current = 0
    try:
        maximum = max(0, int(hearts.get("max") or 0) * 4)
    except Exception:
        maximum = 0
    return f"{current} / {maximum}"


def _at_text(state):
    resources = state.get("resources", {}) if isinstance(state, dict) else {}
    at = resources.get("adversity_tokens", {}) if isinstance(resources, dict) else {}
    try:
        current = max(0, int(at.get("current") or 0))
        maximum = max(0, int(at.get("max") or 0))
    except Exception:
        current = maximum = 0
    return f"{current} / {maximum}"


class _WizardDialog(QDialog):
    page_names = ()

    def _setup_shell(self, title_text, subtitle_text):
        set_themed_stylesheet(self, ROLE_QSS)
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)
        title = QLabel(title_text)
        title.setObjectName("PageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(title)
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("PageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(subtitle)
        self.step_label = QLabel("")
        self.step_label.setObjectName("StepBar")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.step_label)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        bottom = QHBoxLayout()
        self.back_btn = QPushButton("← Back")
        self.back_btn.clicked.connect(lambda: self.show_page(self.page_index - 1))
        bottom.addWidget(self.back_btn)
        bottom.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.next_btn = QPushButton("Next →")
        self.next_btn.setObjectName("PrimaryButton")
        self.next_btn.clicked.connect(lambda: self.show_page(self.page_index + 1))
        bottom.addWidget(self.close_btn)
        bottom.addWidget(self.next_btn)
        root.addLayout(bottom)
        for button in (self.back_btn, self.close_btn, self.next_btn):
            _fit_button(button)
        self.page_index = 0
        self._root_layout = root

    def show_page(self, index):
        index = max(0, min(len(self.page_names) - 1, int(index)))
        self.page_index = index
        self.pages.setCurrentIndex(index)
        self.step_label.setText(f"Step {index + 1} of {len(self.page_names)}  •  {self.page_names[index]}")
        self.back_btn.setVisible(index > 0)
        self.next_btn.setVisible(index < len(self.page_names) - 1)
        # No Cancel button. On the last page Close stays on the right; Back is
        # always at the far left where Cancel used to be.
        self.close_btn.setVisible(index == len(self.page_names) - 1)


class DMCampaignManagerDialog(_WizardDialog):
    page_names = ("Campaign", "Characters", "Creation Rules")

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.campaigns = []
        self.current_campaign = None
        self.setWindowTitle("Campaign Manager")
        self.resize(900, 620)
        self.setMinimumSize(820, 560)
        self._setup_shell(
            "Campaign Manager",
            "Manage campaigns you DM, their characters, creation rules, and dashboards.",
        )
        self._build_campaign_page()
        self._build_characters_page()
        self._build_rules_page()
        self.reload_campaigns()
        self.show_page(0)

    def _build_campaign_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 12, 18, 4)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel("Campaign Setup")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("Choose a campaign you DM, create a new one, or open one of its dashboards.")
        intro.setObjectName("SectionText")
        box.addWidget(intro)
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnStretch(1, 1)
        form.addWidget(QLabel("Selected Campaign"), 0, 0)
        row = QHBoxLayout()
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        row.addWidget(self.campaign_combo, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload_campaigns)
        _fit_button(refresh)
        row.addWidget(refresh)
        form.addLayout(row, 0, 1)
        form.addWidget(QLabel("Campaign Details"), 1, 0)
        self.meta = QLabel("No DM campaigns yet.")
        self.meta.setWordWrap(True)
        form.addWidget(self.meta, 1, 1)
        form.addWidget(QLabel("Campaign Actions"), 2, 0)
        actions = QHBoxLayout()
        new_btn = QPushButton("New Campaign")
        new_btn.clicked.connect(self.create_campaign)
        self.dm_dashboard_btn = QPushButton("Open DM Dashboard")
        self.dm_dashboard_btn.clicked.connect(self.open_dm_dashboard)
        self.party_dashboard_btn = QPushButton("Open Party Dashboard")
        self.party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        for button in (new_btn, self.dm_dashboard_btn, self.party_dashboard_btn):
            _fit_button(button)
            actions.addWidget(button)
        actions.addStretch()
        form.addLayout(actions, 2, 1)
        box.addLayout(form)
        self.pages.addWidget(page)

    def _build_characters_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 12, 18, 4)
        box.setSpacing(8)
        heading = QLabel("Campaign Characters")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("Live campaign characters. Removing one hides it from the campaign without deleting the player's local character file.")
        intro.setObjectName("SectionText")
        intro.setWordWrap(True)
        box.addWidget(intro)
        self.character_scroll = QScrollArea()
        self.character_scroll.setWidgetResizable(True)
        self.character_body = QWidget()
        self.character_layout = QVBoxLayout(self.character_body)
        self.character_layout.setContentsMargins(0, 2, 0, 2)
        self.character_layout.setSpacing(8)
        self.character_scroll.setWidget(self.character_body)
        box.addWidget(self.character_scroll, 1)
        self.pages.addWidget(page)

    def _build_rules_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 12, 18, 4)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel("Creation Rules")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("The same clean creation rules used when players create campaign characters.")
        intro.setObjectName("SectionText")
        box.addWidget(intro)
        self.rules_holder = QVBoxLayout()
        box.addLayout(self.rules_holder)
        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.clicked.connect(self.edit_rules)
        _fit_button(self.edit_rules_btn)
        edit_row = QHBoxLayout()
        edit_row.addWidget(self.edit_rules_btn)
        edit_row.addStretch()
        box.addLayout(edit_row)
        self.pages.addWidget(page)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child is not None:
                self._clear_layout(child)

    def reload_campaigns(self):
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaigns = []
        if self.service is not None:
            try:
                for campaign in self.service.list_campaigns():
                    if self.service.role_for_campaign(campaign.get("id")) == "dm":
                        campaign["role"] = "dm"
                        self.campaigns.append(campaign)
            except Exception as error:
                QMessageBox.warning(self, "Campaigns", str(error))
        for campaign in self.campaigns:
            self.campaign_combo.addItem(str(campaign.get("name") or "Unnamed Campaign"), campaign.get("id"))
        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self.campaign_combo.setCurrentIndex(0)
            self._campaign_changed(0)
        else:
            self.current_campaign = None
            self.meta.setText("No campaigns you DM yet.")
            self._refresh_characters()
            self._refresh_rules()
            self._update_action_state()

    def _campaign_changed(self, index):
        self.current_campaign = self.campaigns[index] if 0 <= index < len(self.campaigns) else None
        if self.current_campaign:
            self.meta.setText(
                f"Role: DM    •    Invite code: {self.current_campaign.get('invite_code') or ''}"
            )
        self._refresh_characters()
        self._refresh_rules()
        self._update_action_state()

    def _update_action_state(self):
        enabled = isinstance(self.current_campaign, dict)
        self.dm_dashboard_btn.setEnabled(enabled)
        self.party_dashboard_btn.setEnabled(enabled)
        self.edit_rules_btn.setEnabled(enabled)

    def _refresh_characters(self):
        self._clear_layout(self.character_layout)
        if not self.current_campaign or self.client is None:
            self.character_layout.addWidget(QLabel("No campaign selected."))
            self.character_layout.addStretch()
            return
        try:
            rows = self.client.list_campaign_characters(self.current_campaign["id"])
        except Exception as error:
            self.character_layout.addWidget(QLabel(f"Could not load characters: {error}"))
            self.character_layout.addStretch()
            return
        if not rows:
            label = QLabel("No characters have been saved to this campaign yet.")
            label.setObjectName("Muted")
            self.character_layout.addWidget(label)
            self.character_layout.addStretch()
            return
        for row in rows:
            state = _state_from_character_row(row)
            card = QFrame()
            card.setObjectName("Card")
            grid = QGridLayout(card)
            grid.setContentsMargins(13, 10, 13, 10)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(4)
            name = QLabel(str(state.get("name") or row.get("display_name") or "Unnamed Character"))
            name.setStyleSheet("font-size:15px; font-weight:900;")
            subtitle = QLabel(
                " • ".join(x for x in (str(state.get("species") or ""), f"Level {int(state.get('level') or 1)}") if state else "") if x)
            )
            subtitle.setObjectName("Muted")
            grid.addWidget(name, 0, 0, 1, 3)
            grid.addWidget(subtitle, 1, 0, 1, 3)
            hp = QLabel(f"HP  {_hp_text(state)}")
            at = QLabel(f"AT  {_at_text(state)}")
            hp.setStyleSheet("font-weight:800;")
            at.setStyleSheet("font-weight:800;")
            grid.addWidget(hp, 2, 0)
            grid.addWidget(at, 2, 1)
            remove = QPushButton("Remove from Campaign")
            remove.setObjectName("DangerButton")
            _fit_button(remove)
            remove.clicked.connect(lambda _checked=False, character_id=row.get("id"), display=name.text(): self.remove_character(character_id, display))
            grid.addWidget(remove, 2, 2, alignment=Qt.AlignmentFlag.AlignRight)
            self.character_layout.addWidget(card)
        self.character_layout.addStretch()

    def remove_character(self, campaign_character_id, display_name):
        answer = QMessageBox.question(
            self,
            "Remove Character",
            f"Remove {display_name} from this campaign?\n\nThis does not delete the player's local .didchar file or historical session snapshots.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.client._request_json(
                "POST",
                "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": str(campaign_character_id)},
            )
            if result is False:
                raise RuntimeError("The character could not be removed.")
        except Exception as error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
            return
        self._refresh_characters()

    def _refresh_rules(self):
        self._clear_layout(self.rules_holder)
        if not self.current_campaign:
            self.rules_holder.addWidget(QLabel("No campaign selected."))
            return
        self.rules_holder.addWidget(_build_rule_cards(self.current_campaign))

    def _choose_rules(self, campaign_name):
        box = QMessageBox(self)
        box.setWindowTitle("Campaign Creation Rules")
        box.setText("Design the campaign's rules now, or start from an existing .didtemplate file.")
        design = box.addButton("Design Rules", QMessageBox.ButtonRole.AcceptRole)
        existing = box.addButton("Use Existing Template", QMessageBox.ButtonRole.ActionRole)
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() == cancel:
            return None
        if box.clickedButton() == existing:
            return load_template_from_file(parent=self)
        template = CharacterTemplate(name=f"{campaign_name} Rules")
        editor = CampaignRulesEditorDialog(self, template=template)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        return editor.template

    def create_campaign(self):
        if self.service is None:
            return
        name, ok = QInputDialog.getText(self, "New Campaign", "Campaign name:")
        name = str(name or "").strip()
        if not ok or not name:
            return
        template = self._choose_rules(name)
        if template is None:
            return
        try:
            created = self.service.create_campaign(name, template)
        except Exception as error:
            QMessageBox.warning(self, "Create Campaign Failed", str(error))
            return
        QMessageBox.information(self, "Campaign Created", f"Invite code: {created.get('invite_code', '')}")
        self.reload_campaigns()
        for index, campaign in enumerate(self.campaigns):
            if str(campaign.get("id")) == str(created.get("id")):
                self.campaign_combo.setCurrentIndex(index)
                break

    def edit_rules(self):
        if not self.current_campaign or self.service is None:
            return
        editor = CampaignRulesEditorDialog(self, template=campaign_template(self.current_campaign))
        if editor.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            updated = self.service.update_campaign_template(self.current_campaign["id"], editor.template)
        except Exception as error:
            QMessageBox.warning(self, "Update Rules Failed", str(error))
            return
        self.current_campaign.update(updated)
        self._refresh_rules()

    def open_dm_dashboard(self):
        if not self.current_campaign or self.client is None:
            return
        try:
            launch_dm_dashboard(self.client, self.current_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open DM Dashboard Failed", str(error))

    def open_party_dashboard(self):
        if not self.current_campaign or self.client is None:
            return
        try:
            launch_party_dashboard(self.client, self.current_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open Party Dashboard Failed", str(error))


class PlayerCampaignsDialog(_WizardDialog):
    page_names = ("Campaign", "My Character & Sharing", "Creation Rules")

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.session_service = CampaignSessionService(self.client) if self.client else None
        self.dm_store = privacy_store_for_window(window)
        self.party_store = party_privacy_store_for_window(window)
        self.campaigns = []
        self.current_campaign = None
        self.inventory_dm_boxes = {}
        self.inventory_party_boxes = {}
        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        self.setWindowTitle("My Campaigns")
        self.resize(960, 680)
        self.setMinimumSize(860, 600)
        self._setup_shell(
            "My Campaigns",
            "Join campaigns you play in, manage your character, and choose what the DM and party can see.",
        )
        self._build_campaign_page()
        self._build_character_page()
        self._build_rules_page()
        self.reload_campaigns()
        pending = getattr(window, "_pending_campaign_character", None)
        if isinstance(pending, dict):
            self._select_campaign_id(pending.get("campaign_id"))
            self.show_page(1)
        else:
            self.show_page(0)

    def _build_campaign_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 12, 18, 4)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel("Campaign")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("Choose a campaign you joined as a player, or join a new campaign with its invite code.")
        intro.setObjectName("SectionText")
        box.addWidget(intro)
        form = QGridLayout()
        form.setHorizontalSpacing(10)
        form.setVerticalSpacing(10)
        form.setColumnMinimumWidth(0, 120)
        form.setColumnStretch(1, 1)
        form.addWidget(QLabel("Selected Campaign"), 0, 0)
        row = QHBoxLayout()
        self.campaign_combo = QComboBox()
        self.campaign_combo.currentIndexChanged.connect(self._campaign_changed)
        row.addWidget(self.campaign_combo, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.reload_campaigns)
        _fit_button(refresh)
        row.addWidget(refresh)
        form.addLayout(row, 0, 1)
        form.addWidget(QLabel("Membership"), 1, 0)
        self.meta = QLabel("No player campaigns yet.")
        form.addWidget(self.meta, 1, 1)
        form.addWidget(QLabel("Actions"), 2, 0)
        actions = QHBoxLayout()
        join_btn = QPushButton("Join Campaign")
        join_btn.clicked.connect(self.join_campaign)
        self.party_dashboard_btn = QPushButton("Open Party Dashboard")
        self.party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        for button in (join_btn, self.party_dashboard_btn):
            _fit_button(button)
            actions.addWidget(button)
        actions.addStretch()
        form.addLayout(actions, 2, 1)
        box.addLayout(form)
        self.pages.addWidget(page)

    def _build_character_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 10, 18, 4)
        box.setSpacing(7)
        heading = QLabel("My Character")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("Create with the campaign's rules, edit normally on the sheet, then save the finished character to the campaign.")
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

        sharing = QFrame()
        sharing.setObjectName("Field")
        grid = QGridLayout(sharing)
        grid.setContentsMargins(12, 9, 12, 9)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(3)
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

        for key, label_text in (("improvements", "Improvements"), ("portrait", "Portrait"), ("inventory", "Inventory"), ("notes", "Notes")):
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

        for toggle in (self.dm_inventory_box, self.party_boxes["inventory"], self.dm_notes_box, self.party_boxes["notes"]):
            toggle.toggled.connect(self._refresh_detail_visibility)

        self.pages.addWidget(page)

    def _build_selection_section(self, title, kind):
        frame = QFrame()
        frame.setObjectName("Field")
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 8, 12, 8)
        heading = QHBoxLayout()
        name = QLabel(title)
        name.setStyleSheet("font-weight:900;")
        heading.addWidget(name)
        heading.addStretch()
        heading.addWidget(QLabel("DM"))
        spacer = QWidget()
        spacer.setFixedWidth(18)
        heading.addWidget(spacer)
        heading.addWidget(QLabel("Party"))
        outer.addLayout(heading)
        body = QVBoxLayout()
        body.setSpacing(2)
        setattr(self, f"{kind}_selection_layout", body)
        outer.addLayout(body)
        frame.setVisible(False)
        return frame

    def _build_rules_page(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(18, 12, 18, 4)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel("Creation Rules")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel("These rules are set by the DM and are read-only for players.")
        intro.setObjectName("SectionText")
        box.addWidget(intro)
        self.rules_holder = QVBoxLayout()
        box.addLayout(self.rules_holder)
        self.pages.addWidget(page)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child is not None:
                self._clear_layout(child)

    def reload_campaigns(self):
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        self.campaigns = []
        if self.service is not None:
            try:
                for campaign in self.service.list_campaigns():
                    if self.service.role_for_campaign(campaign.get("id")) == "player":
                        campaign["role"] = "player"
                        self.campaigns.append(campaign)
            except Exception as error:
                QMessageBox.warning(self, "My Campaigns", str(error))
        for campaign in self.campaigns:
            self.campaign_combo.addItem(str(campaign.get("name") or "Unnamed Campaign"), campaign.get("id"))
        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self.campaign_combo.setCurrentIndex(0)
            self._campaign_changed(0)
        else:
            self.current_campaign = None
            self.meta.setText("You have not joined a campaign as a player yet.")
            self._refresh_character_page()
            self._refresh_rules()

    def _select_campaign_id(self, campaign_id):
        for index, campaign in enumerate(self.campaigns):
            if str(campaign.get("id")) == str(campaign_id):
                self.campaign_combo.setCurrentIndex(index)
                self._campaign_changed(index)
                return

    def _campaign_changed(self, index):
        self.current_campaign = self.campaigns[index] if 0 <= index < len(self.campaigns) else None
        self.meta.setText("Role: Player" if self.current_campaign else "No player campaign selected")
        self.party_dashboard_btn.setEnabled(bool(self.current_campaign))
        self._refresh_character_page()
        self._refresh_rules()

    def _refresh_character_page(self):
        character = getattr(self.window, "character", None)
        name = str(getattr(character, "name", "") or "Unnamed Character")
        progression = getattr(character, "progression", None)
        level = int(getattr(progression, "level", 1) or 1)
        species = str(getattr(character, "species", "") or "")
        self.character_name.setText(name)
        self.character_hint.setText(" • ".join(x for x in (species, f"Level {level}") if x))
        link = self._current_link()
        self.sync_label.setText("Connected" if link else "Not connected")
        self.unlink_btn.setEnabled(bool(link))
        self.roll_share_box.blockSignals(True)
        self.roll_share_box.setEnabled(bool(link))
        if link and self.session_service is not None:
            try:
                self.roll_share_box.setChecked(self.session_service.get_roll_sharing(link.get("campaign_character_id")))
            except Exception:
                self.roll_share_box.setChecked(True)
        else:
            self.roll_share_box.setChecked(False)
        self.roll_share_box.blockSignals(False)
        self._load_sharing_preferences()
        self._populate_inventory_notes()
        self._refresh_detail_visibility()

    def _current_link(self):
        if not self.current_campaign or self.client is None:
            return None
        character = getattr(self.window, "character", None)
        character_id = str(getattr(character, "id", "") or "").strip()
        if not character_id:
            return None
        try:
            link = self.client.get_character_link(character_id)
        except Exception:
            return None
        if isinstance(link, dict) and str(link.get("campaign_id")) == str(self.current_campaign.get("id")):
            return link
        return None

    def _load_sharing_preferences(self):
        if not self.current_campaign:
            return
        character_id = str(getattr(self.window.character, "id", "") or "")
        campaign_id = str(self.current_campaign.get("id") or "")
        dm = normalize_privacy_preferences(self.dm_store.get(campaign_id, character_id))
        party = normalize_party_preferences(self.party_store.get(campaign_id, character_id))
        self.dm_improvements_box.setChecked(dm["share_improvements"])
        self.dm_portrait_box.setChecked(dm["share_portrait"])
        self.dm_inventory_box.setChecked(dm["share_inventory"])
        self.dm_notes_box.setChecked(dm["share_notes"])
        for key in ("hp", "at", "abilities", "improvements", "portrait", "inventory", "notes"):
            self.party_boxes[key].setChecked(party[f"share_{key}"])
        self._dm_prefs = dm
        self._party_prefs = party

    def _populate_inventory_notes(self):
        self._clear_layout(self.inventory_selection_layout)
        self._clear_layout(self.notes_selection_layout)
        self.inventory_dm_boxes = {}
        self.inventory_party_boxes = {}
        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        inventory = list(getattr(getattr(self.window.character, "inventory", None), "list_of_items", []) or [])
        if not inventory:
            muted = QLabel("No inventory items on this character.")
            muted.setObjectName("Muted")
            self.inventory_selection_layout.addWidget(muted)
        else:
            for item in inventory:
                item_id = str(getattr(item, "id", "") or "").strip()
                if not item_id:
                    continue
                row = QHBoxLayout()
                name = QLabel(str(getattr(item, "name", "") or "Unnamed item"))
                row.addWidget(name, 1)
                dm = QCheckBox()
                party = QCheckBox()
                dm.setChecked(item_id in set(self._dm_prefs.get("inventory_item_ids", [])))
                party.setChecked(item_id in set(self._party_prefs.get("inventory_item_ids", [])))
                self.inventory_dm_boxes[item_id] = dm
                self.inventory_party_boxes[item_id] = party
                row.addWidget(dm)
                row.addWidget(party)
                self.inventory_selection_layout.addLayout(row)
        notes = list(getattr(getattr(self.window.character, "notes", None), "list_of_notes", []) or [])
        if not notes:
            muted = QLabel("No notes on this character.")
            muted.setObjectName("Muted")
            self.notes_selection_layout.addWidget(muted)
        else:
            for note in notes:
                note_id = str(getattr(note, "id", "") or "").strip()
                if not note_id:
                    continue
                row = QHBoxLayout()
                title = str(getattr(note, "title", "") or "Untitled note")
                name = QLabel(title)
                row.addWidget(name, 1)
                dm = QCheckBox()
                party = QCheckBox()
                dm.setChecked(note_id in set(self._dm_prefs.get("note_ids", [])))
                party.setChecked(note_id in set(self._party_prefs.get("note_ids", [])))
                self.note_dm_boxes[note_id] = dm
                self.note_party_boxes[note_id] = party
                row.addWidget(dm)
                row.addWidget(party)
                self.notes_selection_layout.addLayout(row)

    def _refresh_detail_visibility(self):
        self.inventory_detail.setVisible(self.dm_inventory_box.isChecked() or self.party_boxes["inventory"].isChecked())
        self.notes_detail.setVisible(self.dm_notes_box.isChecked() or self.party_boxes["notes"].isChecked())

    def apply_sharing(self):
        if not self.current_campaign:
            return
        campaign_id = str(self.current_campaign.get("id") or "")
        character_id = str(getattr(self.window.character, "id", "") or "")
        dm = {
            "share_improvements": self.dm_improvements_box.isChecked(),
            "share_portrait": self.dm_portrait_box.isChecked(),
            "share_inventory": self.dm_inventory_box.isChecked(),
            "inventory_item_ids": [key for key, box in self.inventory_dm_boxes.items() if box.isChecked()],
            "share_notes": self.dm_notes_box.isChecked(),
            "note_ids": [key for key, box in self.note_dm_boxes.items() if box.isChecked()],
        }
        party = {
            "share_hp": self.party_boxes["hp"].isChecked(),
            "share_at": self.party_boxes["at"].isChecked(),
            "share_abilities": self.party_boxes["abilities"].isChecked(),
            "share_improvements": self.party_boxes["improvements"].isChecked(),
            "share_portrait": self.party_boxes["portrait"].isChecked(),
            "share_inventory": self.party_boxes["inventory"].isChecked(),
            "inventory_item_ids": [key for key, box in self.inventory_party_boxes.items() if box.isChecked()],
            "share_notes": self.party_boxes["notes"].isChecked(),
            "note_ids": [key for key, box in self.note_party_boxes.items() if box.isChecked()],
        }
        try:
            self.dm_store.set(campaign_id, character_id, dm)
            self.party_store.set(campaign_id, character_id, party)
            sync_current_character_now(self.window)
        except Exception as error:
            QMessageBox.warning(self, "Update Sharing Failed", str(error))
            return
        QMessageBox.information(self, "Sharing Updated", "Your DM and Party Dashboard sharing choices were updated.")

    def _roll_sharing_changed(self, enabled):
        link = self._current_link()
        if not link or self.session_service is None:
            return
        try:
            self.session_service.set_roll_sharing(link.get("campaign_character_id"), bool(enabled))
        except Exception as error:
            QMessageBox.warning(self, "Update Roll Sharing Failed", str(error))

    def join_campaign(self):
        if self.service is None:
            return
        code, ok = QInputDialog.getText(self, "Join Campaign", "Invite code:")
        code = str(code or "").strip()
        if not ok or not code:
            return
        display_name, ok = QInputDialog.getText(self, "Join Campaign", "Your display name:", text=str(getattr(self.window.character, "name", "") or "Player"))
        if not ok:
            return
        try:
            joined = self.service.join_campaign(code, display_name)
        except Exception as error:
            QMessageBox.warning(self, "Join Campaign Failed", str(error))
            return
        self.reload_campaigns()
        self._select_campaign_id(joined.get("id"))

    def create_character(self):
        if not self.current_campaign:
            return
        try:
            if not _replace_current_character(self.window, campaign_template(self.current_campaign)):
                return
        except Exception as error:
            QMessageBox.warning(self, "Create Campaign Character Failed", str(error))
            return
        self.window._pending_campaign_character = {
            "campaign_id": str(self.current_campaign.get("id") or ""),
            "campaign_name": str(self.current_campaign.get("name") or "Campaign"),
            "character_id": str(getattr(self.window.character, "id", "") or ""),
        }
        self.accept()

    def save_to_campaign(self):
        if not self.current_campaign or self.client is None:
            return
        campaign_id = str(self.current_campaign.get("id") or "")
        window = self.window
        self.accept()

        def save_and_link():
            try:
                window.save_current_character()
            except Exception as error:
                QMessageBox.warning(window, "Save Character Failed", str(error))
                return
            if not getattr(window, "current_character_filepath", None) or getattr(window, "unsaved_changes", False):
                return
            try:
                dm_state = build_window_shared_state(window, campaign_id=campaign_id)
                record = self.client.link_character(campaign_id, dm_state, remember=True)
                party_state = build_window_party_state(window, campaign_id=campaign_id)
                upload_party_state(self.client, campaign_id, record["id"], party_state)
                restore_campaign_connection(window)
                schedule_campaign_state_sync(window)
                sync_current_character_now(window)
            except Exception as error:
                QMessageBox.warning(window, "Save to Campaign Failed", str(error))
                return
            pending = getattr(window, "_pending_campaign_character", None)
            if isinstance(pending, dict) and str(pending.get("character_id")) == str(getattr(window.character, "id", "")):
                try:
                    delattr(window, "_pending_campaign_character")
                except Exception:
                    pass
            QMessageBox.information(window, "Saved to Campaign", "The character was saved locally and connected to the campaign.")
        QTimer.singleShot(0, save_and_link)

    def unlink_character(self):
        if self.client is None:
            return
        character_id = str(getattr(self.window.character, "id", "") or "")
        if not character_id:
            return
        self.client.unlink_local_character(character_id)
        restore_campaign_connection(self.window)
        self._refresh_character_page()

    def _refresh_rules(self):
        while self.rules_holder.count():
            item = self.rules_holder.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.current_campaign:
            self.rules_holder.addWidget(_build_rule_cards(self.current_campaign))
        else:
            self.rules_holder.addWidget(QLabel("No campaign selected."))

    def open_party_dashboard(self):
        if not self.current_campaign or self.client is None:
            return
        try:
            launch_party_dashboard(self.client, self.current_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open Party Dashboard Failed", str(error))


def open_dm_campaign_manager(window):
    dialog = DMCampaignManagerDialog(window)
    dialog.exec()
    return dialog


def open_player_campaigns(window):
    dialog = PlayerCampaignsDialog(window)
    dialog.exec()
    return dialog
