"""Choose standalone or campaign character creation before guided character editing."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QMessageBox, QStackedWidget, QWidget, QFormLayout, QFrame,
)
from ui_theme import (
    FANTASY_DIALOG_QSS, make_negative_button, make_positive_button,
    set_themed_stylesheet,
)


# Use the same warm parchment, gold trim and Georgia type as the Campaign
# Manager and other DID dialogs. set_themed_stylesheet translates the colors
# to the existing dark palette, without any custom dark-mode state.
NEW_CHARACTER_QSS = FANTASY_DIALOG_QSS + """
QDialog#CampaignCreationWizard { background-color: #f7f1e5; }
QLabel#WizardTitle {
    color: #25190f; font-family: Georgia; font-size: 22px; font-weight: 900;
}
QLabel#WizardSubtitle {
    color: #765d34; font-family: Georgia; font-size: 12px;
}
QLabel#FieldTitle {
    color: #25190f; font-family: Georgia; font-size: 13px; font-weight: 800;
}
QLabel#WizardHint {
    color: #6c5428; font-family: Georgia; font-size: 12px;
}
QFrame#WizardCard {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 12px;
}
QFrame#WizardBottomRule {
    background-color: #d9bd82;
    border: none;
    max-height: 1px;
}
QComboBox { min-height: 36px; }
QLineEdit { min-height: 34px; }
"""
from campaign_runtime import campaign_client
from campaign_template import CampaignTemplateService, campaign_template
from campaign_ui import _replace_current_character


class CampaignCreationWizard(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.campaigns = []
        self.setObjectName('CampaignCreationWizard')
        self.setWindowTitle('New Character')
        self.setMinimumWidth(470)
        self.resize(570, 340)
        set_themed_stylesheet(self, NEW_CHARACTER_QSS)

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 18)
        root.setSpacing(12)

        title = QLabel('New Character')
        title.setObjectName('WizardTitle')
        root.addWidget(title)
        subtitle = QLabel('Choose how this character will be used.')
        subtitle.setObjectName('WizardSubtitle')
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName('WizardCard')
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setSpacing(11)

        field_title = QLabel('Where will this character be used?')
        field_title.setObjectName('FieldTitle')
        card_layout.addWidget(field_title)

        self.mode = QComboBox(card)
        self.mode.setMinimumHeight(38)
        self.mode.addItem('Standalone character', 'standalone')
        self.mode.addItem('Character for an existing campaign', 'existing')
        self.mode.addItem('Join a campaign and create a character', 'join')
        card_layout.addWidget(self.mode)

        self.pages = QStackedWidget(card)
        self.pages.setMinimumHeight(98)
        card_layout.addWidget(self.pages)

        standalone = QWidget()
        s = QVBoxLayout(standalone)
        s.setContentsMargins(0, 4, 0, 0)
        s.setAlignment(Qt.AlignmentFlag.AlignTop)
        standalone_hint = QLabel('Create a normal character without campaign restrictions.')
        standalone_hint.setObjectName('WizardHint')
        standalone_hint.setWordWrap(True)
        s.addWidget(standalone_hint)
        self.pages.addWidget(standalone)

        existing = QWidget()
        e = QFormLayout(existing)
        e.setContentsMargins(0, 4, 0, 0)
        e.setSpacing(9)
        self.campaign_choice = QComboBox()
        self.campaign_choice.setMinimumHeight(38)
        e.addRow('Campaign:', self.campaign_choice)
        self.pages.addWidget(existing)

        join = QWidget()
        j = QFormLayout(join)
        j.setContentsMargins(0, 4, 0, 0)
        j.setSpacing(9)
        self.invite_code = QLineEdit()
        self.invite_code.setPlaceholderText('Campaign invitation code')
        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText('Player')
        j.addRow('Invitation code:', self.invite_code)
        j.addRow('Your display name:', self.display_name)
        self.pages.addWidget(join)

        self.mode.currentIndexChanged.connect(self.pages.setCurrentIndex)
        root.addWidget(card, 1)

        rule = QFrame(self)
        rule.setObjectName('WizardBottomRule')
        rule.setFixedHeight(1)
        root.addWidget(rule)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(10)
        cancel = QPushButton('Cancel')
        cancel.setMinimumSize(104, 38)
        make_negative_button(cancel)
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.clicked.connect(self.reject)
        proceed = QPushButton('Continue')
        proceed.setObjectName('PrimaryButton')
        proceed.setMinimumSize(112, 38)
        make_positive_button(proceed)
        proceed.setCursor(Qt.CursorShape.PointingHandCursor)
        proceed.setDefault(True)
        proceed.clicked.connect(self.proceed)
        buttons.addWidget(cancel)
        buttons.addStretch()
        buttons.addWidget(proceed)
        root.addLayout(buttons)
        self._load_campaigns()

    def _load_campaigns(self):
        if not self.service:
            return
        try:
            for campaign in self.service.list_campaigns():
                if self.service.role_for_campaign(campaign.get('id')) == 'player':
                    self.campaigns.append(campaign)
                    self.campaign_choice.addItem(
                        str(campaign.get('name') or 'Unnamed campaign'), campaign.get('id'))
        except Exception as error:
            QMessageBox.warning(self, 'Campaigns Unavailable', str(error))

    def proceed(self):
        mode = self.mode.currentData()
        if mode == 'standalone':
            self.accept()
            self.window.new_character_from_ui()
            return
        if self.service is None:
            QMessageBox.warning(self, 'Campaign Connection Required',
                'Configure your campaign connection before creating a campaign character.')
            return
        try:
            if mode == 'join':
                code = self.invite_code.text().strip()
                if not code:
                    QMessageBox.warning(self, 'Invitation Code Required', 'Enter a campaign invitation code.')
                    return
                campaign = self.service.join_campaign(code, self.display_name.text().strip() or 'Player')
            else:
                index = self.campaign_choice.currentIndex()
                if index < 0:
                    QMessageBox.warning(self, 'No Campaign', 'Join a campaign first, or enter an invitation code.')
                    return
                campaign = self.campaigns[index]
            template = campaign_template(campaign)
            if not _replace_current_character(self.window, template):
                return
            self.window._pending_campaign_character = {
                'campaign_id': str(campaign['id']),
                'campaign_name': str(campaign.get('name') or 'Campaign'),
                'character_id': str(self.window.character.id),
            }
        except Exception as error:
            QMessageBox.warning(self, 'Campaign Character Creation Failed', str(error))
            return
        self.accept()
