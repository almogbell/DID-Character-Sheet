"""Small themed handoff after joining without a named character.

The existing campaign creation/admission protocol is left intact. Choosing
Later does not replace or save the character.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QMessageBox
from ui_theme import set_themed_stylesheet

JOIN_QSS = """
QDialog { background: #f7f1e5; }
QLabel { background:transparent; color:#25190f; font-family:Georgia; }
QPushButton { min-height:34px; border:1px solid #c79a3b;
    border-radius:9px; background:#fffdf7; color:#25190f;
    font: 900 12px Georgia; padding:4px 12px; }
QPushButton#PrimaryButton { background:#d5edf9; border-color:#94722d; }
QPushButton:hover { background:#fff1d6; }
"""


def _ask_create(parent):
    dlg = QDialog(parent)
    dlg.setWindowTitle('Campaign Joined')
    dlg.setModal(True)
    dlg.setFixedWidth(500)
    set_themed_stylesheet(dlg, JOIN_QSS)
    layout = QVBoxLayout(dlg)
    layout.setContentsMargins(20, 18, 20, 17)
    layout.setSpacing(11)
    heading = QLabel('Campaign joined!')
    heading.setStyleSheet('font-size:18px;font-weight:900;')
    layout.addWidget(heading)
    details = QLabel(
        "You don't have a named character open. Create a character using "
        "this campaign's rules now? After you name and save it, the app "
        "will submit it to the DM, or request approval if needed."
    )
    details.setWordWrap(True)
    layout.addWidget(details)
    actions = QHBoxLayout()
    actions.setSpacing(9)
    later = QPushButton('Later')
    create = QPushButton('Create Character')
    create.setObjectName('PrimaryButton')
    later.clicked.connect(dlg.reject)
    create.clicked.connect(dlg.accept)
    actions.addWidget(later)
    actions.addStretch(1)
    actions.addWidget(create)
    layout.addLayout(actions)
    return dlg.exec() == QDialog.DialogCode.Accepted


def offer_create_character_after_join(parent, window, campaign, *, on_created=None):
    """Return True only when the existing character-creation handoff succeeds."""
    if not _ask_create(parent):
        return False
    try:
        from campaign_template import campaign_template
        from campaign_ui import _replace_current_character
        if not _replace_current_character(window, campaign_template(campaign)):
            return False
        character_id = str(getattr(getattr(window, 'character', None), 'id', '') or '')
        campaign_id = str(campaign.get('id') or '').strip()
        if not character_id or not campaign_id:
            raise RuntimeError('The new character or joined campaign has no ID.')
        window._pending_campaign_character = {
            'campaign_id': campaign_id,
            'campaign_name': str(campaign.get('name') or 'Campaign'),
            'character_id': character_id,
        }
    except Exception as error:
        QMessageBox.warning(parent, 'Create Campaign Character Failed', str(error))
        return False
    if on_created is not None:
        on_created()
    return True
