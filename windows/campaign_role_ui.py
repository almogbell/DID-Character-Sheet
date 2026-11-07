from __future__ import annotations

from pathlib import Path
import copy
from queue import Empty, SimpleQueue
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Qt, QTimer, QRunnable, QThreadPool, QRect
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from campaign_dashboard_bridge import open_dm_dashboard as launch_dm_dashboard
from campaign_join_flow import join_campaign_and_publish, JoinedButCharacterNotPublished
from campaign_join_ui import offer_create_character_after_join
from campaign_admission import admit_character
from campaign_party import (
    build_window_party_state,
    normalize_party_preferences,
    party_privacy_store_for_window,
    upload_party_state,
)
from campaign_party_bridge import open_party_dashboard as launch_party_dashboard
from campaign_player_reveals import load_player_reveals, format_entries, format_effects
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
from discord_integration_ui import DiscordIntegrationDialog
from discord_integration import (
    load_config as load_discord_config,
    remove_binding as remove_discord_binding,
    save_config as save_discord_config,
)


ROLE_QSS = """
QDialog { background-color: #f7f1e5; }
QLabel { background: transparent; border: none; color: #25190f; font-family: Georgia; }
QLabel#PageTitle { font-size: 27px; font-weight: 900; }
QLabel#PageSubtitle, QLabel#SectionText {
    color: #765d34; font-size: 12px; font-weight: 700;
}
QLabel#StepBar {
    background-color: #fffdf7; border: 1px solid #c79a3b; border-radius: 10px;
    color: #6c5428; font-size: 12px; font-weight: 800; padding: 5px 9px;
}
QLabel#SectionTitle { font-size: 21px; font-weight: 900; }
QLabel#FieldLabel { font-size: 12px; }
QLabel#Muted { color: #765d34; font-size: 11px; }
QFrame#Field, QFrame#RuleCard, QFrame#ComboShell {
    background-color: #fffdf7; border: 1px solid #d9bd82; border-radius: 10px;
}
QFrame#Card {
    background-color: #fffdf7;
    border: 1px solid #c79a3b;
    border-radius: 10px;
}
QFrame#MiniStat {
    background-color: #fff7e8;
    border: 1px solid #d7b56d;
    border-radius: 10px;
}
QFrame#ComboShell {
    border-color: #c79a3b;
    border-radius: 10px;
}
QFrame#ComboShell QComboBox {
    min-height: 0px;
    max-height: 34px;
    background: transparent;
    border: none;
    padding: 2px 7px 2px 10px;
}
QPushButton#ComboMarkButton {
    min-height: 0px;
    background: #d8edf7;
    border: none;
    border-left: 1px solid #c79a3b;
    border-top-right-radius: 9px;
    border-bottom-right-radius: 9px;
    color: #6c5428;
    font-family: Georgia;
    font-size: 11px;
    font-weight: 900;
    padding: 0px;
}
QPushButton#ComboMarkButton:hover {
    background: #e8f5fb;
    border: none;
    border-left: 1px solid #a87824;
    color: #25190f;
}
QComboBox {
    min-height: 34px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    padding: 4px 10px;
}
QComboBox::drop-down { border:none; width:0px; }
QComboBox::down-arrow { image:none; width:0px; height:0px; }

QComboBox QAbstractItemView {
    background-color: #fffdf7;
    color: #25190f;
    border: 1px solid #c79a3b;
    selection-background-color: #fff1d6;
    selection-color: #25190f;
    outline: none;
}

QPushButton#RemoveXButton {
    min-height: 0px;
    background: transparent;
    border: none;
    color: #8a5a18;
    font-family: Georgia;
    font-size: 14px;
    font-weight: 900;
    padding: 0px;
}

QPushButton#RemoveXButton:hover {
    background: transparent;
    border: none;
    color: #b24a2c;
}

QPushButton#CompactButton {
    min-height: 28px;
    max-height: 30px;
    border-radius: 7px;
    padding: 2px 9px;
    font-size: 11px;
}
QPushButton#RefreshButton {
    min-height: 24px;
    max-height: 26px;
    border-radius: 7px;
    padding: 0px 7px;
    font-size: 10px;
}

QLabel#HPLabel { color: #9b4a42; font-size: 11px; font-weight: 800; }
QLabel#HPValue { color: #8a342d; font-size: 12px; font-weight: 900; }
QLabel#ATLabel { color: #665394; font-size: 11px; font-weight: 800; }
QLabel#ATValue { color: #4f3d80; font-size: 12px; font-weight: 900; }
QPushButton#InviteCodeButton {
    min-height: 0px;
    background: transparent;
    border: none;
    color: #6c5428;
    text-decoration: underline;
    padding: 0px 2px;
    font-size: 12px;
}
QPushButton#InviteCodeButton:hover { color: #25190f; background: transparent; border: none; }
QMenu {
    background-color: #fffdf7;
    color: #25190f;
    border: 1px solid #c79a3b;
    border-radius: 7px;
    padding: 4px;
    font-family: Georgia;
    font-size: 12px;
}
QMenu::item { padding: 7px 22px 7px 10px; border-radius: 5px; }
QMenu::item:selected { background-color: #fff1d6; color: #25190f; }
QLabel#CopySuccess { color: #3f7d4a; font-size: 15px; font-weight: 900; }
QLabel#InviteSuccess { color: #4e79a8; font-size: 15px; font-weight: 900; }
QLineEdit {
    min-height: 34px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    padding: 4px 9px;
}
QPushButton {
    min-height: 32px; background-color: #fffdf7; border: 1px solid #c79a3b;
    border-radius: 9px; color: #25190f; font-family: Georgia; font-size: 12px;
    font-weight: 800; padding: 4px 11px;
}
QPushButton:hover { background-color: #fff4df; border-color: #a87824; }
QPushButton#PrimaryButton { background-color: #d8edf7; }
QPushButton#PrimaryButton:hover { background-color: #e8f5fb; }
QPushButton#DangerButton { color: #aa0000; border-color: #cba79d; }
QPushButton:disabled { color: #9b9388; border-color: #d8ccb5; background-color: #eee9df; }
QCheckBox {
    color: #25190f; font-family: Georgia; font-size: 12px; spacing: 8px;
    min-height: 28px; padding-top: 2px; padding-bottom: 2px;
}
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { background: transparent; border: none; }
/* DID114_CAMPAIGN_SCROLLBAR: matches the character sheet. */
QScrollBar:vertical { background: transparent; border: none; width: 9px; margin: 0px; }
QScrollBar::handle:vertical { background: #d9bd82; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #c6a15d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; height: 0px; width: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }

"""


ABILITY_ORDER = ("agility", "strength", "finesse", "instinct", "presence", "knowledge")
CAMPAIGN_NAME_MAX_LENGTH = 32


def _fit_button(button):
    # Match the Character Creation Template buttons while leaving enough room
    # for bold Georgia text on Windows DPI scaling. The button wraps snugly
    # around the whole label instead of clipping its first/last characters.
    button.ensurePolished()
    text_width = button.fontMetrics().horizontalAdvance(button.text())
    button.setMinimumHeight(40)
    button.setFixedWidth(max(78, text_width + 56))
    button.setCursor(Qt.CursorShape.PointingHandCursor)


def _build_combo_shell(combo):
    shell = QFrame()
    shell.setObjectName("ComboShell")

    shell.setFixedHeight(40)
    layout = QHBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    layout.addWidget(combo, 1)

    mark = QPushButton("v")
    mark.setObjectName("ComboMarkButton")
    mark.setFixedSize(38, 38)
    mark.setCursor(Qt.CursorShape.PointingHandCursor)
    mark.setToolTip("Choose campaign")
    mark.clicked.connect(combo.showPopup)
    layout.addWidget(mark)

    return shell


def _build_stat_chip(label_text, value_text):
    chip = QFrame()
    chip.setObjectName("MiniStat")
    chip.setFixedWidth(150)
    chip.setFixedHeight(46)

    layout = QHBoxLayout(chip)
    layout.setContentsMargins(11, 6, 11, 6)
    layout.setSpacing(8)

    label = QLabel(str(label_text))
    label.setStyleSheet(
        "color:#765d34; font-size:11px; font-weight:800;"
    )

    value = QLabel(str(value_text))
    value.setStyleSheet(
        "color:#25190f; font-size:16px; font-weight:900;"
    )

    layout.addWidget(label)
    layout.addStretch()
    layout.addWidget(value)

    return chip


def _report_join_publication(parent, publication):
    """Show the outcome without suggesting cross-PC .didchar transfers."""
    if publication.status == "needs_character":
        QMessageBox.information(
            parent, "Campaign Joined",
            "You joined the campaign. No named character is currently open to "
            "send to the DM. Create a character using the campaign rules, then "
            "save it. The first save automatically sends it to the campaign."
        )
    elif publication.status == "approval_pending":
        details = "\n".join(f"• {item}" for item in publication.mismatches)
        _show_campaign_approval_notice(parent, publication)
    elif publication.status == "linked_elsewhere":
        QMessageBox.warning(
            parent, "Campaign Joined — Character Not Sent",
            "The current character is already connected to another campaign. "
            "It was not silently moved. Open a character for this campaign "
            "or explicitly choose Save to Campaign."
        )
    elif publication.warning:
        QMessageBox.warning(parent, "Campaign Joined — Partial Sharing", publication.warning)
    else:
        QMessageBox.information(
            parent, "Character Sent to DM",
            f"{publication.character_name} has joined this campaign and was "
            "sent to the DM. Subsequent character changes will synchronize "
            "automatically."
        )


def _show_campaign_approval_notice(parent, publication):
    """A readable, non-alarming explanation of a pending DM exception."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Character Submitted for Approval")
    dialog.setModal(True)
    dialog.setMinimumWidth(480)
    dialog.resize(540, 285)
    set_themed_stylesheet(dialog, ROLE_QSS)
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(12)
    heading = QLabel("Waiting for DM approval")
    heading.setStyleSheet("font-size:21px;font-weight:900;")
    layout.addWidget(heading)
    intro = QLabel(
        f"{publication.character_name} was submitted to your DM. "
        "It is not yet admitted to the campaign."
    )
    intro.setWordWrap(True)
    layout.addWidget(intro)
    differences = []
    for item in publication.mismatches:
        text = str(item).replace(
            "Character was not created with Creation Rules enabled.",
            "This existing character was not created from the campaign's character-creation template.",
        )
        differences.append("• " + text)
    if differences:
        details = QLabel("Why approval is needed:\n" + "\n".join(differences))
        details.setObjectName("Muted")
        details.setWordWrap(True)
        layout.addWidget(details)
    closing = QLabel("You can continue using the character locally while you wait. "
                     "Party Dashboard and Campaign Info are locked until approval.")
    closing.setWordWrap(True)
    layout.addWidget(closing)
    layout.addStretch(1)
    buttons = QHBoxLayout()
    buttons.addStretch(1)
    ok = QPushButton("Got it")
    ok.setObjectName("HubPrimary")
    ok.clicked.connect(dialog.accept)
    buttons.addWidget(ok)
    layout.addLayout(buttons)
    dialog.exec()


def _campaign_invite_text(campaign):
    if not isinstance(campaign, dict):
        return ""

    name = str(campaign.get("name") or "Campaign").strip()
    code = str(campaign.get("invite_code") or "").strip()

    if not code:
        return ""

    return (
        f"You've been invited to join my DID Character Sheet campaign: {name}.\n\n"
        "Open DID Character Sheet and choose Campaigns > Join Campaign.\n"
        f"Invite code: {code}"
    )


def _copy_text_silent(text_value):
    value = str(text_value or "").strip()
    if not value:
        return False
    QApplication.clipboard().setText(value)
    return True


def _text_prompt(parent, title, label_text, default_text=""):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.resize(420, 175)
    set_themed_stylesheet(dialog, ROLE_QSS)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(10)
    label = QLabel(label_text)
    label.setStyleSheet("font-size:13px; font-weight:700;")
    root.addWidget(label)
    field = QLineEdit(str(default_text or ""))
    field.selectAll()
    root.addWidget(field)
    buttons = QHBoxLayout()
    cancel = QPushButton("Cancel")
    ok = QPushButton("OK")
    ok.setObjectName("PrimaryButton")
    _fit_button(cancel)
    _fit_button(ok)
    cancel.clicked.connect(dialog.reject)
    ok.clicked.connect(dialog.accept)
    buttons.addWidget(cancel)
    buttons.addStretch()
    buttons.addWidget(ok)
    root.addLayout(buttons)
    field.returnPressed.connect(dialog.accept)
    field.setFocus()
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return field.text()


def _choice_prompt(parent, title, text_value, choices):
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.resize(560, 190)
    set_themed_stylesheet(dialog, ROLE_QSS)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(12)
    message = QLabel(text_value)
    message.setWordWrap(True)
    message.setStyleSheet("font-size:13px;")
    root.addWidget(message)
    root.addStretch()
    buttons = QHBoxLayout()
    cancel = QPushButton("Cancel")
    _fit_button(cancel)
    cancel.clicked.connect(dialog.reject)
    buttons.addWidget(cancel)
    buttons.addStretch()
    result = {"value": None}
    for label, value, primary in choices:
        button = QPushButton(label)
        if primary:
            button.setObjectName("PrimaryButton")
        _fit_button(button)
        def choose(_checked=False, selected=value):
            result["value"] = selected
            dialog.accept()
        button.clicked.connect(choose)
        buttons.addWidget(button)
    root.addLayout(buttons)
    dialog.exec()
    return result["value"]


def _confirm_campaign_delete(parent, campaign_name):
    """Campaign-themed destructive confirmation with consistent button order."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Delete Campaign")
    dialog.setModal(True)
    dialog.setFixedWidth(500)
    set_themed_stylesheet(dialog, ROLE_QSS)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(12)

    title = QLabel(f'Delete "{campaign_name}"?')
    title.setStyleSheet("font-size:18px; font-weight:900;")
    root.addWidget(title)

    message = QLabel(
        "This removes the campaign for everyone. This action cannot be undone."
    )
    message.setWordWrap(True)
    message.setObjectName("Muted")
    message.setStyleSheet("color:#765d34; font-size:12px;")
    root.addWidget(message)

    buttons = QHBoxLayout()
    buttons.setContentsMargins(0, 6, 0, 0)
    buttons.setSpacing(10)
    cancel = QPushButton("Cancel")
    delete = QPushButton("Delete")
    delete.setObjectName("DangerButton")
    _fit_button(cancel)
    _fit_button(delete)
    cancel.clicked.connect(dialog.reject)
    delete.clicked.connect(dialog.accept)
    buttons.addWidget(cancel)
    buttons.addStretch(1)
    buttons.addWidget(delete)
    root.addLayout(buttons)

    return dialog.exec() == QDialog.DialogCode.Accepted



def _confirm_character_admission(parent, name, mismatches, approve):
    """Make the DM's character-level exception explicit before the RPC."""
    dialog = QDialog(parent)
    dialog.setWindowTitle("Approve Character" if approve else "Reject Character")
    dialog.setModal(True)
    dialog.setMinimumWidth(460)
    dialog.resize(550, 310)
    set_themed_stylesheet(dialog, ROLE_QSS + """
    QTextBrowser#ApprovalDifferences {
        background-color:#fffdf7; color:#25190f; border:1px solid #c79a3b;
        border-radius:7px; padding:7px; font-family:Georgia;
    }
    """)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(20, 16, 20, 16)
    root.setSpacing(10)
    heading = QLabel(("Approve " if approve else "Reject ") + str(name or "Character") + "?")
    heading.setWordWrap(True)
    heading.setStyleSheet("font-size:17px; font-weight:900;")
    root.addWidget(heading)

    if approve:
        message = "This authorizes this character as an exception to the campaign's creation rules."
    else:
        message = "This declines this character's admission request. It does not delete the player's local character."
    description = QLabel(message)
    description.setWordWrap(True)
    description.setObjectName("SectionText")
    root.addWidget(description)

    details = [str(value).strip() for value in (mismatches or ()) if str(value).strip()]
    if details:
        title = QLabel("Rule differences")
        title.setStyleSheet("font-weight:900; font-size:13px;")
        root.addWidget(title)
        summary = QTextBrowser(dialog)
        summary.setObjectName("ApprovalDifferences")
        summary.setPlainText("\n".join("• " + item for item in details))
        summary.setMinimumHeight(75)
        summary.setMaximumHeight(180)
        root.addWidget(summary, 1)
    else:
        note = QLabel("The request includes no visible rule differences. Verify the character before deciding.")
        note.setWordWrap(True)
        note.setObjectName("SectionText")
        root.addWidget(note)
    root.addStretch(1)

    buttons = QHBoxLayout()
    cancel = QPushButton("Cancel")
    action = QPushButton("Approve Character" if approve else "Reject Character")
    action.setObjectName("PrimaryButton" if approve else "DangerButton")
    _fit_button(cancel)
    _fit_button(action)
    cancel.clicked.connect(dialog.reject)
    action.clicked.connect(dialog.accept)
    buttons.addWidget(cancel)
    buttons.addStretch(1)
    buttons.addWidget(action)
    root.addLayout(buttons)
    return dialog.exec() == QDialog.DialogCode.Accepted


class _ThemedSharingCheck(QCheckBox):
    """Theme-matched 20px checkbox for editable and read-only sharing."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRect((self.width()-20)//2, (self.height()-20)//2, 20, 20)
        dark = QApplication.palette().window().color().lightness() < 145
        edge = QColor('#f1c66b' if dark else '#9a7126')
        painter.setPen(QPen(edge, 2))
        painter.setBrush(QColor('#18222e' if dark else '#fffdf7'))
        painter.drawRoundedRect(rect, 5, 5)
        if self.isChecked():
            painter.setPen(QPen(edge, 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            from PySide6.QtCore import QPoint
            painter.drawLine(QPoint(rect.x()+4,rect.y()+10), QPoint(rect.x()+8,rect.y()+14))
            painter.drawLine(QPoint(rect.x()+8,rect.y()+14), QPoint(rect.x()+16,rect.y()+6))
        painter.end()


# DID114_PLAYER_POLISH_7_V1
def _prepare_sharing_checkbox(box, *, locked=False):
    # DID114_SHARING_AUTO_REFRESH_V1: palette-aware contrast & safe click target.
    if not isinstance(box, _ThemedSharingCheck):
        box = _ThemedSharingCheck(box.parent())
    box.setFixedSize(34, 32)
    dark = QApplication.palette().window().color().lightness() < 145
    edge = "#ffffff" if dark else "#93702b"
    fill = "#18222e" if dark else "#fffdf7"
    box.setStyleSheet(
        "QCheckBox { padding:0px 0px 0px 3px; margin:0px; min-height:30px; }"
        "QCheckBox::indicator { width:20px; height:20px; }"
        f"QCheckBox::indicator:unchecked {{ width:16px; height:16px; border:2px solid {edge}; border-radius:5px; background:{fill}; }}"
    )
    if locked:
        box.setChecked(True)
        box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    else:
        box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box

def _confirm_character_removal(parent, display_name):
    dialog = QDialog(parent)
    dialog.setWindowTitle("Remove Character")
    dialog.setModal(True)
    dialog.resize(470, 190)
    set_themed_stylesheet(dialog, ROLE_QSS)

    root = QVBoxLayout(dialog)
    root.setContentsMargins(22, 18, 22, 18)
    root.setSpacing(12)

    title = QLabel(f"Remove {display_name} from this campaign?")
    title.setStyleSheet("font-size:16px; font-weight:900;")
    title.setWordWrap(True)
    root.addWidget(title)

    text = QLabel(
        "This does not delete the player's local .didchar file or historical "
        "session snapshots."
    )
    text.setObjectName("SectionText")
    text.setWordWrap(True)
    root.addWidget(text)
    root.addStretch()

    buttons = QHBoxLayout()
    no_button = QPushButton("No")
    yes_button = QPushButton("Yes")
    yes_button.setObjectName("PrimaryButton")
    _fit_button(no_button)
    _fit_button(yes_button)
    no_button.clicked.connect(dialog.reject)
    yes_button.clicked.connect(dialog.accept)
    buttons.addWidget(no_button)
    buttons.addStretch()
    buttons.addWidget(yes_button)
    root.addLayout(buttons)

    return dialog.exec() == QDialog.DialogCode.Accepted


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
    wrapper.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
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
        # Three compact cards in one row keeps the rules readable and avoids
        # the stacked-card squeeze that previously caused overlapping text in
        # the Campaigns hub.  The parent detail panel scrolls if space is tight.
        layout.addWidget(
            card,
            0,
            index,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
    for column in range(3):
        layout.setColumnStretch(column, 1)
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


def _ip_text(state):
    resources = state.get("resources", {}) if isinstance(state, dict) else {}
    points = resources.get("improvement_points", {}) if isinstance(resources, dict) else {}
    try:
        used = max(0, int(points.get("used") or 0))
        total = max(0, int(points.get("total") or 0))
    except Exception:
        used = total = 0
    return f"{used} / {total}"


class _WizardDialog(QDialog):
    page_names = ()

    def _setup_shell(self, title_text, subtitle_text):
        set_themed_stylesheet(self, ROLE_QSS)
        embedded = bool(getattr(self, "_embedded", False))
        if embedded:
            self.setWindowFlags(Qt.WindowType.Widget)
        root = QVBoxLayout(self)
        root.setContentsMargins(0 if embedded else 8, 0 if embedded else 16, 0 if embedded else 22, 0 if embedded else 16)
        root.setSpacing(8)
        self.header_left = QHBoxLayout()
        self.header_left.setContentsMargins(0, 0, 0, 0)
        self.header_left.setSpacing(6)
        if not embedded:
            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            left_host = QWidget()
            left_host.setFixedWidth(150)
            left_host.setLayout(self.header_left)
            header.addWidget(left_host)
            title = QLabel(title_text)
            title.setObjectName("PageTitle")
            title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            header.addWidget(title, 1)
            right_host = QWidget()
            right_host.setFixedWidth(150)
            header.addWidget(right_host)
            root.addLayout(header)
            subtitle = QLabel(subtitle_text)
            subtitle.setObjectName("PageSubtitle")
            subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            root.addWidget(subtitle)
        else:
            embedded_header = QHBoxLayout()
            embedded_header.addLayout(self.header_left)
            embedded_header.addStretch()
            root.addLayout(embedded_header)
        self.step_label = QLabel("")
        self.step_label.setObjectName("StepBar")
        self.step_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self.step_label)
        self.pages = QStackedWidget()
        root.addWidget(self.pages, 1)
        bottom = QHBoxLayout()
        self.back_btn = QPushButton("Back")
        self.back_btn.clicked.connect(lambda: self.show_page(self.page_index - 1))
        bottom.addWidget(self.back_btn)
        bottom.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.next_btn = QPushButton("Next")
        self.next_btn.setObjectName("PrimaryButton")
        self.next_btn.clicked.connect(lambda: self.show_page(self.page_index + 1))
        bottom.addWidget(self.close_btn)
        bottom.addWidget(self.next_btn)
        root.addLayout(bottom)
        for button in (self.back_btn, self.close_btn, self.next_btn):
            _fit_button(button)
        self.page_index = 0
        self._root_layout = root

    def _legacy_submit_job(self, kind, operation):
        """Perform legacy wizard cloud operations outside Qt's event thread."""
        if not hasattr(self, "_legacy_job_results"):
            self._legacy_job_results = SimpleQueue()
            self._legacy_job_epochs = {}
            self._legacy_job_timer = QTimer(self)
            self._legacy_job_timer.setInterval(75)
            self._legacy_job_timer.timeout.connect(self._legacy_drain_results)
            self._legacy_job_timer.start()
        generation = self._legacy_job_epochs.get(kind, 0) + 1
        self._legacy_job_epochs[kind] = generation
        QThreadPool.globalInstance().start(
            _CampaignHubNetworkJob(self._legacy_job_results, kind, generation, operation)
        )

    def _legacy_drain_results(self):
        while True:
            try:
                kind, generation, payload, error = self._legacy_job_results.get_nowait()
            except Empty:
                break
            if generation != self._legacy_job_epochs.get(kind):
                continue  # Superseded request; do not restore stale UI state.
            if kind == "campaigns":
                self._finish_legacy_campaign_list(payload, error)
            elif kind == "characters" and hasattr(self, "_finish_legacy_dm_characters"):
                self._finish_legacy_dm_characters(payload, error)
            elif kind == "remove" and hasattr(self, "_finish_legacy_dm_remove"):
                self._finish_legacy_dm_remove(payload, error)

    def show_page(self, index):
        index = max(0, min(len(self.page_names) - 1, int(index)))
        self.page_index = index
        self.pages.setCurrentIndex(index)
        self.step_label.setText(f"Step {index + 1} of {len(self.page_names)}  •  {self.page_names[index]}")
        self.back_btn.setVisible(index > 0)
        self.next_btn.setVisible(index < len(self.page_names) - 1)
        self.close_btn.setVisible((not getattr(self, "_embedded", False)) and index == len(self.page_names) - 1)


class DMCampaignManagerDialog(_WizardDialog):
    page_names = ("Campaign", "Characters", "Creation Rules", "Edit Rules")

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
        self._build_embedded_rules_editor_page()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        self.refresh_btn.setObjectName("RefreshButton")
        self.refresh_btn.setFixedWidth(66)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_left.addWidget(self.refresh_btn)
        self.reload_campaigns()
        self.show_page(0)

    def show_page(self, index):
        # The first three pages are the normal DM wizard. The embedded rules
        # editor is opened only from Edit Rules, so Next never lands on an
        # empty editor page.
        if int(index) == 3:
            self.page_index = 3
            self.pages.setCurrentIndex(3)
            self.step_label.setText("Edit Rules")
            self.back_btn.setVisible(False)
            self.next_btn.setVisible(False)
            self.close_btn.setVisible(False)
            return
        index = max(0, min(2, int(index)))
        self.page_index = index
        self.pages.setCurrentIndex(index)
        names = ("Campaign", "Characters", "Creation Rules")
        self.step_label.setText(f"Step {index + 1} of 3  •  {names[index]}")
        self.back_btn.setVisible(index > 0)
        self.next_btn.setVisible(index < 2)
        self.close_btn.setVisible(index == 2)

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
        row.addWidget(_build_combo_shell(self.campaign_combo), 1)
        form.addLayout(row, 0, 1)
        form.addWidget(QLabel("Campaign Details"), 1, 0)
        details = QHBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(6)
        self.role_label = QLabel("Role: DM")
        details.addWidget(self.role_label)
        details.addWidget(QLabel("•"))
        details.addWidget(QLabel("Invite code:"))
        self.invite_code_btn = QPushButton("")
        self.invite_code_btn.setObjectName("InviteCodeButton")
        self.invite_code_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.invite_code_btn.clicked.connect(self.copy_invite_code)
        details.addWidget(self.invite_code_btn)
        self.copy_code_success = QLabel("✓")
        self.copy_code_success.setObjectName("CopySuccess")
        self.copy_code_success.setVisible(False)
        details.addWidget(self.copy_code_success)
        details.addStretch()
        self.full_invite_btn = QPushButton("Invite Players")
        self.full_invite_btn.setObjectName("CompactButton")
        self.full_invite_btn.clicked.connect(self.copy_full_invite)
        self.full_invite_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        details.addWidget(self.full_invite_btn)
        self.invite_success = QLabel("✓")
        self.invite_success.setObjectName("InviteSuccess")
        self.invite_success.setVisible(False)
        details.addWidget(self.invite_success)
        self.meta = QLabel("")
        self.meta.setVisible(False)
        form.addLayout(details, 1, 1)
        form.addWidget(QLabel("Campaign Actions"), 2, 0)
        actions = QHBoxLayout()
        new_btn = QPushButton("New Campaign")
        new_btn.clicked.connect(self.create_campaign)
        self.dm_dashboard_btn = QPushButton("Open DM Dashboard")
        self.dm_dashboard_btn.clicked.connect(self.open_dm_dashboard)
        self.party_dashboard_btn = QPushButton("Open Party Dashboard")
        self.party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        self.discord_btn = QPushButton("Discord")
        self.discord_btn.clicked.connect(self.open_discord_setup)
        for button in (new_btn, self.dm_dashboard_btn, self.party_dashboard_btn, self.discord_btn):
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
        self.character_scroll.viewport().setStyleSheet("background: transparent;")
        self.character_body = QWidget()
        self.character_body.setStyleSheet("background: transparent;")
        self.character_layout = QGridLayout(self.character_body)
        self.character_layout.setContentsMargins(0, 2, 0, 2)
        self.character_layout.setHorizontalSpacing(10)
        self.character_layout.setVerticalSpacing(10)
        self.character_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.character_layout.setColumnStretch(0, 1)
        self.character_layout.setColumnStretch(1, 1)
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

    def _build_embedded_rules_editor_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 0, 4, 0)
        outer.setSpacing(0)
        self.embedded_rules_host = QVBoxLayout()
        self.embedded_rules_host.setContentsMargins(0, 0, 0, 0)
        outer.addLayout(self.embedded_rules_host)
        self.pages.addWidget(page)

    def _clear_embedded_rules_editor(self):
        while self.embedded_rules_host.count():
            item = self.embedded_rules_host.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.embedded_rules_editor = None

    def _open_embedded_rules_editor(self):
        if not self.current_campaign or self.service is None:
            return
        self._clear_embedded_rules_editor()
        editor = CampaignRulesEditorDialog(self, template=campaign_template(self.current_campaign))
        editor.setWindowFlags(Qt.WindowType.Widget)
        editor.setModal(False)
        editor.accepted.connect(lambda: self._finish_embedded_rules_editor(editor))
        editor.rejected.connect(lambda: self.show_page(2))
        self.embedded_rules_editor = editor
        self.embedded_rules_host.addWidget(editor)
        editor.show()
        self.show_page(3)

    def _finish_embedded_rules_editor(self, editor):
        try:
            updated = self.service.update_campaign_template(
                self.current_campaign["id"], editor.template
            )
        except Exception as error:
            QMessageBox.warning(self, "Update Rules Failed", str(error))
            return
        self.current_campaign.update(updated)
        self._refresh_rules()
        self.show_page(2)

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                # Remove refreshed widgets from the visible hierarchy immediately.
                # deleteLater() alone can leave the old rule-card widget painted
                # until the event loop runs, which made successive refreshes look
                # like duplicated/overlapping rule sections.
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif child is not None:
                self._clear_layout(child)

    def reload_campaigns(self):
        if self.service is None:
            self._finish_legacy_campaign_list([], None)
            return
        service = self.service
        def fetch():
            return [dict(campaign, role="dm") for campaign in service.list_campaigns()
                    if service.role_for_campaign(campaign.get("id")) == "dm"]
        self._legacy_submit_job("campaigns", fetch)

    def _finish_legacy_campaign_list(self, rows, error):
        if error:
            QMessageBox.warning(self, "Campaigns", str(error))
            return  # Keep existing rows on network failure.
        selected_id = (str(getattr(self, "_legacy_target_campaign_id", "") or "")
                       or str((self.current_campaign or {}).get("id") or ""))
        self._legacy_target_campaign_id = ""
        self.campaigns = list(rows or [])
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        for campaign in self.campaigns:
            self.campaign_combo.addItem(str(campaign.get("name") or "Unnamed Campaign"), campaign.get("id"))
        selected_index = next((i for i, c in enumerate(self.campaigns)
                               if str(c.get("id") or "") == selected_id), 0)
        self.campaign_combo.setCurrentIndex(selected_index if self.campaigns else -1)
        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self._campaign_changed(selected_index)
            if getattr(self, "_legacy_copy_invite_after_load", False):
                self._legacy_copy_invite_after_load = False
                self.copy_invite_code()
        else:
            self.current_campaign = None
            self.meta.setText("No campaigns you DM yet.")
            self._refresh_characters()
            self._refresh_rules()
            self._update_action_state()

    def _campaign_changed(self, index):
        self.current_campaign = self.campaigns[index] if 0 <= index < len(self.campaigns) else None
        if self.current_campaign:
            self.role_label.setText("Role: DM")
            self.invite_code_btn.setText(str(self.current_campaign.get("invite_code") or ""))
        self._refresh_characters()
        self._refresh_rules()
        self._update_action_state()

    def _update_action_state(self):
        enabled = isinstance(self.current_campaign, dict)
        self.dm_dashboard_btn.setEnabled(enabled)
        self.party_dashboard_btn.setEnabled(enabled)
        self.discord_btn.setEnabled(enabled)
        self.edit_rules_btn.setEnabled(enabled)
        self.invite_code_btn.setEnabled(enabled)
        self.full_invite_btn.setEnabled(enabled)

    def copy_invite_code(self):
        code = self.current_campaign.get("invite_code") if isinstance(self.current_campaign, dict) else ""
        if _copy_text_silent(code):
            self.copy_code_success.setVisible(True)
            QTimer.singleShot(1400, lambda: self.copy_code_success.setVisible(False))

    def copy_full_invite(self):
        if _copy_text_silent(_campaign_invite_text(self.current_campaign)):
            self.invite_success.setVisible(True)
            QTimer.singleShot(1400, lambda: self.invite_success.setVisible(False))

    def _refresh_characters(self):
        self._clear_layout(self.character_layout)
        if not self.current_campaign or self.client is None:
            self.character_layout.addWidget(QLabel("No campaign selected."), 0, 0, 1, 2)
            return
        campaign_id = str(self.current_campaign["id"])
        self.character_layout.addWidget(QLabel("Loading characters…"), 0, 0, 1, 2)
        client = self.client
        self._legacy_submit_job(
            "characters", lambda: (campaign_id, client.list_campaign_characters(campaign_id))
        )

    def _finish_legacy_dm_characters(self, payload, error):
        if payload and str((self.current_campaign or {}).get("id") or "") != str(payload[0]):
            return
        self._clear_layout(self.character_layout)
        if error:
            self.character_layout.addWidget(QLabel(f"Could not load characters: {error}"), 0, 0, 1, 2)
            return
        rows = payload[1] if payload else []
        if not rows:
            label = QLabel("No characters have been saved to this campaign yet.")
            label.setObjectName("Muted")
            self.character_layout.addWidget(label, 0, 0, 1, 2)
            return

        for index, row in enumerate(rows):
            state = _state_from_character_row(row)
            display_name = str(
                state.get("name")
                or row.get("display_name")
                or "Unnamed Character"
            )
            try:
                level_value = int(state.get("level") or 1)
            except Exception:
                level_value = 1

            card = QFrame()
            card.setObjectName("Card")
            card.setMaximumWidth(520)

            card_box = QVBoxLayout(card)
            card_box.setContentsMargins(14, 11, 14, 12)
            card_box.setSpacing(7)

            top = QHBoxLayout()
            top.setContentsMargins(0, 0, 0, 0)
            top.setSpacing(6)

            identity = QVBoxLayout()
            identity.setContentsMargins(0, 0, 0, 0)
            identity.setSpacing(1)
            name = QLabel(display_name)
            name.setStyleSheet("font-size:15px; font-weight:900;")
            level = QLabel(f"Level {level_value}")
            level.setObjectName("Muted")
            identity.addWidget(name)
            identity.addWidget(level)
            top.addLayout(identity, 1)

            remove = QPushButton("×")
            remove.setObjectName("RemoveXButton")
            remove.setFixedSize(18, 18)
            remove.setToolTip("Remove from campaign")
            remove.setCursor(Qt.CursorShape.PointingHandCursor)
            remove.clicked.connect(
                lambda _checked=False,
                character_id=row.get("id"),
                display=display_name:
                    self.remove_character(character_id, display)
            )
            top.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            card_box.addLayout(top)

            stats = QGridLayout()
            stats.setContentsMargins(0, 3, 0, 0)
            stats.setHorizontalSpacing(18)
            stats.setVerticalSpacing(4)

            hp_label = QLabel("HP")
            hp_label.setObjectName("HPLabel")
            hp_value = QLabel(_hp_text(state))
            hp_value.setObjectName("HPValue")
            at_label = QLabel("AT")
            at_label.setObjectName("ATLabel")
            at_value = QLabel(_at_text(state))
            at_value.setObjectName("ATValue")

            stats.addWidget(hp_label, 0, 0)
            stats.addWidget(hp_value, 0, 1)
            stats.addWidget(at_label, 1, 0)
            stats.addWidget(at_value, 1, 1)
            stats.setColumnStretch(1, 1)
            card_box.addLayout(stats)

            self.character_layout.addWidget(
                card,
                index // 2,
                index % 2,
                alignment=Qt.AlignmentFlag.AlignTop,
            )

    def remove_character(self, campaign_character_id, display_name):
        if not _confirm_character_removal(self, display_name):
            return
        client = self.client
        if client is None:
            return
        def remove_remote():
            result = client._request_json(
                "POST", "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": str(campaign_character_id)},
            )
            if result is False:
                raise RuntimeError("The character could not be removed.")
            return True
        self._legacy_submit_job("remove", remove_remote)

    def _finish_legacy_dm_remove(self, payload, error):
        if error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
        else:
            self._refresh_characters()

    def _refresh_rules(self):
        self._clear_layout(self.rules_holder)
        if not self.current_campaign:
            self.rules_holder.addWidget(QLabel("No campaign selected."))
            return
        self.rules_holder.addWidget(_build_rule_cards(self.current_campaign))

    def _choose_rules(self, campaign_name):
        choice = _choice_prompt(
            self,
            "Campaign Creation Rules",
            "Design the campaign's rules now, or start from an existing .didtemplate file.",
            (("Design Rules", "design", True), ("Use Existing Template", "existing", False)),
        )
        if choice == "existing":
            return load_template_from_file(parent=self)
        if choice != "design":
            return None
        template = CharacterTemplate(name=f"{campaign_name} Rules")
        editor = CampaignRulesEditorDialog(self, template=template)
        if editor.exec() != QDialog.DialogCode.Accepted:
            return None
        return editor.template

    def create_campaign(self):
        if self.service is None:
            return
        name = _text_prompt(self, "New Campaign", "Campaign name:")
        name = str(name or "").strip()
        if not name:
            return
        template = self._choose_rules(name)
        if template is None:
            return
        try:
            created = self.service.create_campaign(name, template)
        except Exception as error:
            QMessageBox.warning(self, "Create Campaign Failed", str(error))
            return
        self._legacy_target_campaign_id = str(created.get("id") or "")
        self._legacy_copy_invite_after_load = True
        self.reload_campaigns()

    def edit_rules(self):
        self._open_embedded_rules_editor()

    def open_dm_dashboard(self):
        if not self.current_campaign or self.client is None:
            return
        try:
            launch_dm_dashboard(self.client, self.current_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open DM Dashboard Failed", str(error))

    def open_discord_setup(self):
        if not self.current_campaign:
            return
        dialog = DiscordIntegrationDialog(
            self,
            campaign_id=self.current_campaign.get("id"),
            campaign_name=self.current_campaign.get("name") or "Campaign",
            app_dir=Path(__file__).resolve().parent,
            campaign_client=self.client,
        )
        dialog.exec()

    def open_party_dashboard(self):
        if not self.current_campaign or self.client is None:
            return
        campaign_id = str(self.current_campaign.get("id") or "")
        links = getattr(self.client, "links", None)
        saved = links.all_links() if links and hasattr(links, "all_links") else {}
        allowed = any(
            isinstance(link, dict)
            and str(link.get("campaign_id") or "") == campaign_id
            and bool(link.get("campaign_character_id"))
            and link.get("approval_status") not in ("pending", "rejected")
            for link in saved.values()
        )
        if not allowed:
            QMessageBox.information(self, "Character Approval Required",
                "The Party Dashboard is available after the DM approves your campaign character.")
            return
        try:
            launch_party_dashboard(self.client, self.current_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open Party Dashboard Failed", str(error))


class PlayerCampaignsDialog(_WizardDialog):
    page_names = ("Campaign", "My Character & Sharing", "Creation Rules")

    def __init__(self, window, *, embedded=False, host_dialog=None, defer_initial_reload=False):
        self._embedded = bool(embedded)
        self._host_dialog = host_dialog
        super().__init__(host_dialog if embedded and host_dialog is not None else window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.session_service = CampaignSessionService(self.client) if self.client else None
        self.dm_store = privacy_store_for_window(window)
        self.party_store = party_privacy_store_for_window(window)
        self._dm_prefs = normalize_privacy_preferences()
        self._party_prefs = normalize_party_preferences()
        self.campaigns = []
        self.current_campaign = None
        self.inventory_dm_boxes = {}
        self.inventory_party_boxes = {}
        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        # Always have a valid sharing model, even before a player has joined a
        # campaign.  The character page can still refresh in that state.
        self._dm_prefs = normalize_privacy_preferences()
        self._party_prefs = normalize_party_preferences()
        self.setWindowTitle("My Campaigns")
        if not self._embedded:
            self.resize(900, 620)
            self.setMinimumSize(820, 560)
        self._setup_shell(
            "My Campaigns",
            "Join campaigns you play in, manage your character, and choose what the DM and party can see.",
        )
        self._build_campaign_page()
        self._build_character_page()
        self._build_rules_page()
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("RefreshButton")
        self.refresh_btn.setFixedWidth(66)
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.reload_campaigns)
        self.header_left.addWidget(self.refresh_btn)
        # The hidden hub helper is just a controller. Do not perform a full
        # cloud fetch plus one role lookup per campaign during hub construction.
        pending = getattr(window, "_pending_campaign_character", None)
        if isinstance(pending, dict) and not (embedded and defer_initial_reload):
            self._legacy_target_campaign_id = str(pending.get("campaign_id") or "")
        if not (embedded and defer_initial_reload):
            self.reload_campaigns()
        if isinstance(pending, dict) and not (embedded and defer_initial_reload):
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
        row.addWidget(_build_combo_shell(self.campaign_combo), 1)
        form.addLayout(row, 0, 1)
        form.addWidget(QLabel("Membership"), 1, 0)
        self.meta = QLabel("No player campaigns yet.")
        form.addWidget(self.meta, 1, 1)
        form.addWidget(QLabel("Actions"), 2, 0)
        actions = QHBoxLayout()
        self.join_campaign_btn = QPushButton("Join Campaign")
        self.join_campaign_btn.clicked.connect(self.join_campaign)
        self.party_dashboard_btn = QPushButton("Open Party Dashboard")
        self.party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        for button in (self.join_campaign_btn, self.party_dashboard_btn):
            _fit_button(button)
            actions.addWidget(button)
        actions.addStretch()
        form.addLayout(actions, 2, 1)
        box.addLayout(form)

        self.inline_join_form = QFrame()
        self.inline_join_form.setObjectName("Field")
        join_form = QGridLayout(self.inline_join_form)
        join_form.setContentsMargins(12, 10, 12, 10)
        join_form.setHorizontalSpacing(10)
        join_form.setVerticalSpacing(8)
        join_form.addWidget(QLabel("Invite code"), 0, 0)
        self.inline_join_code = QLineEdit()
        self.inline_join_code.setPlaceholderText("Enter campaign invite code")
        join_form.addWidget(self.inline_join_code, 0, 1)
        join_form.addWidget(QLabel("Your name"), 1, 0)
        self.inline_join_name = QLineEdit()
        self.inline_join_name.setPlaceholderText("Name shown to the DM")
        join_form.addWidget(self.inline_join_name, 1, 1)
        join_actions = QHBoxLayout()
        join_actions.addStretch()
        cancel_join = QPushButton("Cancel")
        cancel_join.clicked.connect(lambda: self.inline_join_form.setVisible(False))
        confirm_join = QPushButton("Join")
        confirm_join.setObjectName("PrimaryButton")
        confirm_join.clicked.connect(self._submit_inline_join)
        join_actions.addWidget(cancel_join)
        join_actions.addWidget(confirm_join)
        join_form.addLayout(join_actions, 2, 0, 1, 2)
        self.inline_join_form.setVisible(False)
        box.addWidget(self.inline_join_form)
        self.pages.addWidget(page)

    def _build_character_page(self):
        # This page contains the sharing matrix and can grow when inventory or
        # note details are expanded.  Put the page itself in a scroll area so
        # it never forces the whole wizard taller than the user's screen.
        page = QWidget()
        page_outer = QVBoxLayout(page)
        page_outer.setContentsMargins(0, 0, 0, 0)
        page_outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        box = QVBoxLayout(content)
        box.setContentsMargins(18, 10, 18, 6)
        box.setSpacing(8)
        box.setAlignment(Qt.AlignmentFlag.AlignTop)

        heading = QLabel("My Character")
        heading.setObjectName("SectionTitle")
        box.addWidget(heading)
        intro = QLabel(
            "Create with the campaign's rules, edit normally on the sheet, "
            "then save the finished character to the campaign."
        )
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
        actions.setSpacing(8)
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

        help_text = QLabel(
            "Choose separately what the DM can see and what the rest of the party can see. "
            "HP, AT and Abilities are always available to the DM for campaign play."
        )
        help_text.setObjectName("SectionText")
        help_text.setWordWrap(True)
        box.addWidget(help_text)

        sharing = QFrame()
        sharing.setObjectName("Field")
        grid = QGridLayout(sharing)
        grid.setContentsMargins(24, 12, 18, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(5)
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
            dm = _prepare_sharing_checkbox(QCheckBox(), locked=True)
            party = _prepare_sharing_checkbox(QCheckBox())
            self.dm_core_boxes[key] = dm
            self.party_boxes[key] = party
            grid.addWidget(dm, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(party, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
            row += 1

        for key, label_text in (
            ("improvements", "Improvements"),
            ("portrait", "Portrait"),
            ("inventory", "Inventory"),
            ("notes", "Notes"),
        ):
            grid.addWidget(QLabel(label_text), row, 0)
            dm = _prepare_sharing_checkbox(QCheckBox())
            party = _prepare_sharing_checkbox(QCheckBox())
            setattr(self, f"dm_{key}_box", dm)
            self.party_boxes[key] = party
            grid.addWidget(dm, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
            grid.addWidget(party, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
            row += 1

        grid.addWidget(QLabel("Session dice rolls (shared)"), row, 0)
        self.roll_share_box = _prepare_sharing_checkbox(QCheckBox())
        self.party_roll_share_box = _prepare_sharing_checkbox(QCheckBox())
        self.roll_share_box.setToolTip("DM and Party rolls share one setting. If not linked, this is a temporary choice until linking.")
        self.party_roll_share_box.setToolTip("DM and Party rolls share one setting. If not linked, this is a temporary choice until linking.")
        self.roll_share_box.toggled.connect(self._roll_sharing_changed)
        self.party_roll_share_box.toggled.connect(self._party_roll_sharing_changed)
        grid.addWidget(self.roll_share_box, row, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(self.party_roll_share_box, row, 2, alignment=Qt.AlignmentFlag.AlignHCenter)
        grid.setColumnMinimumWidth(1, 54)
        grid.setColumnMinimumWidth(2, 70)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 0)
        grid.setColumnStretch(2, 0)
        box.addWidget(sharing)

        self.inventory_detail = self._build_selection_section("Inventory items", "inventory")
        self.notes_detail = self._build_selection_section("Notes", "notes")
        box.addWidget(self.inventory_detail)
        box.addWidget(self.notes_detail)

        for toggle in (
            self.dm_inventory_box,
            self.party_boxes["inventory"],
            self.dm_notes_box,
            self.party_boxes["notes"],
        ):
            toggle.toggled.connect(self._refresh_detail_visibility)

        box.addStretch()
        scroll.setWidget(content)
        page_outer.addWidget(scroll)
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
        # Use the same 34px columns and spacing as the checkbox rows.
        # A separate spacer used to shift the DM heading out of alignment.
        for title in ("DM", "Party"):
            label = QLabel(title)
            label.setFixedWidth(34)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            heading.addWidget(label)
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
        if self.service is None:
            self._finish_legacy_campaign_list([], None)
            return
        service = self.service
        def fetch():
            return [dict(campaign, role="player") for campaign in service.list_campaigns()
                    if service.role_for_campaign(campaign.get("id")) == "player"]
        self._legacy_submit_job("campaigns", fetch)

    def _finish_legacy_campaign_list(self, rows, error):
        if error:
            QMessageBox.warning(self, "My Campaigns", str(error))
            return
        selected_id = (str(getattr(self, "_legacy_target_campaign_id", "") or "")
                       or str((self.current_campaign or {}).get("id") or ""))
        self._legacy_target_campaign_id = ""
        self.campaigns = list(rows or [])
        self.campaign_combo.blockSignals(True)
        self.campaign_combo.clear()
        for campaign in self.campaigns:
            self.campaign_combo.addItem(str(campaign.get("name") or "Unnamed Campaign"), campaign.get("id"))
        selected_index = next((i for i, c in enumerate(self.campaigns)
                               if str(c.get("id") or "") == selected_id), 0)
        self.campaign_combo.setCurrentIndex(selected_index if self.campaigns else -1)
        self.campaign_combo.blockSignals(False)
        if self.campaigns:
            self._campaign_changed(selected_index)
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

    def _sharing_character_context(self):
        """Resolve the approved character for the selected campaign, not the open tab.

        A saved character may be opened elsewhere in the app; never switch the
        user's sheet merely to view its campaign sharing preferences.
        """
        campaign_id = str((self.current_campaign or {}).get("id") or "")
        if not campaign_id or self.client is None:
            return None, None
        links = getattr(self.client, "links", None)
        records = links.all_links() if links and hasattr(links, "all_links") else {}
        for raw_id, record in records.items():
            if not isinstance(record, dict):
                continue
            if str(record.get("campaign_id") or "") != campaign_id:
                continue
            if (not record.get("campaign_character_id") or
                    str(record.get("approval_status") or "").lower() in {"pending", "rejected"}):
                continue
            character_id = str(raw_id)
            opened = getattr(self.window, "character", None)
            if str(getattr(opened, "id", "") or "") == character_id:
                return opened, dict(record)
            # Load only the selected campaign character. Do not mutate the
            # current character or its unsaved edits.
            from backend_2_1 import CharacterStorageSystem
            import os
            CharacterStorageSystem.ensure_save_dir()
            for directory, subdirs, files in os.walk(CharacterStorageSystem.SAVE_DIR):
                subdirs[:] = [d for d in subdirs if d != "_history"]
                for filename in files:
                    if not filename.lower().endswith(".didchar"):
                        continue
                    path = os.path.join(directory, filename)
                    try:
                        if not CharacterStorageSystem.looks_like_character_file(path):
                            continue
                        candidate = CharacterStorageSystem.import_character_file(path)
                        if str(getattr(candidate, "id", "") or "") == character_id:
                            return candidate, dict(record)
                    except Exception:
                        continue
            # Do not display or publish an unrelated open character if the
            # linked character's saved file is missing.
            return None, dict(record)
        return None, None

    def _refresh_character_page(self):
        character, link = self._sharing_character_context()
        self._sharing_character = character
        self._sharing_link = link
        if character is None:
            self.character_name.setText("Linked character unavailable" if link else "No character added")
            self.character_hint.setText("Find the saved character file" if link else "Add a character to this campaign")
            self.sync_label.setText("Not available" if link else "Not connected")
        else:
            name = str(getattr(character, "name", "") or "Unnamed Character")
            progression = getattr(character, "progression", None)
            level = int(getattr(progression, "level", 1) or 1)
            species = str(getattr(character, "species", "") or "")
            self.character_name.setText(name)
            self.character_hint.setText(" • ".join(x for x in (species, f"Level {level}") if x))
            self.sync_label.setText("Connected")
        self.unlink_btn.setEnabled(bool(link))
        self.apply_sharing_btn.setEnabled(bool(character and link))
        open_id = str(getattr(getattr(self.window, "character", None), "id", "") or "")
        linked_id = str(getattr(character, "id", "") or "")
        self.save_btn.setEnabled(bool(character and link and open_id == linked_id))
        self.save_btn.setToolTip("Open the linked character sheet to save character changes." if open_id != linked_id else "")
        checked = False
        if link and self.session_service is not None:
            try:
                checked = bool(self.session_service.get_roll_sharing(link.get("campaign_character_id")))
            except Exception:
                checked = True
        for box in (self.roll_share_box, self.party_roll_share_box):
            box.blockSignals(True)
            box.setChecked(checked)
            box.setEnabled(bool(character and link))
            box.blockSignals(False)
        self._load_sharing_preferences()
        self._populate_inventory_notes()
        self._refresh_detail_visibility()

    def _current_link(self):
        _, link = self._sharing_character_context()
        return link

    def _load_sharing_preferences(self):
        # The Character page is refreshed even when the user has not joined a
        # player campaign yet. Always keep valid default preference models so
        # inventory/note rows can be built safely in that state.
        if not self.current_campaign or getattr(self, "_sharing_character", None) is None:
            self._dm_prefs = normalize_privacy_preferences()
            self._party_prefs = normalize_party_preferences()
            return
        character_id = str(getattr(getattr(self, "_sharing_character", None), "id", "") or "")
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
        if not hasattr(self, "_dm_prefs"):
            self._dm_prefs = normalize_privacy_preferences()
        if not hasattr(self, "_party_prefs"):
            self._party_prefs = normalize_party_preferences()
        self._clear_layout(self.inventory_selection_layout)
        self._clear_layout(self.notes_selection_layout)
        self.inventory_dm_boxes = {}
        self.inventory_party_boxes = {}
        self.note_dm_boxes = {}
        self.note_party_boxes = {}
        inventory = list(getattr(getattr(getattr(self, "_sharing_character", None), "inventory", None), "list_of_items", []) or [])
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
                dm = _prepare_sharing_checkbox(QCheckBox())
                party = _prepare_sharing_checkbox(QCheckBox())
                dm.setChecked(item_id in set(self._dm_prefs.get("inventory_item_ids", [])))
                party.setChecked(item_id in set(self._party_prefs.get("inventory_item_ids", [])))
                self.inventory_dm_boxes[item_id] = dm
                self.inventory_party_boxes[item_id] = party
                row.addWidget(dm)
                row.addWidget(party)
                self.inventory_selection_layout.addLayout(row)
        notes = list(getattr(getattr(getattr(self, "_sharing_character", None), "notes", None), "list_of_notes", []) or [])
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
                dm = _prepare_sharing_checkbox(QCheckBox())
                party = _prepare_sharing_checkbox(QCheckBox())
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
        if not self.current_campaign or getattr(self, "_sharing_character", None) is None:
            return
        campaign_id = str(self.current_campaign.get("id") or "")
        character_id = str(getattr(getattr(self, "_sharing_character", None), "id", "") or "")
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
            # Publishing the open character here would overwrite the campaign
            # character when a different sheet is selected. Build both states
            # from the resolved character and its own privacy preferences.
            from campaign_privacy import build_shared_character_state_with_preferences
            from campaign_party import build_party_character_state_with_preferences
            selected = self._sharing_character
            link = self._current_link()
            if not link or not link.get("campaign_character_id"):
                raise RuntimeError("The selected campaign has no approved character link.")
            record_id = link["campaign_character_id"]
            shared = build_shared_character_state_with_preferences(selected, dm)
            party_state = build_party_character_state_with_preferences(selected, party)
            self.client.upload_character_state(record_id, shared)
            upload_party_state(self.client, campaign_id, record_id, party_state)
        except Exception as error:
            QMessageBox.warning(self, "Update Sharing Failed", str(error))
            return
        QMessageBox.information(self, "Sharing Updated", "Your DM and Party Dashboard sharing choices were updated.")

    def _set_roll_sharing_from_ui(self, enabled):
        # DID114_SHARING_AUTO_REFRESH_V1: one server setting for DM + Party.
        enabled = bool(enabled)
        link = self._current_link()
        if not link or self.session_service is None:
            self._did114_pending_roll_share = enabled
            character = getattr(self, "_sharing_character", None)
            self._did114_pending_roll_key = (
                str((self.current_campaign or {}).get("id") or ""),
                str(getattr(character, "id", "") or ""))
        else:
            try:
                self.session_service.set_roll_sharing(
                    link.get("campaign_character_id"), enabled
                )
            except Exception as error:
                QMessageBox.warning(self, "Update Roll Sharing Failed", str(error))
                return
            self._did114_pending_roll_share = None
            self._did114_pending_roll_key = None
        for box in (self.roll_share_box, self.party_roll_share_box):
            box.blockSignals(True)
            box.setChecked(enabled)
            box.blockSignals(False)

    def _roll_sharing_changed(self, enabled):
        self._set_roll_sharing_from_ui(enabled)

    def _party_roll_sharing_changed(self, enabled):
        self._set_roll_sharing_from_ui(enabled)

    def join_campaign(self):
        if self.service is None:
            return
        if self._embedded:
            self.inline_join_name.setText(
                str(getattr(self.window.character, "name", "") or "Player")
            )
            self.inline_join_form.setVisible(True)
            self.inline_join_code.setFocus()
            return
        code = _text_prompt(self, "Join Campaign", "Invite code:")
        code = str(code or "").strip()
        if not code:
            return
        display_name = _text_prompt(
            self,
            "Join Campaign",
            "Your display name:",
            str(getattr(self.window.character, "name", "") or "Player"),
        )
        if display_name is None:
            return
        try:
            publication = join_campaign_and_publish(
                self.window, self.service, self.client, code, display_name
            )
            joined = publication.campaign
        except JoinedButCharacterNotPublished as error:
            joined = error.campaign
            publication = None
            QMessageBox.warning(self, "Campaign Joined — Upload Failed", str(error))
        except Exception as error:
            QMessageBox.warning(self, "Join Campaign Failed", str(error))
            return
        self._legacy_target_campaign_id = str(joined.get("id") or "")
        self.reload_campaigns()
        if publication is not None:
            if publication.status == "needs_character":
                offer_create_character_after_join(
                    self, self.window, publication.campaign,
                    on_created=self._leave_campaign_surface_for_sheet,
                )
            else:
                _report_join_publication(self, publication)

    def _submit_inline_join(self):
        if self.service is None:
            return
        code = str(self.inline_join_code.text() or "").strip()
        display_name = str(self.inline_join_name.text() or "Player").strip() or "Player"
        if not code:
            self.inline_join_code.setFocus()
            return
        try:
            publication = join_campaign_and_publish(
                self.window, self.service, self.client, code, display_name
            )
            joined = publication.campaign
        except JoinedButCharacterNotPublished as error:
            joined = error.campaign
            publication = None
            QMessageBox.warning(self, "Campaign Joined — Upload Failed", str(error))
        except Exception as error:
            QMessageBox.warning(self, "Join Campaign Failed", str(error))
            return
        self.inline_join_code.clear()
        self.inline_join_form.setVisible(False)
        self._legacy_target_campaign_id = str(joined.get("id") or "")
        self.reload_campaigns()
        if publication is not None:
            if publication.status == "needs_character":
                offer_create_character_after_join(
                    self, self.window, publication.campaign,
                    on_created=self._leave_campaign_surface_for_sheet,
                )
            else:
                _report_join_publication(self, publication)

    def _leave_campaign_surface_for_sheet(self):
        if self._embedded and self._host_dialog is not None:
            self._host_dialog.accept()
        else:
            self.accept()

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
        self._leave_campaign_surface_for_sheet()

    def save_to_campaign(self):
        selected = getattr(self, "_sharing_character", None)
        if not self.current_campaign or self.client is None or selected is None:
            return
        if str(getattr(selected, "id", "") or "") != str(getattr(getattr(self.window, "character", None), "id", "") or ""):
            QMessageBox.warning(self, "Open Campaign Character", "Open the campaign's linked character before saving its sheet.")
            return
        campaign_id = str(self.current_campaign.get("id") or "")
        window = self.window
        self._leave_campaign_surface_for_sheet()

        def save_and_link():
            # A campaign-wizard character has its own first-save admission hook
            # in frontend_2_8.py. Do not submit its request a second time.
            had_wizard_marker = isinstance(getattr(window, "_pending_campaign_character", None), dict)
            try:
                window.save_current_character()
            except Exception as error:
                QMessageBox.warning(window, "Save Character Failed", str(error))
                return
            if not getattr(window, "current_character_filepath", None) or getattr(window, "unsaved_changes", False):
                return
            if had_wizard_marker and not getattr(window, "_pending_campaign_character", None):
                return  # The main-sheet hook already linked or requested approval.
            try:
                dm_state = build_window_shared_state(window, campaign_id=campaign_id)
                admission = admit_character(window, self.current_campaign, self.client, dm_state)
                if admission.status == "approval_pending":
                    from types import SimpleNamespace
                    _show_campaign_approval_notice(window, SimpleNamespace(
                        character_name=str(getattr(window.character, "name", "Character") or "Character"),
                        mismatches=admission.mismatches,
                    ))
                    return
                if admission.status == "linked_elsewhere":
                    QMessageBox.warning(window, "Character Not Linked", "This character belongs to another campaign.")
                    return
                party_state = build_window_party_state(window, campaign_id=campaign_id)
                upload_party_state(self.client, campaign_id, admission.record_id, party_state)
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
        character_id = str(getattr(getattr(self, "_sharing_character", None), "id", "") or "")
        if not character_id:
            return
        self.client.unlink_local_character(character_id)
        if str(getattr(getattr(self.window, "character", None), "id", "") or "") == character_id:
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






class _InlineRulesResponsivePanels(QWidget):
    """Keep inline campaign rules readable across DPI and window widths."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        box = self.layout()
        if isinstance(box, QBoxLayout):
            direction = (QBoxLayout.Direction.LeftToRight
                         if self.width() >= 960
                         else QBoxLayout.Direction.TopToBottom)
            if box.direction() != direction:
                box.setDirection(direction)


class _CampaignHubNetworkJob(QRunnable):
    """Background-only network task. No QWidget is accessed off the GUI thread."""

    def __init__(self, results, kind, generation, operation):
        super().__init__()
        self.results = results
        self.kind = kind
        self.generation = generation
        self.operation = operation

    def run(self):
        try:
            payload = self.operation()
            error = None
        except Exception as exc:
            payload = None
            error = str(exc)
        self.results.put((self.kind, self.generation, payload, error))


class _CampaignCharacterOpenLabel(QLabel):
    """Double-click a verified linked name to return to its open sheet."""
    _on_open = None

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and callable(self._on_open):
            self._on_open()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and callable(self._on_open):
            self._on_open()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class CampaignsHubDialog(QDialog):
    """Single campaign home with permanent DM and Player tabs."""

    @staticmethod
    def _scrollable_panel(widget):
        """Offer wheel/touchpad scrolling without introducing a second gold border."""
        scroll = QScrollArea()
        scroll.setObjectName("HubContentScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(widget)
        return scroll

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.client = campaign_client(window)
        self.service = CampaignTemplateService(self.client) if self.client else None
        self.dm_campaigns = []
        self.player_campaigns = []
        self.current_dm_campaign = None
        self.current_player_campaign = None
        self._help_return_page = 0
        self._player_helper_needs_reload = True
        self._dm_details_dirty = False
        # Requests never execute in the GUI thread. Epochs discard responses
        # from campaigns the user has already switched away from.
        self._hub_results = SimpleQueue()
        self._hub_list_epoch = 0
        self._hub_dm_epoch = 0
        self._hub_discord_epoch = 0
        self._hub_player_link_epoch = 0
        self._hub_approval_epoch = 0
        self._hub_decision_epoch = 0
        self._hub_delete_epoch = 0
        self._hub_remove_epoch = 0
        self._hub_replace_epoch = 0
        self._hub_leave_epoch = 0
        self._hub_rules_epoch = 0
        self._hub_leave_in_flight = False
        self._hub_player_link_token = None
        self._hub_closed = False
        self._hub_poll_timer = QTimer(self)
        self._hub_poll_timer.setInterval(45)
        self._hub_poll_timer.timeout.connect(self._drain_hub_results)
        self._hub_poll_timer.start()
        self._did114_auto_epoch = 0
        self._did114_auto_pending = False
        self._did114_auto_timer = QTimer(self)
        self._did114_auto_timer.setInterval(20000)
        self._did114_auto_timer.timeout.connect(self._did114_poll_campaigns)
        self._did114_auto_timer.start()

        self.setWindowTitle("Campaigns")
        # Keep the Campaigns hub comfortably below full-screen height at the
        # common 150% Windows display scale.  1040 x 620 logical pixels maps
        # closely to the compact floating-window size used elsewhere in the app.
        self.setMinimumSize(760, 440)
        # Respect actual usable space at Windows 125% / 150% / 200% scaling.
        screen = self.screen() or QApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        self.resize(
            min(1040, max(760, available.width() - 64)) if available else 1040,
            min(620, max(440, available.height() - 64)) if available else 620,
        )
        set_themed_stylesheet(self, ROLE_QSS + """
        QPushButton#CampaignRoleTab, QPushButton#CampaignToolbarButton {
            background:#fffdf7; border:1px solid #c79a3b;
            border-radius:9px; color:#25190f; font-weight:900;
            min-height:35px; max-height:43px;
            min-width:0px; max-width:999px;
            padding:2px 10px;
        }
        QPushButton#CampaignRoleTab:hover, QPushButton#CampaignToolbarButton:hover { background:#fff4df; border-color:#a87824; }
        QPushButton#CampaignRoleTab:checked {
            background:#fffdf7; color:#25190f; border:2px solid #b98322;
        }
        QListWidget#CampaignList {
            background:#fffdf7; border:1px solid #d7b56d; border-radius:10px;
            padding:5px; color:#25190f; font-family:Georgia; font-size:13px;
            outline:none;
        }
        QListWidget#CampaignList:focus { outline:none; }
        QListWidget#CampaignList::item { padding:9px 10px; border-radius:7px; margin:1px; outline:none; }
        QListWidget#CampaignList::item:focus { outline:none; border:none; }
        QListWidget#CampaignList::item:selected { background:#fff1d6; color:#25190f; outline:none; }
        QFrame#CampaignPanel {
            background:#fffdf7; border:1px solid #d9bd82; border-radius:10px;
        }
        QFrame#CampaignSection {
            background:#fffdf7; border:1px solid #d9bd82; border-radius:9px;
        }
        QPushButton#HubPrimary { background:#fff1d6; border-color:#b98322; }
        QPushButton#HubPrimary:hover { background:#fff4df; }
        QScrollArea#HubContentScroll { background:transparent; border:none; }
        QScrollArea#HubContentScroll > QWidget > QWidget { background:transparent; }
        QTabWidget::pane { border:1px solid #c79a3b; border-radius:8px; background:#fffdf7; }
        QTabBar::tab { background:#fffaf0; border:1px solid #d9bd82; color:#25190f;
                       padding:7px 16px; min-width:70px; }
        QTabBar::tab:selected { background:#fff1d6; color:#25190f; border-color:#c79a3b; }
        QTabBar::tab:hover { background:#fff4df; }
        QTabBar::tab:disabled { color:#9b9388; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(0)

        header = QHBoxLayout()
        toolbar = QHBoxLayout()
        toolbar.setSpacing(6)
        self._campaign_actions_host = QWidget()
        self._campaign_actions_host.setVisible(False)
        self._campaign_actions_layout = QHBoxLayout(self._campaign_actions_host)
        self._campaign_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._campaign_actions_layout.setSpacing(6)
        self._campaign_actions_layout.addStretch(1)
        title_box = QVBoxLayout()
        title_box.setSpacing(1)
        title = QLabel("Campaigns")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Everything for campaigns you run and campaigns you play in, in one place.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        # Campaign-level DM actions live in the global header so they do not
        # consume vertical space inside the selected campaign panel.
        self.dm_dashboard_btn = QPushButton("DM Dashboard")
        self.dm_dashboard_btn.setObjectName("CompactButton")
        self.dm_dashboard_btn.clicked.connect(self.open_dm_dashboard)
        self.party_dashboard_dm_btn = QPushButton("Party Dashboard")
        self.party_dashboard_dm_btn.setObjectName("CompactButton")
        self.party_dashboard_dm_btn.clicked.connect(self.open_party_dashboard)
        self.discord_settings_btn = QPushButton("Connect Discord")
        self.discord_settings_btn.setObjectName("CompactButton")
        self.discord_settings_btn.clicked.connect(self.open_discord_settings)
        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):
            button.setVisible(False)
            _fit_button(button)
            self._campaign_actions_layout.addWidget(button)

        # Inline Campaign Creation Rules actions live in the Campaigns header,
        # not in the editor footer.  This keeps every rules page consistent
        # and preserves the bottom row for Back on the far left and the
        # positive Next/Save action on the far right.
        self.rules_back_campaign_btn = QPushButton("Back to Campaign")
        self.rules_back_campaign_btn.setObjectName("CompactButton")
        self.rules_back_campaign_btn.clicked.connect(self._close_inline_rules_editor)
        self.rules_back_campaign_btn.setVisible(False)
        self._campaign_actions_layout.addWidget(self.rules_back_campaign_btn)

        self.rules_load_btn = QPushButton("Load Rules")
        self.rules_load_btn.setObjectName("CompactButton")
        self.rules_load_btn.clicked.connect(self._load_inline_rules)
        self.rules_load_btn.setVisible(False)
        self._campaign_actions_layout.addWidget(self.rules_load_btn)

        toolbar.addStretch(1)
        self.help_btn = QPushButton("How to Use / Help")
        self.help_btn.setObjectName("CampaignToolbarButton")
        self.help_btn.clicked.connect(self._toggle_help)
        toolbar.addWidget(self.help_btn)
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("CampaignToolbarButton")
        self.refresh_btn.clicked.connect(self._refresh_hub_from_button)
        toolbar.addWidget(self.refresh_btn)
        # Matching buttons: avoid different content-derived widths.
        # Campaign toolbar dimensions are managed by _resize_campaign_tabs.
        root.addLayout(header)
        root.addSpacing(6)
        root.addLayout(toolbar)

        # 1.0.14: campaign tabs sit together above the list
        tabs_host = QWidget()
        self._campaign_tabs_host = tabs_host
        tabs_host.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        tabs = QHBoxLayout(tabs_host)
        tabs.setContentsMargins(0, 0, 0, 0)
        tabs.setSpacing(6)
        self.dm_tab_btn = QPushButton("DM Campaigns")
        self.dm_tab_btn.setObjectName("CampaignRoleTab")
        self.dm_tab_btn.setCheckable(True)
        self.dm_tab_btn.clicked.connect(lambda: self._show_role_page(0))
        self.player_tab_btn = QPushButton("Player Campaigns")
        self.player_tab_btn.setObjectName("CampaignRoleTab")
        self.player_tab_btn.setCheckable(True)
        self.player_tab_btn.clicked.connect(lambda: self._show_role_page(1))
        tabs.addWidget(self.dm_tab_btn, 1)
        tabs.addWidget(self.player_tab_btn, 1)
        # DM/Player tabs and Help/Refresh now share one compact toolbar.
        toolbar.insertWidget(0, tabs_host)
        root.addWidget(self._campaign_actions_host, 0, Qt.AlignmentFlag.AlignRight)
        root.addSpacing(4)

        self.role_pages = QStackedWidget()
        self.role_pages.addWidget(self._build_dm_page())
        self.role_pages.addWidget(self._build_player_page())
        self.role_pages.addWidget(self._build_help_page())
        root.addWidget(self.role_pages, 1)

        # No separate Close button is needed. The Campaigns window uses the
        # normal title-bar close control, leaving the full height available to
        # campaign content.
        self._show_role_page(0)
        self.reload_campaigns()
        QTimer.singleShot(0, lambda: _did_1013_align_help_refresh(self))

    # DID114_COMPACT_CAMPAIGN_TOOLBAR_V1: consistent sizing at Windows DPI scales.
    def _resize_campaign_tabs(self):
        tabs = (self.dm_tab_btn, self.player_tab_btn)
        for button in tabs:
            button.ensurePolished()
        width = max(160, *(button.fontMetrics().horizontalAdvance(button.text()) + 30 for button in tabs))
        for button in tabs:
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)
            button.setFixedSize(width, 38)
        self._campaign_tabs_host.setFixedWidth(2 * width + 6)
        # Help/Refresh share their size, but are not as wide as the campaign tabs.
        help_width = max(128, self.help_btn.fontMetrics().horizontalAdvance("How to Use / Help") + 24)
        for button in (self.help_btn, self.refresh_btn):
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)
            button.setFixedSize(help_width, 38)

    def _show_role_page(self, index):
        index = 0 if int(index) == 0 else 1
        self.role_pages.setCurrentIndex(index)
        self.dm_tab_btn.setChecked(index == 0)
        self.player_tab_btn.setChecked(index == 1)
        self.help_btn.setText("How to Use / Help")
        self._resize_campaign_tabs()
        self._update_header_actions()
        # A refresh from the Player tab should not fetch hidden DM characters,
        # approval requests, or Discord state. Fetch only on entering the tab.
        if index == 0 and self._dm_details_dirty:
            self._refresh_dm_details()

    def _toggle_help(self):
        if self.role_pages.currentIndex() == 2:
            self._show_role_page(self._help_return_page)
            return
        active = self.role_pages.currentIndex()
        self._help_return_page = active if active in (0, 1) else 0
        self.role_pages.setCurrentIndex(2)
        self.help_btn.setText("← Back")
        self.dm_tab_btn.setChecked(False)
        self.player_tab_btn.setChecked(False)
        self._update_header_actions()

    def _build_help_page(self):
        """Integrated read-only guide in the same Campaigns dialog."""
        frame = QFrame()
        frame.setObjectName("CampaignPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(18, 12, 18, 12)
        title = QLabel("How to Use Campaigns")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        tabs = QTabWidget(frame)
        tabs.setDocumentMode(False)
        tabs.tabBar().setExpanding(False)
        set_themed_stylesheet(tabs.tabBar(), """
            QTabBar::tab { background:#fffdf7; color:#25190f; border:1px solid #c79a3b;
                border-radius:9px; padding:8px 19px; min-height:28px; min-width:94px;
                margin-right:7px; font-family:Georgia; font-size:12px; font-weight:900; }
            QTabBar::tab:selected { background:#fff1d6; border:2px solid #b98322; }
            QTabBar::tab:hover { background:#fff4df; }
        """)
        player = QTextBrowser()
        dm = QTextBrowser()
        for pane in (player, dm):
            pane.setOpenExternalLinks(False)
            set_themed_stylesheet(pane, "QTextBrowser { background:#fffdf7; color:#25190f; font-family:Georgia; font-size:13px; border:1px solid #c79a3b; padding:12px; }")
        player.setHtml("""
            <h2>For players</h2>
            <h3>Joining a campaign</h3>
            <p>Choose <b>Player Campaigns</b> and <b>Join Campaign</b>. Paste the
            invitation code supplied by your DM, then select the campaign.</p>
            <h3>Link or create a character</h3>
            <p>Clicking <b>Join</b> connects you to the campaign and immediately
            sends your currently open, named character to the DM. Its future
            changes synchronize automatically. If you have no named character
            open yet, use <b>Character &amp; Sharing</b> to create one using the
            campaign rules. Saving a newly created campaign character links and
            sends it automatically. <b>Save to Campaign</b> is available as a
            manual retry if a previous upload failed. Existing characters may
            not satisfy campaign rules. In that case the app explains the exact
            differences and sends a private <b>DM approval request</b>. Your
            character remains unlinked until the DM approves it. Rejected
            characters can be edited locally and submitted again.</p>
            <h3>Privacy and shared information</h3>
            <p>Use the sharing settings to control what the DM and other players
            can see in shared views. Inventory, notes and other details are
            subject to those preferences. Set session dice-roll sharing separately.</p>
            <h3>Party Dashboard and sessions</h3>
            <p>Open <b>Party Dashboard</b> to view the shared party information.
            A session's available features depend on its active status and the
            DM's setup. Your local character is kept on your computer.</p>
            <h3>Discord participation</h3>
            <p>If your DM has linked a Discord channel, use the available DID
            commands in that channel. Discord commands require the service to
            be configured and online.</p>
        """)
        dm.setHtml("""
            <h2>For Dungeon Masters</h2>
            <h3>Create a campaign</h3>
            <p>Choose <b>DM Campaigns</b> and <b>New Campaign</b>. Choose a name
            and set <b>Character Creation Rules</b>. Review participating
            characters whenever rules are changed.</p>
            <h3>Invite and manage players</h3>
            <p>Copy your campaign invitation code or invitation text and share
            it with players. The campaign character list shows shared characters.
            Any existing character that violates the campaign rules appears
            in <b>Character approval requests</b>. Review the listed differences
            and choose <b>Approve Character</b> or <b>Reject</b>. Only approved
            characters enter the campaign's active character list.
            The <b>×</b> beside a character removes it from the campaign without
            deleting the player's local character file.</p>
            <h3>Dashboards and sharing</h3>
            <p><b>DM Dashboard</b> opens your management view. <b>Party Dashboard</b>
            opens the shared party view. Information visibility depends on each
            player's sharing/privacy settings.</p>
            <h3>Discord setup</h3>
            <p>Choose <b>Connect Discord</b> in the selected campaign and follow
            the on-screen steps to link the desired channel using
            <b>/did-connect</b>. This requires an available Discord service.</p>
            <h3>Sessions</h3>
            <p>Use the campaign's session controls to start and end sessions.
            Session data and recorded dice rolls depend on players' sharing
            choices and on the connected services.</p>
        """)
        tabs.addTab(player, "Players")
        tabs.addTab(dm, "DMs")
        layout.addWidget(tabs, 1)
        return frame

    def _update_header_actions(self):
        show_dm_actions = (
            hasattr(self, "role_pages")
            and self.role_pages.currentIndex() == 0
            and bool(self.current_dm_campaign)
            and getattr(self, "_inline_rules_editor", None) is None
        )
        for name in ("dm_dashboard_btn", "party_dashboard_dm_btn", "discord_settings_btn"):
            button = getattr(self, name, None)
            if button is not None:
                button.setVisible(show_dm_actions)
                button.setEnabled(show_dm_actions)
        self._campaign_actions_host.setVisible(
            show_dm_actions or getattr(self, "_inline_rules_editor", None) is not None
        )

    def _build_dm_page(self):
        page = QWidget()
        body = QHBoxLayout(page)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        left = QFrame()
        left.setObjectName("CampaignPanel")
        left.setMinimumWidth(205)
        left.setMaximumWidth(280)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        box = QVBoxLayout(left)
        box.setContentsMargins(12, 12, 12, 12)
        box.setSpacing(8)
        heading = QLabel("Campaigns you DM")
        heading.setStyleSheet("font-size:17px; font-weight:900;")
        box.addWidget(heading)
        hint = QLabel("Create, select and manage your campaigns here.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        box.addWidget(hint)
        self.dm_list = QListWidget()
        self.dm_list.setObjectName("CampaignList")
        self.dm_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.dm_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.dm_list.currentRowChanged.connect(self._dm_selection_changed)
        box.addWidget(self.dm_list, 1)
        self.new_btn = QPushButton("+ New Campaign")
        self.new_btn.setObjectName("HubPrimary")
        self.new_btn.clicked.connect(self.new_campaign)
        box.addWidget(self.new_btn)
        body.addWidget(left)

        right = QFrame()
        right.setObjectName("CampaignPanel")
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(18, 15, 18, 15)
        right_box.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(8)
        name_and_invite = QVBoxLayout()
        name_and_invite.setSpacing(2)
        self.dm_name_label = QLabel("Select a campaign")
        self.dm_name_label.setStyleSheet("font-size:22px; font-weight:900;")
        self.dm_name_label.setWordWrap(True)
        self.dm_name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        name_and_invite.addWidget(self.dm_name_label)
        invite_row = QHBoxLayout()
        invite_row.setSpacing(5)
        self.dm_invite_label = QLabel("Invite code:")
        invite_row.addWidget(self.dm_invite_label)
        self.dm_invite_code = QPushButton("")
        self.dm_invite_code.setObjectName("InviteCodeButton")
        self.dm_invite_code.setToolTip("Click for copy options")
        self.dm_invite_code.clicked.connect(self.copy_invite_code)
        invite_row.addWidget(self.dm_invite_code)
        invite_row.addStretch(1)
        name_and_invite.addLayout(invite_row)
        top.addLayout(name_and_invite, 1)
        self.delete_campaign_btn = QPushButton("Delete Campaign")
        self.delete_campaign_btn.setObjectName("DangerButton")
        self.delete_campaign_btn.clicked.connect(self.delete_dm_campaign)
        self.delete_campaign_btn.setVisible(False)  # Hidden until a DM campaign is selected.
        _fit_button(self.delete_campaign_btn)
        top.addWidget(self.delete_campaign_btn, 0, Qt.AlignmentFlag.AlignTop)
        right_box.addLayout(top)

        self.dm_empty = QLabel("Create a campaign to get started.")
        self.dm_empty.setObjectName("SectionText")
        right_box.addWidget(self.dm_empty)

        self.dm_content = QWidget()
        content = QVBoxLayout(self.dm_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(10)

        char_section = QFrame()
        char_section.setObjectName("CampaignSection")
        chars = QVBoxLayout(char_section)
        chars.setContentsMargins(12, 10, 12, 10)
        chars.setSpacing(6)
        char_head = QHBoxLayout()
        char_title = QLabel("Characters")
        char_title.setStyleSheet("font-size:15px; font-weight:900;")
        char_head.addWidget(char_title)
        char_head.addStretch()
        chars.addLayout(char_head)
        self.dm_character_scroll = QScrollArea()
        self.dm_character_scroll.setWidgetResizable(True)
        self.dm_character_scroll.setMinimumHeight(88)
        self.dm_character_scroll.setMaximumHeight(290)
        self.dm_character_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.dm_character_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.dm_character_scroll.setStyleSheet(
            "QScrollArea, QScrollArea > QWidget > QWidget { border:none; background:transparent; }"
        )
        self.dm_character_body = QWidget()
        self.dm_character_body.setStyleSheet("background:transparent;")
        self.dm_character_layout = QVBoxLayout(self.dm_character_body)
        self.dm_character_layout.setContentsMargins(0, 0, 0, 0)
        self.dm_character_layout.setSpacing(5)
        self.dm_character_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.dm_character_scroll.setWidget(self.dm_character_body)
        chars.addWidget(self.dm_character_scroll)
        content.addWidget(char_section)

        rules_section = QFrame()
        rules_section.setObjectName("CampaignSection")
        rules = QVBoxLayout(rules_section)
        rules.setContentsMargins(12, 10, 12, 10)
        rules.setSpacing(7)

        rules_head = QHBoxLayout()
        rules_title = QLabel("Character Creation Rules")
        rules_title.setStyleSheet("font-size:15px; font-weight:900;")
        rules_head.addWidget(rules_title)
        rules_head.addStretch()
        self.edit_rules_btn = QPushButton("Edit Rules")
        self.edit_rules_btn.setObjectName("CompactButton")
        self.edit_rules_btn.clicked.connect(self.edit_dm_rules)
        rules_head.addWidget(self.edit_rules_btn)
        rules.addLayout(rules_head)

        # Keep the rules summary intentionally simple.  It is one permanent
        # panel with three rows; campaign changes only replace label text.
        # This avoids nested/rebuilt card widgets and makes the DM screen much
        # easier to scan.
        summary_grid = QGridLayout()
        summary_grid.setContentsMargins(0, 2, 0, 0)
        summary_grid.setHorizontalSpacing(16)
        summary_grid.setVerticalSpacing(5)
        self.dm_rule_summary_labels = {}
        for row_index, section_name in enumerate((
            "Starting Character",
            "Resources",
            "Character Options",
        )):
            section_label = QLabel(section_name)
            section_label.setStyleSheet("font-weight:900; font-size:12px;")
            section_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            value_label = QLabel("-")
            value_label.setObjectName("Muted")
            value_label.setWordWrap(True)
            set_themed_stylesheet(value_label, "QLabel { color:#6c5428; font-size:11px; }")
            summary_grid.addWidget(section_label, row_index, 0)
            summary_grid.addWidget(value_label, row_index, 1)
            self.dm_rule_summary_labels[section_name] = value_label
        summary_grid.setColumnMinimumWidth(0, 135)
        summary_grid.setColumnStretch(1, 1)
        rules.addLayout(summary_grid)
        content.addWidget(rules_section)
        content.addStretch(1)

        # The scrollable details area keeps the name / invite / delete row
        # visible while allowing rich rules and approval cards on short screens.
        self.dm_detail_scroll = self._scrollable_panel(self.dm_content)
        right_box.addWidget(self.dm_detail_scroll, 1)
        body.addWidget(right, 1)
        return page

    def _build_player_page(self):
        # Join is a dedicated page. The campaign list and all dashboard/character
        # controls are wholly absent while the user enters an invitation.
        page = QStackedWidget()
        self.player_workspace_stack = page
        workspace = QWidget()
        body = QHBoxLayout(workspace)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(14)

        # Keep the existing player-campaign logic as a hidden controller, but
        # do not expose its old wizard shell.  The visible Player tab below is
        # a normal campaign workspace, matching the DM tab.
        self.player_helper = PlayerCampaignsDialog(
            self.window, embedded=True, host_dialog=self,
            defer_initial_reload=True,
        )
        self.player_helper.hide()

        left = QFrame()
        left.setObjectName("CampaignPanel")
        left.setMinimumWidth(205)
        left.setMaximumWidth(280)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        left_box = QVBoxLayout(left)
        left_box.setContentsMargins(12, 12, 12, 12)
        left_box.setSpacing(8)

        heading = QLabel("Campaigns you play in")
        heading.setStyleSheet("font-size:17px; font-weight:900;")
        left_box.addWidget(heading)
        hint = QLabel("Select a campaign, or join one with an invite code.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        left_box.addWidget(hint)

        self.player_list = QListWidget()
        self.player_list.setObjectName("CampaignList")
        self.player_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.player_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.player_list.currentRowChanged.connect(self._player_selection_changed)
        left_box.addWidget(self.player_list, 1)

        self.join_player_campaign_btn = QPushButton("+ Join Campaign")
        self.join_player_campaign_btn.setObjectName("HubPrimary")
        self.join_player_campaign_btn.clicked.connect(self._show_player_join_form)
        left_box.addWidget(self.join_player_campaign_btn)
        body.addWidget(left)

        right = QFrame()
        right.setObjectName("CampaignPanel")
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(18, 15, 18, 15)
        right_box.setSpacing(10)

        # Keep the selected campaign heading and its description fixed at the
        # top of the player panel. Previously both labels were embedded inside
        # the scrollable overview, so opening a join form or scrolling moved
        # them away from the header position.
        self.player_header = QWidget()
        header_layout = QVBoxLayout(self.player_header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self.player_name_label = QLabel("No player campaigns yet")
        self.player_name_label.setStyleSheet("font-size:22px; font-weight:900;")
        self.player_name_label.setWordWrap(True)
        self.player_name_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.player_name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        header_layout.addWidget(self.player_name_label)

        self.player_explainer = QLabel("Join a campaign with an invite code to see it here.")
        self.player_explainer.setObjectName("SectionText")
        self.player_explainer.setWordWrap(True)
        self.player_explainer.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.player_explainer.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        header_layout.addWidget(self.player_explainer)
        right_box.addWidget(self.player_header, 0, Qt.AlignmentFlag.AlignTop)

        self.player_detail_stack = QStackedWidget()

        # ---- Campaign overview -------------------------------------------------
        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)
        overview_layout.setContentsMargins(0, 0, 0, 0)
        overview_layout.setSpacing(6)
        overview_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.player_content = QWidget()
        player_content_layout = QVBoxLayout(self.player_content)
        player_content_layout.setContentsMargins(0, 0, 0, 0)
        player_content_layout.setSpacing(10)

        actions_section = QFrame()
        actions_section.setObjectName("CampaignSection")
        actions_layout = QHBoxLayout(actions_section)
        actions_layout.setContentsMargins(12, 10, 12, 10)
        actions_layout.setSpacing(8)
        self.player_party_dashboard_btn = QPushButton("Party Dashboard")
        self.player_party_dashboard_btn.clicked.connect(self.open_party_dashboard)
        self.player_character_sharing_btn = QPushButton("Character & Sharing")
        # Match the neighboring Party Dashboard and Campaign Info buttons.
        self.player_character_sharing_btn.clicked.connect(self._show_player_character_page)
        self.player_campaign_info_btn = QPushButton("Campaign Info")
        self.player_campaign_info_btn.clicked.connect(self._show_player_info_page)
        actions_layout.addWidget(self.player_party_dashboard_btn)
        actions_layout.addWidget(self.player_character_sharing_btn)
        actions_layout.addWidget(self.player_campaign_info_btn)
        actions_layout.addStretch()
        player_content_layout.addWidget(actions_section)
        self.player_inline_section = QFrame()
        self.player_inline_section.setObjectName("CampaignSection")
        inline_layout = QVBoxLayout(self.player_inline_section)
        inline_layout.setContentsMargins(8, 8, 8, 8)
        self.player_inline_stack = QStackedWidget()
        # A bounded height lets the sharing matrix scroll independently
        # without replacing the campaign overview or its left list.
        self.player_inline_stack.setFixedHeight(475)
        inline_layout.addWidget(self.player_inline_stack)
        self.player_inline_section.setVisible(False)
        player_content_layout.addWidget(self.player_inline_section)

        character_section = QFrame()
        character_section.setObjectName("CampaignSection")
        character_layout = QVBoxLayout(character_section)
        character_layout.setContentsMargins(12, 10, 12, 10)
        character_layout.setSpacing(6)
        character_title = QLabel("My Character")
        character_title.setStyleSheet("font-size:15px; font-weight:900;")
        character_layout.addWidget(character_title)
        self.player_character_name = _CampaignCharacterOpenLabel("-")
        self.player_character_name.setStyleSheet("font-size:14px; font-weight:900;")
        self.player_character_name._on_open = self._open_linked_player_character
        character_layout.addWidget(self.player_character_name)
        self.player_character_status = QLabel("")
        self.player_character_status.setObjectName("Muted")
        self.player_character_status.setWordWrap(True)
        character_layout.addWidget(self.player_character_status)
        self.player_add_character_btn = QPushButton("+ Add Character")
        self.player_add_character_btn.setObjectName("HubPrimary")
        self.player_add_character_btn.clicked.connect(self._select_player_campaign_character)
        self.player_add_character_btn.setVisible(False)
        character_layout.addWidget(self.player_add_character_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.player_replace_character_btn = QPushButton("Remove / Replace Character")
        self.player_replace_character_btn.setObjectName("CompactButton")
        self.player_replace_character_btn.clicked.connect(self._replace_player_character)
        self.player_replace_character_btn.setVisible(False)
        character_layout.addWidget(self.player_replace_character_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.player_leave_campaign_btn = QPushButton("Leave Campaign")
        self.player_leave_campaign_btn.setObjectName("CompactButton")
        self.player_leave_campaign_btn.clicked.connect(self._leave_player_campaign)
        self.player_leave_campaign_btn.setVisible(False)
        character_layout.addWidget(self.player_leave_campaign_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.player_character_section = character_section
        player_content_layout.addWidget(character_section)

        rules_section = QFrame()
        rules_section.setObjectName("CampaignSection")
        rules_layout = QVBoxLayout(rules_section)
        rules_layout.setContentsMargins(12, 10, 12, 10)
        rules_layout.setSpacing(7)
        rules_title = QLabel("Character Creation Rules")
        rules_title.setStyleSheet("font-size:15px; font-weight:900;")
        rules_layout.addWidget(rules_title)
        rules_grid = QGridLayout()
        rules_grid.setContentsMargins(0, 2, 0, 0)
        rules_grid.setHorizontalSpacing(16)
        rules_grid.setVerticalSpacing(5)
        self.player_rule_summary_labels = {}
        for row_index, section_name in enumerate((
            "Starting Character", "Resources", "Character Options"
        )):
            section_label = QLabel(section_name)
            section_label.setStyleSheet("font-weight:900; font-size:12px;")
            section_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
            value_label = QLabel("-")
            value_label.setObjectName("Muted")
            value_label.setWordWrap(True)
            set_themed_stylesheet(value_label, "QLabel { color:#6c5428; font-size:11px; }")
            rules_grid.addWidget(section_label, row_index, 0)
            rules_grid.addWidget(value_label, row_index, 1)
            self.player_rule_summary_labels[section_name] = value_label
        rules_grid.setColumnMinimumWidth(0, 135)
        rules_grid.setColumnStretch(1, 1)
        rules_layout.addLayout(rules_grid)
        player_content_layout.addWidget(rules_section)
        rules_section.setVisible(False)
        # DID114_PLAYER_REVEALS: Read-only content revealed by the DM.
        reveals_section = QFrame()
        reveals_section.setObjectName("CampaignSection")
        reveals_layout = QVBoxLayout(reveals_section)
        reveals_layout.setContentsMargins(12, 10, 12, 10)
        reveals_layout.setSpacing(6)
        reveals_title = QLabel("Effects on My Character")
        reveals_title.setStyleSheet("font-size:15px; font-weight:900;")
        reveals_layout.addWidget(reveals_title)
        hooks_title = QLabel("Hooks, Clues & Quests")
        hooks_title.setStyleSheet("font-size:12px; font-weight:900;")
        # DID114_OVERVIEW_HOOK_DEDUP_V3: redundant overview element omitted.
        self.player_shared_hooks = QLabel("Press Refresh to load shared hooks.")
        self.player_shared_hooks.setObjectName("Muted")
        self.player_shared_hooks.setTextFormat(Qt.TextFormat.PlainText)
        self.player_shared_hooks.setWordWrap(True)
        # DID114_OVERVIEW_HOOK_DEDUP_V3: redundant overview element omitted.
        effects_title = QLabel("Effects on My Character")
        effects_title.setStyleSheet("font-size:12px; font-weight:900;")
        # DID114_OVERVIEW_HOOK_DEDUP_V3: redundant overview element omitted.
        self.player_shared_effects = QLabel("No effects loaded.")
        self.player_shared_effects.setObjectName("Muted")
        self.player_shared_effects.setTextFormat(Qt.TextFormat.PlainText)
        self.player_shared_effects.setWordWrap(True)
        reveals_layout.addWidget(self.player_shared_effects)
        self.player_effects_section = reveals_section
        player_content_layout.addWidget(reveals_section)
        player_content_layout.addStretch(1)
        overview_layout.addWidget(self.player_content, 1)

        # Inline join form.  It lives in this same Campaigns window rather
        # than opening prompts or another dialog.
        self.player_join_form = QFrame()
        self.player_join_form.setObjectName("CampaignSection")
        self.player_join_form.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.player_join_form.setMaximumHeight(178)
        join_layout = QGridLayout(self.player_join_form)
        join_layout.setContentsMargins(14, 12, 14, 12)
        join_layout.setHorizontalSpacing(10)
        join_layout.setVerticalSpacing(8)
        join_layout.addWidget(QLabel("Invite code"), 0, 0)
        self.player_join_code = QLineEdit()
        self.player_join_code.setPlaceholderText("Enter campaign invite code")
        self.player_join_code.setFixedHeight(38)
        self.player_join_code.setStyleSheet("QLineEdit { font-family: Consolas, 'Courier New', monospace; font-size:15px; font-weight:600; }")
        join_layout.addWidget(self.player_join_code, 0, 1)
        join_layout.addWidget(QLabel("Your name"), 1, 0)
        self.player_join_name = QLineEdit()
        self.player_join_name.setPlaceholderText("Name shown to the DM")
        self.player_join_name.setFixedHeight(38)
        join_layout.addWidget(self.player_join_name, 1, 1)
        join_buttons = QHBoxLayout()
        cancel_join = QPushButton("Cancel")
        cancel_join.setObjectName("CompactButton")
        cancel_join.clicked.connect(self._hide_player_join_form)
        confirm_join = QPushButton("Join")
        confirm_join.setObjectName("HubPrimary")
        confirm_join.clicked.connect(self._submit_player_join)
        join_buttons.addWidget(cancel_join)
        join_buttons.addStretch()
        join_buttons.addWidget(confirm_join)
        join_layout.addLayout(join_buttons, 2, 0, 1, 2)
        join_layout.setColumnStretch(1, 1)
        self.player_join_form.setVisible(False)
        overview_layout.insertWidget(0, self.player_join_form)

        self.player_overview_scroll = self._scrollable_panel(overview_page)
        self.player_detail_stack.addWidget(self.player_overview_scroll)

        # ---- Character/sharing page -------------------------------------------
        # Reuse the mature sharing controls from PlayerCampaignsDialog, but
        # remove them from the old step wizard and place them directly inside
        # this Campaigns window.
        character_page = self.player_helper.pages.widget(1)
        self.player_helper.pages.removeWidget(character_page)
        self._did_1013_character_content = character_page
        character_host = QWidget()
        character_host_layout = QVBoxLayout(character_host)
        character_host_layout.setContentsMargins(0, 0, 0, 0)
        character_host_layout.setSpacing(8)
        back_row = QHBoxLayout()
        back_btn = QPushButton("Close Character Sharing")
        back_btn.setObjectName("CompactButton")
        back_btn.clicked.connect(self._show_player_overview)
        back_row.addWidget(back_btn)
        back_row.addStretch()
        character_host_layout.addLayout(back_row)
        character_page.setParent(character_host)
        character_host_layout.addWidget(character_page, 1)
        self.player_inline_stack.addWidget(character_host)

        # Phase 8 adds a player-safe Campaign Info page.  Keep that useful
        # surface, but present it as another in-place page instead of another
        # wizard step/window.
        self.player_info_stack_index = None
        if self.player_helper.pages.count() >= 3:
            info_page = self.player_helper.pages.widget(self.player_helper.pages.count() - 1)
            self.player_helper.pages.removeWidget(info_page)
            self._did_1013_info_content = info_page
            info_host = QWidget()
            info_host_layout = QVBoxLayout(info_host)
            info_host_layout.setContentsMargins(0, 0, 0, 0)
            info_host_layout.setSpacing(8)
            info_back_row = QHBoxLayout()
            info_back = QPushButton("Close Campaign Info")
            info_back.setObjectName("CompactButton")
            info_back.clicked.connect(self._show_player_overview)
            info_back_row.addWidget(info_back)
            info_back_row.addStretch()
            info_host_layout.addLayout(info_back_row)
            info_page.setParent(info_host)
            info_host_layout.addWidget(info_page, 1)
            self.player_info_stack_index = self.player_inline_stack.addWidget(info_host)

        right_box.addWidget(self.player_detail_stack, 1)
        body.addWidget(right, 1)
        page.addWidget(workspace)
        page.addWidget(self._build_player_join_page())
        page.setCurrentIndex(0)
        return page

    def _build_player_join_page(self):
        page = QFrame()
        page.setObjectName("CampaignPanel")
        root = QVBoxLayout(page)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)
        title = QLabel("Join a Campaign")
        title.setStyleSheet("font-size:22px; font-weight:900;")
        root.addWidget(title)
        self.join_step_intro = QLabel("Enter the invitation code from your DM.")
        self.join_step_intro.setObjectName("Muted")
        self.join_step_intro.setWordWrap(True)
        root.addWidget(self.join_step_intro)

        self.join_code_section = QWidget()
        code_layout = QVBoxLayout(self.join_code_section)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_layout.setSpacing(10)
        code_layout.addWidget(QLabel("Invite code"))
        self.join_code_field = QLineEdit()
        self.join_code_field.setObjectName("CampaignInviteCodeInput")
        self.join_code_field.setPlaceholderText("Enter campaign invite code")
        self.join_code_field.setMaxLength(64)
        self.join_code_field.setFixedHeight(42)
        self.join_code_field.setStyleSheet(
            "QLineEdit { font-family: Consolas, 'Courier New', monospace; "
            "font-size:15px; font-weight:600; letter-spacing:1px; }"
        )
        self.join_code_field.returnPressed.connect(self._resolve_player_invite)
        code_layout.addWidget(self.join_code_field)
        root.addWidget(self.join_code_section)

        self.join_choice_section = QWidget()
        choice_layout = QVBoxLayout(self.join_choice_section)
        choice_layout.setContentsMargins(0, 0, 0, 0)
        choice_layout.setSpacing(8)
        self.join_campaign_title = QLabel("")
        self.join_campaign_title.setStyleSheet("font-size:18px;font-weight:900;")
        choice_layout.addWidget(self.join_campaign_title)
        self.join_candidate_help = QLabel(
            "Select a saved character. Characters not created with this "
            "campaign's rules may require DM approval."
        )
        self.join_candidate_help.setWordWrap(True)
        self.join_candidate_help.setObjectName("Muted")
        choice_layout.addWidget(self.join_candidate_help)
        self.join_character_list = QListWidget()
        self.join_character_list.setObjectName("CampaignList")
        self.join_character_list.setMinimumHeight(165)
        self.join_character_list.currentRowChanged.connect(self._join_candidate_changed)
        choice_layout.addWidget(self.join_character_list, 1)
        self.join_candidate_details = QLabel("")
        self.join_candidate_details.setObjectName("Muted")
        self.join_candidate_details.setWordWrap(True)
        choice_layout.addWidget(self.join_candidate_details)
        self.join_create_btn = QPushButton("+ Create New Using Campaign Rules")
        self.join_create_btn.setObjectName("HubPrimary")
        self.join_create_btn.clicked.connect(self._create_character_for_joined_campaign)
        choice_layout.addWidget(self.join_create_btn, 0, Qt.AlignmentFlag.AlignLeft)
        self.join_choice_section.hide()
        root.addWidget(self.join_choice_section, 1)

        buttons = QHBoxLayout()
        self.join_cancel_btn = QPushButton("Cancel")
        self.join_cancel_btn.setObjectName("CompactButton")
        self.join_cancel_btn.clicked.connect(self._hide_player_join_form)
        buttons.addWidget(self.join_cancel_btn)
        buttons.addStretch(1)
        self.join_confirm_btn = QPushButton("Continue")
        self.join_confirm_btn.setObjectName("HubPrimary")
        self.join_confirm_btn.clicked.connect(self._submit_player_join)
        buttons.addWidget(self.join_confirm_btn)
        root.addLayout(buttons)
        return page

    def _resolve_player_invite(self):
        """Join account membership first, *never* silently publish the open sheet."""
        if self.service is None:
            QMessageBox.warning(self, "Not Connected", "Sign in to join campaigns.")
            return
        code = str(self.join_code_field.text() or "").strip()
        if not code:
            self.join_code_field.setFocus()
            return
        self.join_confirm_btn.setEnabled(False)
        try:
            # The name is derived from the chosen character in the next step.
            # Joining here grants account membership, NOT character admission.
            joined = self.service.join_campaign(code, "Player")
        except Exception as error:
            QMessageBox.warning(self, "Cannot Join Campaign", str(error))
            return
        finally:
            self.join_confirm_btn.setEnabled(True)
        linked_id, existing_record = self._campaign_character_record(joined)
        if linked_id and existing_record:
            QMessageBox.information(
                self, "Character Already Selected",
                "This campaign already has a linked or pending character. "
                "Use Remove / Replace Character on the campaign overview first."
            )
            self._hide_player_join_form()
            self.reload_campaigns(select_player_id=str(joined.get("id") or ""))
            return
        self._joined_campaign_candidate = joined
        self.join_cancel_btn.setText("Later")
        self.join_code_section.hide()
        self.join_choice_section.show()
        self.join_step_intro.setText(
            "Choose a local character or create a new character with this campaign's rules. "
            "Only an approved character can open Party Dashboard and Campaign Info."
        )
        self.join_campaign_title.setText(str(joined.get("name") or "Campaign"))
        self.join_confirm_btn.setText("Use Selected Character")
        self._populate_join_candidates(joined)

    def _populate_join_candidates(self, campaign):
        import os
        from backend_2_1 import CharacterStorageSystem
        from campaign_template import character_rule_mismatches
        self._join_character_options = []
        self.join_character_list.clear()
        CharacterStorageSystem.ensure_save_dir()
        save_dir = CharacterStorageSystem.SAVE_DIR
        for directory, subdirs, filenames in os.walk(save_dir):
            subdirs[:] = [d for d in subdirs if d != "_history"]
            for filename in sorted(filenames, key=str.casefold):
                if not filename.lower().endswith(".didchar"):
                    continue
                path = os.path.join(directory, filename)
                try:
                    if not CharacterStorageSystem.looks_like_character_file(path):
                        continue
                    character = CharacterStorageSystem.import_character_file(path)
                    name = str(getattr(character, "name", "") or "").strip()
                    if not name or name.lower() == "unnamed character":
                        continue
                    differences = character_rule_mismatches(character, campaign_template(campaign))
                    status = "Matches rules" if not differences else "DM approval may be required"
                    item = QListWidgetItem(f"{name}  —  {status}")
                    item.setData(Qt.ItemDataRole.UserRole, path)
                    self.join_character_list.addItem(item)
                    self._join_character_options.append((path, tuple(differences)))
                except Exception:
                    continue
        if self.join_character_list.count():
            self.join_character_list.setCurrentRow(0)
        else:
            self.join_candidate_details.setText(
                "No saved characters found. Create a new character using the campaign rules below."
            )
        self.join_confirm_btn.setEnabled(self.join_character_list.count() > 0)

    def _join_candidate_changed(self, row):
        choices = getattr(self, "_join_character_options", [])
        if row < 0 or row >= len(choices):
            self.join_candidate_details.setText("Choose a saved character to continue.")
            self.join_confirm_btn.setEnabled(False)
            return
        differences = choices[row][1]
        if differences:
            translated = [
                "This character was not originally created from a Creation Rules template."
                if "Creation Rules enabled" in difference else difference
                for difference in differences
            ]
            self.join_candidate_details.setText(
                "This character may need DM approval:\n" + "\n".join("• " + d for d in translated[:4])
            )
        else:
            self.join_candidate_details.setText("Matches the campaign's character creation rules.")
        self.join_confirm_btn.setEnabled(True)

    def _create_character_for_joined_campaign(self):
        campaign = getattr(self, "_joined_campaign_candidate", None)
        if not isinstance(campaign, dict):
            return
        try:
            if not _replace_current_character(self.window, campaign_template(campaign)):
                return
            character_id = str(getattr(self.window.character, "id", "") or "")
            self.window._pending_campaign_character = {
                "campaign_id": str(campaign.get("id") or ""),
                "campaign_name": str(campaign.get("name") or "Campaign"),
                "invite_code": str(self.join_code_field.text() or "").strip(),
                "character_id": character_id,
            }
        except Exception as error:
            QMessageBox.warning(self, "Creation Failed", str(error))
            return
        self._hide_player_join_form()
        self.accept()  # Continue editing the new character sheet; Save links it.

    def _use_selected_campaign_character(self):
        campaign = getattr(self, "_joined_campaign_candidate", None)
        row = self.join_character_list.currentRow()
        options = getattr(self, "_join_character_options", [])
        if not isinstance(campaign, dict) or not 0 <= row < len(options):
            return
        path, differences = options[row]
        loader = getattr(self.window, "load_character_from_path", None)
        if not callable(loader):
            QMessageBox.warning(self, "Unavailable", "This application cannot open a chosen character.")
            return
        if not loader(path):
            return
        chosen_name = str(getattr(self.window.character, "name", "") or "Player").strip()
        try:
            publication = join_campaign_and_publish(
                self.window, self.service, self.client,
                str(self.join_code_field.text() or campaign.get("invite_code") or ""), chosen_name,
            )
        except JoinedButCharacterNotPublished as error:
            QMessageBox.warning(self, "Character Not Submitted", str(error))
            return
        except Exception as error:
            QMessageBox.warning(self, "Character Submission Failed", str(error))
            return
        self._hide_player_join_form()
        self.reload_campaigns(select_player_id=str(campaign.get("id") or ""))
        if publication.status == "approval_pending":
            _show_campaign_approval_notice(self, publication)
        else:
            _report_join_publication(self, publication)

    def _find_saved_character_file(self, character_id):
        # Find by stable ID, never by display name (names need not be unique).
        import os
        from backend_2_1 import CharacterStorageSystem
        CharacterStorageSystem.ensure_save_dir()
        for directory, subdirs, files in os.walk(CharacterStorageSystem.SAVE_DIR):
            subdirs[:] = [name for name in subdirs if name != "_history"]
            for filename in files:
                if not filename.lower().endswith(".didchar"):
                    continue
                path = os.path.join(directory, filename)
                try:
                    if not CharacterStorageSystem.looks_like_character_file(path):
                        continue
                    candidate = CharacterStorageSystem.import_character_file(path)
                    if str(getattr(candidate, "id", "") or "") == character_id:
                        return path
                except Exception:
                    continue
        return None

    def _open_linked_player_character(self):
        if not self.current_player_campaign:
            return
        target_id, record = self._campaign_character_record()
        if not target_id or not record:
            return
        current_id = str(getattr(getattr(self.window, "character", None), "id", "") or "")
        if current_id != target_id:
            filepath = self._find_saved_character_file(target_id)
            if not filepath:
                QMessageBox.warning(
                    self, "Character Unavailable",
                    "The saved character file was not found. The campaign link is preserved."
                )
                return
            # This existing loader handles unsaved changes and refreshes the UI.
            if not self.window.load_character_from_path(filepath):
                return
        self.accept()
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _show_player_join_form(self):
        self._show_role_page(1)
        self._joined_campaign_candidate = None
        self.join_code_field.clear()
        self.join_code_section.show()
        self.join_choice_section.hide()
        self.join_step_intro.setText("Enter the invitation code from your DM.")
        self.join_confirm_btn.setText("Continue")
        self.join_cancel_btn.setText("Cancel")
        self.join_confirm_btn.setEnabled(True)
        self.player_workspace_stack.setCurrentIndex(1)
        self.join_code_field.setFocus()

    def _hide_player_join_form(self):
        self.player_workspace_stack.setCurrentIndex(0)
        self._joined_campaign_candidate = None
        # The legacy embedded form remains permanently hidden.
        self.player_join_form.setVisible(False)
        self._refresh_player_details()

    def _submit_player_join(self):
        if isinstance(getattr(self, "_joined_campaign_candidate", None), dict):
            return self._use_selected_campaign_character()
        return self._resolve_player_invite()

    def _ensure_player_helper_current(self):
        helper = getattr(self, "player_helper", None)
        if helper is None or not getattr(self, "_player_helper_needs_reload", True):
            return
        # These rows were already classified by the hub's list_campaigns()
        # result. Reusing them avoids N separate role RPCs and another full
        # campaign-list request each time sharing/info is opened.
        helper.campaign_combo.blockSignals(True)
        try:
            helper.campaign_combo.clear()
            helper.campaigns = [dict(item) for item in self.player_campaigns]
            for item in helper.campaigns:
                helper.campaign_combo.addItem(
                    str(item.get("name") or "Unnamed Campaign"), item.get("id")
                )
        finally:
            helper.campaign_combo.blockSignals(False)
        self._player_helper_needs_reload = False

    def _select_player_campaign_character(self):
        """Pick a character without exposing sharing or rejoining the campaign."""
        campaign = self.current_player_campaign
        if not isinstance(campaign, dict) or self._campaign_character_record(campaign)[1]:
            return
        self._show_role_page(1)
        self._joined_campaign_candidate = campaign
        self.join_code_field.setText(str(campaign.get("invite_code") or ""))
        self.join_code_section.hide()
        self.join_choice_section.show()
        self.join_step_intro.setText("Select a saved character or create one with this campaign's rules.")
        self.join_campaign_title.setText(str(campaign.get("name") or "Campaign"))
        self.join_confirm_btn.setText("Use Selected Character")
        self.join_cancel_btn.setText("Cancel")
        self.player_workspace_stack.setCurrentIndex(1)
        self._populate_join_candidates(campaign)

    def _show_player_character_page(self):
        if not self.current_player_campaign:
            return
        if not self._player_has_approved_character():
            self._select_player_campaign_character()
            return
        self._ensure_player_helper_current()
        self._sync_player_helper()
        self.player_detail_stack.setCurrentIndex(0)
        self.player_inline_stack.setCurrentIndex(0)
        self.player_inline_section.setVisible(True)
        self.player_character_section.setVisible(False)
        self.player_effects_section.setVisible(False)
        _did_1013_reveal_embedded_page(self, "_did_1013_character_content")

    def _show_player_overview(self):
        self.player_effects_section.setVisible(self._player_has_approved_character())
        self.player_character_section.setVisible(True)
        self.player_inline_section.setVisible(False)
        self.player_detail_stack.setCurrentIndex(0)
        self._refresh_player_details()

    def _show_player_info_page(self):
        if not self.current_player_campaign or not self._player_has_approved_character():
            return
        self._ensure_player_helper_current()
        self._sync_player_helper()
        index = getattr(self, "player_info_stack_index", None)
        if index is not None:
            self.player_detail_stack.setCurrentIndex(0)
            self.player_inline_stack.setCurrentIndex(index)
            self.player_inline_section.setVisible(True)
            self.player_character_section.setVisible(False)
            self.player_effects_section.setVisible(False)
            _did_1013_reveal_embedded_page(self, "_did_1013_info_content")
            helper = getattr(self, "player_helper", None)
            if helper is not None and hasattr(helper, "_phase8_refresh_campaign_info"):
                helper._phase8_refresh_campaign_info()
                helper._phase8_info_dirty = False

    def _sync_player_helper(self):
        helper = getattr(self, "player_helper", None)
        campaign = self.current_player_campaign
        if helper is None:
            return
        if campaign:
            # _select_campaign_id invokes _campaign_changed, which itself
            # refreshes character/sharing and rules exactly once.
            helper._select_campaign_id(campaign.get("id"))
        else:
            helper._campaign_changed(-1)

    def _refresh_hub_from_button(self):
        """Refresh the selected player's DM decision only on explicit Refresh.

        Hidden player pages never issue approval RPCs as a side effect of DM
        navigation, so Problem 11's lazy-loading behavior remains intact.
        """
        self._refresh_selected_player_admission()
        self.reload_campaigns()

    def _refresh_selected_player_admission(self):
        """Check the DM's response on a worker; never block the Qt event loop."""
        if (self.client is None or not self.current_player_campaign
                or not hasattr(self, "role_pages")
                or self.role_pages.currentIndex() != 1):
            return False
        character = getattr(self.window, "character", None)
        character_id = str(getattr(character, "id", "") or "").strip()
        campaign_id = str(self.current_player_campaign.get("id") or "")
        if not character_id:
            return False
        pending = self.client.get_pending_character_approval(character_id)
        if (not isinstance(pending, dict) or pending.get("approval_status") != "pending"
                or str(pending.get("campaign_id") or "") != campaign_id):
            return False

        self._hub_approval_epoch += 1
        generation = self._hub_approval_epoch
        client = self.client

        def fetch_approval():
            # Both the RPC and the subsequent local link lookup stay off the GUI.
            result = client.refresh_pending_character_approval(character_id)
            link = (client.get_character_link(character_id)
                    if isinstance(result, dict) and result.get("approval_status") == "approved"
                    else None)
            return character_id, campaign_id, result, link

        self._submit_hub_job("approval", generation, fetch_approval)
        return True

    def _finish_player_approval_refresh(self, payload, error):
        if self._hub_closed:
            return
        if error:
            # A failed lookup is not a rejection. Leave local approval intact.
            self._approval_refresh_error = str(error)
            return
        if not payload:
            return
        character_id, campaign_id, result, link = payload
        active_id = str(getattr(getattr(self.window, "character", None), "id", "") or "")
        selected_id = str((self.current_player_campaign or {}).get("id") or "")
        if (character_id != active_id or campaign_id != selected_id
                or self.role_pages.currentIndex() != 1):
            return  # This worker belongs to an old character or campaign.
        self._approval_refresh_error = ""
        if (isinstance(result, dict) and result.get("approval_status") == "approved"
                and isinstance(link, dict)
                and str(link.get("campaign_id") or "") == campaign_id):
            schedule_campaign_state_sync(self.window)
        if isinstance(result, dict) and result.get("approval_status") in {"approved", "rejected"}:
            self._refresh_player_details()

    def closeEvent(self, event):
        """Invalidate in-flight requests without blocking dialog shutdown."""
        self._hub_closed = True
        self._hub_list_epoch += 1
        self._hub_dm_epoch += 1
        self._hub_discord_epoch += 1
        self._hub_player_link_epoch += 1
        self._hub_approval_epoch += 1
        self._hub_decision_epoch += 1
        self._hub_delete_epoch += 1
        self._hub_remove_epoch += 1
        self._hub_replace_epoch += 1
        self._hub_leave_epoch += 1
        self._hub_rules_epoch += 1
        self._hub_poll_timer.stop()
        self._did114_auto_timer.stop()
        super().closeEvent(event)

    # DID114_SHARING_AUTO_REFRESH_V1: silent, read-only campaign refresh.
    def _did114_poll_campaigns(self):
        if (not self.isVisible() or self._hub_closed or self._did114_auto_pending
                or getattr(self, "_inline_rules_editor", None) is not None
                or self.service is None):
            return
        self._did114_auto_pending = True
        self._did114_auto_epoch += 1
        generation = self._did114_auto_epoch
        service = self.service
        client = self.client
        player_id = str((self.current_player_campaign or {}).get("id") or "")
        dm_id = str((self.current_dm_campaign or {}).get("id") or "")
        character_id = str(getattr(getattr(self.window, "character", None), "id", "") or "")
        show_dm = self.role_pages.currentIndex() == 0
        def fetch():
            owner_id = str(client.user_id)
            rows = service.list_campaigns()
            revealed = None
            if player_id:
                link = client.get_character_link(character_id) if character_id else None
                link_id = (str(link.get("campaign_character_id") or "")
                           if isinstance(link, dict) and str(link.get("campaign_id") or "") == player_id
                           else "")
                entries, effects = load_player_reveals(client, player_id, link_id or None)
                revealed = (player_id, link_id, entries, effects)
            roster_key = None
            if dm_id and show_dm:
                roster = client.list_campaign_characters(dm_id)
                approvals = client.list_pending_character_approvals(dm_id)
                roster_key = (dm_id, roster, approvals)
            return owner_id, rows, revealed, roster_key
        self._submit_hub_job("did114_auto", generation, fetch)

    def _did114_apply_campaign_poll(self, payload, error):
        self._did114_auto_pending = False
        if error or not payload or not self.isVisible():
            return  # Network loss must never clear a displayed campaign.
        owner_id, rows, revealed, roster_key = payload
        new_dm = sorted((str(c.get("id") or ""), str(c.get("name") or ""))
                        for c in rows if str(c.get("owner_user_id") or "") == owner_id)
        new_player = sorted((str(c.get("id") or ""), str(c.get("name") or ""))
                            for c in rows if str(c.get("owner_user_id") or "") != owner_id)
        old_dm = sorted((str(c.get("id") or ""), str(c.get("name") or "")) for c in self.dm_campaigns)
        old_player = sorted((str(c.get("id") or ""), str(c.get("name") or "")) for c in self.player_campaigns)
        if (new_dm, new_player) != (old_dm, old_player):
            self.reload_campaigns()  # The existing async loader preserves selection.
            return
        # Apply only changed read-only data, and only to the same campaign.
        if (roster_key and self.role_pages.currentIndex() == 0
                and str((self.current_dm_campaign or {}).get("id") or "") == roster_key[0]):
            if roster_key != getattr(self, "_did114_previous_roster", None):
                self._did114_previous_roster = roster_key
                self._finish_dm_characters((roster_key[0], roster_key[1], roster_key[2], None, None), None)
        if (revealed and self.role_pages.currentIndex() == 1
                and str((self.current_player_campaign or {}).get("id") or "") == revealed[0]):
            self.player_shared_hooks.setText(format_entries(revealed[2]))
            self.player_shared_effects.setText(format_effects(revealed[3], bool(revealed[1])))
            if hasattr(self, "player_effects_section"):
                self.player_effects_section.setVisible(bool(revealed[1]) and not self.player_inline_section.isVisible())

    def _submit_hub_job(self, kind, generation, operation):
        # Qt owns these runnables until completion. The worker only puts plain
        # Python data into the queue; all widget changes occur in the timer.
        QThreadPool.globalInstance().start(
            _CampaignHubNetworkJob(self._hub_results, kind, generation, operation)
        )

    def _drain_hub_results(self):
        if self._hub_closed:
            return
        while True:
            try:
                kind, generation, payload, error = self._hub_results.get_nowait()
            except Empty:
                break
            if kind == "list" and generation == self._hub_list_epoch:
                self._finish_campaign_reload(payload, error)
            elif kind == "dm" and generation == self._hub_dm_epoch:
                self._finish_dm_characters(payload, error)
            elif kind == "discord" and generation == self._hub_discord_epoch:
                self._finish_discord_label(payload, error)
            elif kind == "player_link" and generation == self._hub_player_link_epoch:
                self._finish_player_link_check(payload, error)
            elif kind == "approval" and generation == self._hub_approval_epoch:
                self._finish_player_approval_refresh(payload, error)
            elif kind == "dm_decision" and generation == self._hub_decision_epoch:
                self._finish_dm_character_decision(payload, error)
            elif kind == "dm_delete" and generation == self._hub_delete_epoch:
                self._finish_dm_campaign_delete(payload, error)
            elif kind == "dm_remove" and generation == self._hub_remove_epoch:
                self._finish_dm_character_remove(payload, error)
            elif kind == "player_replace" and generation == self._hub_replace_epoch:
                self._finish_player_replace(payload, error)
            elif kind == "player_leave" and generation == self._hub_leave_epoch:
                self._finish_player_leave(payload, error)
            elif kind == "rules_save" and generation == self._hub_rules_epoch:
                self._finish_inline_rules_save(payload, error)
            elif kind == "did114_auto" and generation == self._did114_auto_epoch:
                self._did114_apply_campaign_poll(payload, error)

    def reload_campaigns(self, *, select_dm_id=None, select_player_id=None):
        """Open immediately; the network campaign list is loaded in a worker.

        When a campaign was just created or joined, select that campaign when
        the asynchronous result arrives (not the stale pre-refresh list).
        """
        self._hub_player_link_token = None
        self._hub_player_link_epoch += 1
        self._hub_target_dm_id = str(select_dm_id or "")
        self._hub_target_player_id = str(select_player_id or "")
        self._hub_list_epoch += 1
        generation = self._hub_list_epoch
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Refresh")
        self.refresh_btn.setToolTip("Checking campaigns…")
        self._resize_campaign_tabs()
        if not self.dm_campaigns and self.dm_list.count() == 0:
            self._show_campaigns_loading(self.dm_list)
        if (not self.player_campaigns and hasattr(self, "player_list")
                and self.player_list.count() == 0):
            self._show_campaigns_loading(self.player_list)
        if self.service is None:
            self._finish_campaign_reload(("", []), None)
            return

        service = self.service
        client = self.client

        def fetch_campaigns():
            # Resolving an expired Supabase session may itself involve a slow
            # auth request, so resolve the user ID on the worker as well.
            owner_id = str(client.user_id)
            return owner_id, service.list_campaigns()

        self._submit_hub_job("list", generation, fetch_campaigns)

    @staticmethod
    def _show_campaigns_loading(widget, message="Loading campaigns…"):
        widget.blockSignals(True)
        try:
            widget.clear()
            item = QListWidgetItem(message)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            widget.addItem(item)
        finally:
            widget.blockSignals(False)

    def _finish_campaign_reload(self, payload, error):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Refresh")
        self._resize_campaign_tabs()
        if error:
            self._campaign_loading_error = str(error)
            # Retain existing rows and selection on offline/timeout failures.
            # Do not interrupt navigation with a modal network dialog.
            self.refresh_btn.setToolTip(f"Could not refresh campaigns: {error}")
            if not self.dm_campaigns:
                self._show_campaigns_loading(
                    self.dm_list, "Could not load campaigns. Press Refresh."
                )
            if not self.player_campaigns and hasattr(self, "player_list"):
                self._show_campaigns_loading(
                    self.player_list, "Could not load campaigns. Press Refresh."
                )
            return
        self._campaign_loading_error = ""
        self.refresh_btn.setToolTip("")
        owner_id, loaded = payload
        dm_id = (getattr(self, "_hub_target_dm_id", "") or
                 str((self.current_dm_campaign or {}).get("id") or ""))
        player_id = (getattr(self, "_hub_target_player_id", "") or
                     str((self.current_player_campaign or {}).get("id") or ""))
        self._hub_target_dm_id = ""
        self._hub_target_player_id = ""
        self.dm_campaigns = []
        self.player_campaigns = []
        for campaign in loaded or []:
            campaign = dict(campaign)
            if owner_id and str(campaign.get("owner_user_id") or "") == str(owner_id):
                campaign["role"] = "dm"
                self.dm_campaigns.append(campaign)
            else:
                campaign["role"] = "player"
                self.player_campaigns.append(campaign)
        self.dm_campaigns.sort(key=lambda c: str(c.get("name") or "").lower())
        self.player_campaigns.sort(key=lambda c: str(c.get("name") or "").lower())

        self.dm_list.blockSignals(True)
        self.dm_list.clear()
        for campaign in self.dm_campaigns:
            item = QListWidgetItem(str(campaign.get("name") or "Unnamed Campaign"))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.UserRole, campaign.get("id"))
            self.dm_list.addItem(item)
        self.dm_list.blockSignals(False)

        if hasattr(self, "player_list"):
            self.player_list.blockSignals(True)
            self.player_list.clear()
            for campaign in self.player_campaigns:
                item = QListWidgetItem(str(campaign.get("name") or "Unnamed Campaign"))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                item.setData(Qt.ItemDataRole.UserRole, campaign.get("id"))
                self.player_list.addItem(item)
            self.player_list.blockSignals(False)

        # The old hidden Player controller triggers its own network requests.
        # It is populated only when Character & Sharing / Info is opened.
        self._player_helper_needs_reload = True
        self.dm_tab_btn.setText(f"DM Campaigns  ({len(self.dm_campaigns)})")
        self.player_tab_btn.setText(f"Player Campaigns  ({len(self.player_campaigns)})")
        self._resize_campaign_tabs()
        self._restore_list_selection(self.dm_list, self.dm_campaigns, dm_id, self._dm_selection_changed)
        if hasattr(self, "player_list"):
            self._restore_list_selection(
                self.player_list, self.player_campaigns, player_id,
                self._player_selection_changed
            )

    def _restore_list_selection(self, widget, campaigns, wanted_id, callback):
        if not campaigns:
            previous = widget.currentRow()
            widget.setCurrentRow(-1)
            if previous == -1:
                callback(-1)
            return
        row = 0
        if wanted_id:
            for i, campaign in enumerate(campaigns):
                if str(campaign.get("id")) == wanted_id:
                    row = i
                    break
        previous = widget.currentRow()
        widget.setCurrentRow(row)
        # Qt emits currentRowChanged when the row really changed. Calling the
        # handler again would repeat potentially slow campaign RPCs.
        if previous == row:
            callback(row)

    def _dm_selection_changed(self, row):
        self.current_dm_campaign = self.dm_campaigns[row] if 0 <= row < len(self.dm_campaigns) else None
        self._refresh_dm_details()

    def _player_selection_changed(self, row):
        self._hub_player_link_token = None
        self._hub_player_link_epoch += 1
        self.current_player_campaign = self.player_campaigns[row] if 0 <= row < len(self.player_campaigns) else None
        self._approval_refresh_error = ""  # A previous campaign's network error is not this campaign's status.
        if hasattr(self, "player_detail_stack"):
            self.player_detail_stack.setCurrentIndex(0)
            self.player_inline_section.setVisible(False)
        # Hidden controller pages should not perform role/link/info network
        # requests simply because a different overview row was clicked.
        self._refresh_player_details()

    def _refresh_dm_details(self):
        campaign = self.current_dm_campaign
        self.dm_content.setVisible(bool(campaign))
        self.dm_empty.setVisible(not bool(campaign))
        self.delete_campaign_btn.setEnabled(bool(campaign))
        self.delete_campaign_btn.setVisible(bool(campaign))
        self.dm_invite_label.setVisible(bool(campaign))
        self.dm_invite_code.setVisible(bool(campaign))
        self._update_header_actions()
        if not campaign:
            self._hub_dm_epoch = getattr(self, "_hub_dm_epoch", 0) + 1
            self._hub_discord_epoch = getattr(self, "_hub_discord_epoch", 0) + 1
            self.dm_name_label.setText("No DM campaigns yet")
            self.dm_empty.setText("Create a campaign to get started.")
            self._clear_layout(self.dm_character_layout)
            self._dm_details_dirty = False
            self._refresh_dm_rules()
            return
        self.dm_name_label.setText(str(campaign.get("name") or "Unnamed Campaign"))
        code = str(campaign.get("invite_code") or "").strip()
        self.dm_invite_code.setText(code or "No invite code")
        self.dm_invite_code.setEnabled(bool(code))
        self._refresh_dm_rules()
        if hasattr(self, "role_pages") and self.role_pages.currentIndex() != 0:
            self._hub_dm_epoch = getattr(self, "_hub_dm_epoch", 0) + 1
            self._hub_discord_epoch = getattr(self, "_hub_discord_epoch", 0) + 1
            self._dm_details_dirty = True
            return
        self._dm_details_dirty = False
        self._refresh_dm_characters()
        self._refresh_discord_action_label()

    def _refresh_discord_action_label(self):
        """Check Discord without delaying the campaign details or tab switching."""
        self._hub_discord_epoch += 1
        generation = self._hub_discord_epoch
        button = getattr(self, "discord_settings_btn", None)
        campaign = self.current_dm_campaign
        if button is None:
            return
        if not campaign or self.client is None:
            self._finish_discord_label(None, None)
            return
        campaign_id = str(campaign.get("id") or "")
        button.setText("Checking Discord…")
        button.setToolTip("Checking Discord connection")
        _fit_button(button)
        client = self.client
        self._submit_hub_job(
            "discord", generation,
            lambda: (campaign_id, client.get_discord_connection(campaign_id)),
        )

    def _finish_discord_label(self, payload, error):
        button = getattr(self, "discord_settings_btn", None)
        if button is None:
            return
        campaign_id = str((self.current_dm_campaign or {}).get("id") or "")
        if payload is not None and str(payload[0]) != campaign_id:
            return
        connection = payload[1] if payload else None
        if connection:
            channel_name = str(connection.get("channel_name") or "").strip()
            guild_name = str(connection.get("guild_name") or "Discord server").strip()
            label = f"Discord: #{channel_name} ✓" if channel_name else "Discord Connected ✓"
            button.setText(label)
            button.setToolTip(
                f"{guild_name} · #{channel_name}" if channel_name else guild_name
            )
        else:
            button.setText("Connect Discord")
            button.setToolTip(
                "Could not check Discord connection; retry with Refresh"
                if error else "Connect this campaign to a Discord channel"
            )
        full_text = button.text()
        width = 235
        metrics = button.fontMetrics()
        if metrics.horizontalAdvance(full_text) > width:
            button.setText(metrics.elidedText(
                full_text, Qt.TextElideMode.ElideMiddle, width
            ))
        _fit_button(button)

    def _campaign_character_record(self, campaign=None):
        """Find this campaign's character independently of the open sheet.

        Approved links outrank outstanding/rejected approval requests. Pending
        and rejected records are returned only for replacement controls, never
        as authorization to open private campaign views.
        """
        campaign = campaign or self.current_player_campaign
        if campaign is None or self.client is None:
            return None, None
        campaign_id = str(campaign.get("id") or "")
        links = getattr(self.client, "links", None)
        records = links.all_links() if links and hasattr(links, "all_links") else {}
        rejected_or_pending = (None, None)
        for character_id, raw in records.items():
            if not isinstance(raw, dict) or str(raw.get("campaign_id") or "") != campaign_id:
                continue
            status = str(raw.get("approval_status") or "").lower()
            if status not in {"pending", "rejected"} and raw.get("campaign_character_id"):
                return str(character_id), dict(raw)
            if status in {"pending", "rejected"} and rejected_or_pending[1] is None:
                rejected_or_pending = (str(character_id), dict(raw))
        return rejected_or_pending

    def _player_has_approved_character(self):
        _, record = self._campaign_character_record()
        return (isinstance(record, dict)
                and bool(record.get("campaign_character_id"))
                and record.get("approval_status") not in {"pending", "rejected"})

    def _confirm_player_replacement(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Remove Campaign Character")
        dialog.setModal(True)
        set_themed_stylesheet(dialog, ROLE_QSS)
        dialog.setMinimumWidth(410)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)
        title = QLabel("Replace this campaign character?")
        title.setStyleSheet("font-size:17px;font-weight:900;")
        layout.addWidget(title)
        description = QLabel(
            "The character will remain saved on your computer. "
            "Only its connection to this campaign will be removed. "
            "You can then choose or create another character."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        buttons = QHBoxLayout()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("CompactButton")
        cancel.clicked.connect(dialog.reject)
        remove = QPushButton("Remove from Campaign")
        remove.setObjectName("HubPrimary")
        remove.clicked.connect(dialog.accept)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        buttons.addWidget(remove)
        layout.addLayout(buttons)
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _leave_player_campaign(self):
        """Leave an empty player campaign without deleting it for the DM."""
        campaign = self.current_player_campaign
        if (not campaign or self.client is None or self._hub_leave_in_flight
                or self._campaign_character_record(campaign)[1] is not None):
            return
        name = str(campaign.get("name") or "this campaign")
        answer = QMessageBox.question(
            self, "Leave Campaign",
            f"Leave {name}? It will disappear from your Player Campaigns list, "
            "but the DM's campaign and other players will not be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        campaign_id = str(campaign.get("id") or "")
        client = self.client
        self._hub_leave_in_flight = True
        self.player_leave_campaign_btn.setEnabled(False)
        self._hub_leave_epoch += 1
        generation = self._hub_leave_epoch

        def leave_remote():
            # Check the server as well as the local UI. Another computer may
            # have added a character or submitted an approval request.
            characters = client._request_json(
                "GET", "/rest/v1/campaign_characters",
                query={"campaign_id": f"eq.{campaign_id}",
                       "owner_user_id": f"eq.{client.user_id}",
                       "active": "eq.true", "select": "id", "limit": "1"},
            )
            if not isinstance(characters, list):
                raise RuntimeError("Could not verify campaign characters.")
            if characters:
                raise RuntimeError("Remove your campaign character before leaving.")
            pending = client._request_json(
                "GET", "/rest/v1/campaign_character_approval_requests",
                query={"campaign_id": f"eq.{campaign_id}",
                       "owner_user_id": f"eq.{client.user_id}",
                       "status": "eq.pending", "select": "id", "limit": "1"},
            )
            if not isinstance(pending, list):
                raise RuntimeError("Could not verify pending character requests.")
            if pending:
                raise RuntimeError("Withdraw your pending character request before leaving.")
            deleted = client._request_json(
                "DELETE", "/rest/v1/campaign_members",
                query={"campaign_id": f"eq.{campaign_id}",
                       "user_id": f"eq.{client.user_id}",
                       "role": "neq.dm", "select": "campaign_id"},
                prefer="return=representation",
            )
            if not isinstance(deleted, list) or not deleted:
                raise RuntimeError("The server did not confirm leaving this campaign.")
            return campaign_id

        self._submit_hub_job("player_leave", generation, leave_remote)

    def _finish_player_leave(self, campaign_id, error):
        self._hub_leave_in_flight = False
        if error:
            self.player_leave_campaign_btn.setEnabled(True)
            QMessageBox.warning(self, "Leave Campaign Failed", str(error))
            return
        if not campaign_id:
            return
        links = getattr(self.client, "links", None)
        if links is not None:
            for character_id, link in list(links.all_links().items()):
                if isinstance(link, dict) and str(link.get("campaign_id") or "") == str(campaign_id):
                    self.client.unlink_local_character(character_id)
        if str((self.current_player_campaign or {}).get("id") or "") == str(campaign_id):
            self.current_player_campaign = None
        restore_campaign_connection(self.window)
        self.reload_campaigns()

    def _replace_player_character(self):
        campaign = self.current_player_campaign
        character_id, record = self._campaign_character_record()
        if campaign is None or not character_id or record is None or self.client is None:
            return
        if not self._confirm_player_replacement():
            return
        self.player_replace_character_btn.setEnabled(False)
        self._hub_replace_epoch += 1
        generation = self._hub_replace_epoch
        campaign_id = str(campaign.get("id") or "")
        client = self.client
        request_id = str(record.get("request_id") or "")
        def withdraw():
            if record.get("approval_status") in ("pending", "rejected"):
                if not request_id:
                    raise RuntimeError("The approval request is missing its ID; refresh and try again.")
                if not client.cancel_character_approval(request_id):
                    raise RuntimeError("Could not cancel the character approval request.")
            else:
                result = client._request_json(
                    "POST", "/rest/v1/rpc/did_withdraw_campaign_character",
                    body={"p_campaign_id": campaign_id, "p_character_id": character_id},
                )
                if result is not True:
                    raise RuntimeError("The campaign server did not confirm removal.")
            return (campaign_id, character_id)
        self._submit_hub_job("player_replace", generation, withdraw)

    def _finish_player_replace(self, payload, error):
        self.player_replace_character_btn.setEnabled(True)
        if error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
            return
        campaign_id, character_id = payload
        # Only clear local state after the server has confirmed the withdrawal.
        self.client.unlink_local_character(character_id)
        current_id = str(getattr(getattr(self.window, "character", None), "id", "") or "")
        if current_id == character_id:
            restore_campaign_connection(self.window)
        if str((self.current_player_campaign or {}).get("id") or "") == campaign_id:
            self.player_inline_section.setVisible(False)
            self._refresh_player_details()

    def _refresh_player_details(self):
        campaign = self.current_player_campaign
        self.player_content.setVisible(bool(campaign))
        if not campaign:
            self.player_name_label.setText("No player campaigns yet")
            self.player_explainer.setText("Join a campaign with an invite code.")
            self.player_character_name.setText("-")
            self.player_character_status.setText("")
            self.player_add_character_btn.setVisible(False)
            self.player_replace_character_btn.setVisible(False)
            self.player_leave_campaign_btn.setVisible(False)
            self.player_party_dashboard_btn.setVisible(False)
            self.player_campaign_info_btn.setVisible(False)
            for label in self.player_rule_summary_labels.values():
                label.setText("-")
            self.player_join_form.setVisible(False)
            self.join_player_campaign_btn.setVisible(True)
            self.player_name_label.setVisible(True)
            self.player_explainer.setVisible(True)
            return

        self.join_player_campaign_btn.setVisible(True)
        # A selected player campaign uses the overview by default.  The join
        # form remains opt-in via + Join Campaign.
        if not self.player_join_code.hasFocus():
            self.player_join_form.setVisible(False)

        self.player_name_label.setText(str(campaign.get("name") or "Unnamed Campaign"))
        self.player_explainer.setText(
            "Select a character for this campaign. Party details and sharing "
            "become available once the DM approves your character."
        )

        character = getattr(self.window, "character", None)
        open_id = str(getattr(character, "id", "") or "")
        character_id, record = self._campaign_character_record(campaign)
        is_approved = self._player_has_approved_character()
        self._player_linked_character_id = character_id if is_approved else None
        self.player_party_dashboard_btn.setVisible(is_approved)
        self.player_campaign_info_btn.setVisible(is_approved)
        self.player_character_sharing_btn.setVisible(is_approved)
        if not self.player_inline_section.isVisible():
            self.player_character_section.setVisible(True)
        if not is_approved and self.player_inline_stack.currentIndex() != 0:
            self.player_inline_section.setVisible(False)
        self.player_replace_character_btn.setVisible(record is not None)
        self.player_add_character_btn.setVisible(record is None)
        self.player_leave_campaign_btn.setVisible(record is None)
        self.player_leave_campaign_btn.setEnabled(not self._hub_leave_in_flight)
        self.player_character_name.setCursor(
            Qt.CursorShape.PointingHandCursor if record else Qt.CursorShape.ArrowCursor
        )
        self.player_character_name.setToolTip("Click to open the saved character" if record else "")
        if record and is_approved:
            name = str(record.get("character_name") or "").strip()
            if character_id == open_id:
                name = str(getattr(character, "name", "") or "").strip() or name
                self.player_character_name.setCursor(Qt.CursorShape.PointingHandCursor)
                self.player_character_name.setToolTip("Click to open this character sheet")
            self.player_character_name.setText(name or "Campaign character")
            self.player_character_status.setText("Character linked and approved by DM")
        elif record:
            self.player_character_name.setText(str(record.get("character_name") or "Campaign character"))
            if record.get("approval_status") == "rejected":
                self.player_character_status.setText(
                    "Rejected by DM. Remove this request to select or create another character.")
            else:
                self.player_character_status.setText(
                    "Awaiting DM approval. Party Dashboard and Campaign Info are unavailable.")
        else:
            self.player_character_name.setText("No approved character in this campaign")
            self.player_character_status.setText(
                "Select or create a character. Party Dashboard and Campaign Info "
                "become available after DM approval.")
        if hasattr(self, "player_effects_section"):
            self.player_effects_section.setVisible(is_approved and not self.player_inline_section.isVisible())

        summaries = {
            "Starting Character": "-",
            "Resources": "-",
            "Character Options": "-",
        }
        for section_name, rows in _campaign_rules_rows(campaign):
            summaries[section_name] = "  •  ".join(
                f"{field_name}: {value}" for field_name, value in rows
            )
        for section_name, label in self.player_rule_summary_labels.items():
            label.setText(summaries.get(section_name, "-"))

        self._schedule_player_link_check(campaign, character, record if is_approved and character_id == open_id else None)
        if is_approved:
            self._refresh_player_reveals()

    def _refresh_player_reveals(self):
        if not hasattr(self, "player_shared_hooks"):
            return
        campaign = self.current_player_campaign
        if not campaign or self.client is None:
            self.player_shared_hooks.setText("Select a campaign to see shared content.")
            self.player_shared_effects.setText("Select a campaign to see your effects.")
            return
        helper = getattr(self, "player_helper", None)
        link = helper._current_link() if helper else None
        character_id = (link or {}).get("campaign_character_id")
        try:
            entries, effects = load_player_reveals(
                self.client, campaign.get("id"), character_id
            )
        except Exception as error:
            self.player_shared_hooks.setText(f"Could not load shared content: {error}")
            self.player_shared_effects.setText("Press Refresh to retry.")
            return
        self.player_shared_hooks.setText(format_entries(entries))
        self.player_shared_effects.setText(format_effects(effects, bool(character_id)))

    # DID_PLAYER_LINK_CHECK_V1 — asynchronous server-verified link reconciliation.
    def _schedule_player_link_check(self, campaign, character, link):
        if not isinstance(link, dict) or self.client is None:
            return
        campaign_id = str(campaign.get('id') or '')
        character_id = str(getattr(character, 'id', '') or '')
        link_id = str(link.get('campaign_character_id') or '')
        if not campaign_id or not character_id or not link_id:
            return
        token = (campaign_id, character_id, link_id)
        if token == self._hub_player_link_token:
            return
        self._hub_player_link_token = token
        self._hub_player_link_epoch += 1
        generation = self._hub_player_link_epoch
        from campaign_link_guard import verify_character_link
        client = self.client
        self._submit_hub_job('player_link', generation,
                             lambda: (token, verify_character_link(client, character_id, campaign_id)))

    def _finish_player_link_check(self, payload, error):
        if error or payload is None:
            return  # Wi-Fi offline or unknown status: retain local link.
        token, check = payload
        if token != self._hub_player_link_token:
            return
        current_campaign_id = str((self.current_player_campaign or {}).get('id') or '')
        current_character_id = str(getattr(getattr(self.window, 'character', None), 'id', '') or '')
        if (current_campaign_id, current_character_id) != token[:2]:
            return
        if check.status == 'removed':
            from campaign_link_guard import clear_confirmed_removed_link
            if clear_confirmed_removed_link(self.client, current_character_id, check):
                character = getattr(self.window, 'character', None)
                progression = getattr(character, 'progression', None)
                details = [str(getattr(character, 'species', '') or '').strip(),
                           f'Level {int(getattr(progression, "level", 1) or 1)}',
                           'Removed from campaign by DM (local character preserved)']
                self.player_character_status.setText('  •  '.join(x for x in details if x))
                helper = getattr(self, 'player_helper', None)
                if helper is not None:
                    helper._refresh_character_page()
                self.player_character_name.setText("No character added to this campaign")
                self.player_character_status.setText("Removed by the DM. Your local character remains saved.")
                self.player_add_character_btn.setVisible(True)
                if hasattr(self, "player_effects_section"):
                    self.player_effects_section.setVisible(False)
        elif check.status == 'offline':
            self.player_character_status.setToolTip(check.message)
        elif check.status == 'active':
            self.player_character_status.setToolTip('Character is active in this campaign.')

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
            elif child is not None:
                self._clear_layout(child)

    def _refresh_dm_characters(self):
        """Render a placeholder now; fetch roster and approvals off-thread."""
        self._hub_dm_epoch += 1
        generation = self._hub_dm_epoch
        self._clear_layout(self.dm_character_layout)
        campaign = self.current_dm_campaign
        if not campaign or self.client is None:
            return
        campaign_id = str(campaign.get("id") or "")
        loading = QLabel("Loading characters and approval requests…")
        loading.setObjectName("Muted")
        self.dm_character_layout.addWidget(loading)
        client = self.client

        def fetch_details():
            # Fetch roster and approval requests concurrently. Both are
            # independent read-only requests, so total wait is the slower RPC
            # rather than the sum of two HTTP round-trips.
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="did-dm-read") as pool:
                roster_future = pool.submit(client.list_campaign_characters, campaign_id)
                approvals_future = pool.submit(client.list_pending_character_approvals, campaign_id)
                try:
                    rows = roster_future.result()
                    characters_error = None
                except Exception as exc:
                    rows = []
                    characters_error = str(exc)
                try:
                    approvals = approvals_future.result()
                    approvals_error = None
                except Exception as exc:
                    approvals = []
                    approvals_error = str(exc)
            return campaign_id, rows, approvals, characters_error, approvals_error

        self._submit_hub_job("dm", generation, fetch_details)

    def _finish_dm_characters(self, payload, error):
        if not self.current_dm_campaign:
            return
        if payload is not None and str(payload[0]) != str(self.current_dm_campaign.get("id") or ""):
            return
        self._clear_layout(self.dm_character_layout)
        if error or payload is None:
            label = QLabel(f"Could not load characters: {error or 'Unknown error'}")
            label.setObjectName("Muted")
            self.dm_character_layout.addWidget(label)
            return
        _, rows, approvals, characters_error, approvals_error = payload
        if characters_error:
            label = QLabel(f"Could not load characters: {characters_error}")
            label.setObjectName("Muted")
            self.dm_character_layout.addWidget(label)
        if approvals_error:
            lowered = approvals_error.lower()
            if ('campaign_character_approval_requests' in lowered
                    or 'schema cache' in lowered or '(404)' in lowered):
                message = ('Character approval requests are unavailable until '
                           'the campaign approval table is installed.')
            else:
                message = f'Could not load approval requests: {approvals_error}'
            warning = QLabel(message)
            warning.setObjectName("Muted")
            warning.setWordWrap(True)
            self.dm_character_layout.addWidget(warning)
        if approvals:
            heading = QLabel(f"Character approval requests ({len(approvals)})")
            heading.setObjectName("SectionText")
            self.dm_character_layout.addWidget(heading)
        for request in approvals:
            request_id = str(request.get("id") or "")
            frame = QFrame()
            frame.setObjectName("MiniStat")
            card_layout = QVBoxLayout(frame)
            card_layout.setContentsMargins(10, 8, 10, 8)
            name = QLabel(str(request.get("display_name") or "Character") + " — awaiting DM decision")
            name.setWordWrap(True)
            card_layout.addWidget(name)
            differences = request.get("mismatch_details") or []
            details = QLabel("\n".join("• " + str(x) for x in differences))
            details.setObjectName("Muted")
            details.setWordWrap(True)
            card_layout.addWidget(details)
            actions = QHBoxLayout()
            reject = QPushButton("Reject")
            reject.setObjectName("CompactButton")
            approve = QPushButton("Approve Character")
            approve.setObjectName("HubPrimary")
            # Capture the request snapshot: the DM must see exactly which
            # character and differences the decision applies to.
            request_name = str(request.get("display_name") or "Character")
            request_campaign_id = str(request.get("campaign_id") or "")
            differences = tuple(str(item) for item in differences)
            reject.clicked.connect(
                lambda _checked=False, rid=request_id, n=request_name, ds=differences, cid=request_campaign_id:
                self._decide_dm_character_request(rid, False, n, ds, cid)
            )
            approve.clicked.connect(
                lambda _checked=False, rid=request_id, n=request_name, ds=differences, cid=request_campaign_id:
                self._decide_dm_character_request(rid, True, n, ds, cid)
            )
            actions.addWidget(reject)
            actions.addStretch()
            actions.addWidget(approve)
            card_layout.addLayout(actions)
            self.dm_character_layout.addWidget(frame)
        if not rows and not characters_error:
            label = QLabel("No approved characters are in this campaign yet.")
            label.setObjectName("Muted")
            self.dm_character_layout.addWidget(label)
            return
        for row in rows:
            state = _state_from_character_row(row)
            display_name = str(state.get("name") or row.get("display_name") or "Unnamed Character")
            line = QFrame()
            line.setObjectName("MiniStat")
            # QFrame defaults to a vertically expanding size policy.  Inside
            # the scroll-area layout that made a one-line character entry grow
            # to the full viewport height, leaving a long gold border down the
            # left side and a malformed-looking top-right corner.
            line.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            line.setFixedHeight(38)
            layout = QHBoxLayout(line)
            layout.setContentsMargins(10, 6, 7, 6)
            layout.setSpacing(6)
            name = QLabel(display_name)
            name.setStyleSheet("font-weight:900;")
            name.setMinimumWidth(120)
            name.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            name.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            name.setWordWrap(False)
            layout.addWidget(name, 1)
            # Keep campaign resources in real columns rather than one proportional-text
            # string.  This makes the current/maximum values and separators line up
            # cleanly even when the digit widths differ.
            for index, (stat_name, stat_value) in enumerate((
                ("HP", _hp_text(state)),
                ("AT", _at_text(state)),
                ("IP", _ip_text(state)),
            )):
                if index:
                    separator = QLabel("•")
                    separator.setObjectName("Muted")
                    separator.setFixedWidth(10)
                    separator.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.addWidget(separator)

                stat_box = QWidget()
                stat_layout = QHBoxLayout(stat_box)
                stat_layout.setContentsMargins(0, 0, 0, 0)
                stat_layout.setSpacing(3)

                stat_label = QLabel(stat_name)
                stat_label.setObjectName("Muted")
                stat_label.setFixedWidth(18)
                stat_label.setAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )

                value_label = QLabel(stat_value)
                value_label.setObjectName("Muted")
                value_label.setFixedWidth(44)
                value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

                stat_layout.addWidget(stat_label)
                stat_layout.addWidget(value_label)
                layout.addWidget(stat_box)
            remove = QPushButton("×")
            remove.setObjectName("RemoveXButton")
            remove.setFixedSize(20, 20)
            remove.setToolTip("Remove from campaign")
            remove.clicked.connect(lambda _checked=False, character_id=row.get("id"), display=display_name: self.remove_dm_character(character_id, display))
            layout.addWidget(remove)
            self.dm_character_layout.addWidget(line)

    def _decide_dm_character_request(self, request_id, approve, display_name="", mismatches=(), campaign_id=""):
        if not request_id or self.client is None:
            return
        # Do not apply a stale card's decision to another selected campaign.
        current_id = str((self.current_dm_campaign or {}).get("id") or "")
        if campaign_id and str(campaign_id) != current_id:
            QMessageBox.warning(self, "Character Admission", "Campaign changed. Refresh and review the request again.")
            return
        if not _confirm_character_admission(self, display_name, mismatches, approve):
            return
        self._hub_decision_epoch += 1
        generation = self._hub_decision_epoch
        client = self.client
        # The actual RPC runs in the existing background job pool.
        self._submit_hub_job(
            "dm_decision", generation,
            lambda: (current_id, client.decide_character_approval(request_id, approve)),
        )

    def _finish_dm_character_decision(self, payload, error):
        if self._hub_closed:
            return
        if error:
            QMessageBox.warning(self, "Character Admission Failed", str(error))
        # Reconcile only the currently selected campaign; a stale request
        # must not refresh an unrelated DM roster.
        if error or (payload and str((self.current_dm_campaign or {}).get("id") or "") == str(payload[0])):
            self._refresh_dm_characters()

    def _refresh_dm_rules(self):
        campaign = self.current_dm_campaign
        summaries = {
            "Starting Character": "-",
            "Resources": "-",
            "Character Options": "-",
        }
        if campaign:
            for section_name, rows in _campaign_rules_rows(campaign):
                summaries[section_name] = "  •  ".join(
                    f"{field_name}: {value}" for field_name, value in rows
                )
        for section_name, label in self.dm_rule_summary_labels.items():
            label.setText(summaries.get(section_name, "-"))

    @staticmethod
    def _polish_inline_rules_starting_page(editor):
        """Use the rules editor width without producing giant input fields.

        Keep all controls and signal connections from CharacterTemplateDialog.
        The two balanced panels are horizontal on wide displays and stack
        naturally on narrower displays.  Back/Next remain outside the scroll.
        """
        page = editor.pages.widget(1)
        if page is None:
            return
        page_layout = page.layout()
        if page_layout is None:
            return

        expected = (
            editor.level_input,
            editor.extra_ip_input,
            editor.free_heightened_input,
            editor.species_input,
            editor.hearts_input,
            editor.at_input,
        )
        if page_layout.count() < 10:
            return
        labels = {}
        for i in range(2, page_layout.count()):
            item = page_layout.itemAt(i)
            row = item.layout() if item is not None else None
            if row is None or row.count() < 2:
                continue
            label_item, value_item = row.itemAt(0), row.itemAt(1)
            label = label_item.widget() if label_item is not None else None
            value = value_item.widget() if value_item is not None else None
            if isinstance(label, QLabel) and value is not None:
                labels[value] = label
        if any(widget not in labels for widget in expected):
            return  # If upstream editor layout changes, don't modify it.

        # Detach only the original field layouts, retaining the actual input
        # widgets/labels and all existing signal and validation bindings.
        while page_layout.count() > 2:
            item = page_layout.takeAt(2)
            row = item.layout()
            if row is None:
                continue
            while row.count():
                child = row.takeAt(0)
                widget = child.widget()
                if widget is not None and widget.objectName() == "InlineSpeciesArrow":
                    widget.hide()
                    widget.deleteLater()
            row.deleteLater()

        page_layout.setContentsMargins(12, 8, 12, 8)
        page_layout.setSpacing(14)
        panels = _InlineRulesResponsivePanels(page)
        panels.setObjectName("InlineRulesResponsivePanels")
        panels.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Maximum)
        column_layout = QHBoxLayout(panels)
        column_layout.setContentsMargins(0, 2, 0, 0)
        column_layout.setSpacing(16)

        def make_panel(title, description):
            card = QFrame(panels)
            card.setObjectName("InlineRulesPanel")
            card.setSizePolicy(QSizePolicy.Policy.Expanding,
                               QSizePolicy.Policy.Preferred)
            set_themed_stylesheet(card, """
                QFrame#InlineRulesPanel {
                    background-color: #fffdf7;
                    border: 1px solid #d9bd82;
                    border-radius: 11px;
                }
            """)
            body = QVBoxLayout(card)
            body.setContentsMargins(18, 14, 18, 18)
            body.setSpacing(10)
            heading = QLabel(title, card)
            heading.setObjectName("SectionTitle")
            body.addWidget(heading)
            subtitle = QLabel(description, card)
            subtitle.setObjectName("SectionText")
            subtitle.setWordWrap(True)
            body.addWidget(subtitle)
            grid = QGridLayout()
            grid.setContentsMargins(0, 8, 0, 0)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(12)
            grid.setColumnMinimumWidth(0, 180)
            grid.setColumnStretch(0, 0)
            grid.setColumnStretch(1, 1)
            body.addLayout(grid)
            body.addStretch(1)
            column_layout.addWidget(card, 1)
            return grid

        basics = make_panel("Starting Values",
                            "Choose the character's starting progression and species.")
        resources = make_panel("Resources",
                               "Keep the normal defaults, or override HP and AT.")

        for field in expected:
            if field is editor.species_input:
                continue
            field.setMinimumWidth(110)
            field.setMaximumWidth(460)
            field.setFixedHeight(36)
            field.setSizePolicy(QSizePolicy.Policy.Expanding,
                                QSizePolicy.Policy.Fixed)

        # Match the native Improvement-mode selector in CharacterTemplateDialog.
        # No custom arrow widget or frame: Qt styles the drop-down as one
        # continuous control with a full-width click target and right cap.
        combo = editor.species_input
        combo.setObjectName("InlineSpeciesCombo")
        combo.setMinimumWidth(110)
        combo.setMaximumWidth(16777215)
        combo.setMinimumHeight(42)
        combo.setMaximumHeight(42)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding,
                            QSizePolicy.Policy.Fixed)
        set_themed_stylesheet(combo, """
            QComboBox#InlineSpeciesCombo {
                background-color: #fffaf0; border: 1px solid #d9bd82;
                border-radius: 9px; padding: 6px 8px;
                color: #25190f; font-family: Georgia; font-size: 13px;
                min-height: 0px;
            }
            QComboBox#InlineSpeciesCombo::drop-down {
                width: 26px; border: none;
                border-left: 1px solid #d9bd82;
                background-color: #d8edf7;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }
            QComboBox#InlineSpeciesCombo::down-arrow {
                image: none; width: 0px; height: 0px;
            }
            QComboBox#InlineSpeciesCombo QAbstractItemView {
                background-color: #fffdf7; border: 1px solid #cdaa63;
                color: #25190f; selection-background-color: #d8edf7;
                selection-color: #25190f; outline: none;
            }
        """)

        def put_row(grid, row, field, widget=None):
            label = labels[field]
            label.setMinimumWidth(160)
            label.setMaximumWidth(205)
            label.setSizePolicy(QSizePolicy.Policy.Preferred,
                                QSizePolicy.Policy.Preferred)
            grid.addWidget(label, row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(widget if widget is not None else field, row, 1)

        put_row(basics, 0, editor.level_input)
        put_row(basics, 1, editor.extra_ip_input)
        put_row(basics, 2, editor.free_heightened_input)
        put_row(basics, 3, combo)
        resources.addWidget(editor.custom_hearts_checkbox, 0, 0, 1, 2)
        put_row(resources, 1, editor.hearts_input)
        resources.addWidget(editor.custom_at_checkbox, 2, 0, 1, 2)
        put_row(resources, 3, editor.at_input)

        for checkbox in (editor.custom_hearts_checkbox,
                         editor.custom_at_checkbox):
            checkbox.setMinimumHeight(30)
            checkbox.setSizePolicy(QSizePolicy.Policy.Preferred,
                                    QSizePolicy.Policy.Fixed)
            set_themed_stylesheet(checkbox, """
                QCheckBox { background: transparent; border: none;
                    color: #25190f; font-family: Georgia;
                    font-size: 12px; font-weight: 700; spacing: 9px; }
                QCheckBox::indicator { width: 17px; height: 17px;
                    border: 1px solid #c79a3b; border-radius: 4px;
                    background: #fffdf7; }
                QCheckBox::indicator:checked { background: #d8edf7;
                    border: 2px solid #a87824; }
            """)

        page_layout.addWidget(panels)
        page_layout.addStretch(1)

        # Keep the footer separate from this independently scrollable page.
        index = editor.pages.indexOf(page)
        if index < 0:
            return
        editor.pages.removeWidget(page)
        scroll = QScrollArea(editor.pages)
        scroll.setObjectName("InlineRulesStartingScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumSize(0, 0)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding,
                             QSizePolicy.Policy.Expanding)
        set_themed_stylesheet(scroll, """
            QScrollArea#InlineRulesStartingScroll { background: transparent;
                                                   border: none; }
            QScrollArea#InlineRulesStartingScroll > QWidget > QWidget {
                background: transparent;
            }
        """)
        scroll.setWidget(page)
        editor.pages.insertWidget(index, scroll)

    def _open_inline_rules_editor(self, template, *, mode, campaign_name=None):
        if getattr(self, "_inline_rules_editor", None) is not None:
            return
        editor = CampaignRulesEditorDialog(self, template=template)
        editor.setWindowFlags(Qt.WindowType.Widget)
        editor.setMinimumSize(0, 0)
        editor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        if hasattr(editor, "save_button"):
            editor.save_button.setText("Save Rules")
        if hasattr(editor, "load_button"):
            editor.load_button.setText("Load Rules")
        if hasattr(editor, "close_button"):
            editor.close_button.setText("Back to Campaign")

        # Keep the embedded rules editor footer extremely simple on every
        # page: Back is always the left-most action, while Next/Save remains
        # on the far right.  Load Rules and Back to Campaign are exposed in
        # the Campaigns header beside Refresh instead of consuming footer room.
        try:
            outer_layout = editor.layout()
            button_layout = outer_layout.itemAt(outer_layout.count() - 1).layout()
            if button_layout is not None:
                # Rebuild the footer from scratch.  The original template
                # footer contains a spacer before Back; merely removing the
                # buttons leaves that spacer in place and pushes Back toward
                # the middle of the window.
                while button_layout.count():
                    button_layout.takeAt(0)

                editor.load_button.setVisible(False)
                editor.close_button.setVisible(False)
                button_layout.setContentsMargins(0, 0, 0, 0)
                button_layout.setSpacing(8)
                button_layout.addWidget(editor.back_button, 0, Qt.AlignmentFlag.AlignLeft)
                button_layout.addStretch(1)
                button_layout.addWidget(editor.next_button, 0, Qt.AlignmentFlag.AlignRight)
                button_layout.addWidget(editor.save_button, 0, Qt.AlignmentFlag.AlignRight)
        except Exception:
            pass

        # The first page was too tall once embedded below the Campaigns header.
        # Tighten only the two rich-text fields so Description and Instructions
        # for Players are both fully visible without overlapping the footer.
        try:
            editor.description_input.setFixedHeight(58)
            editor.instructions_input.setFixedHeight(64)
            first_page_layout = editor.pages.widget(0).layout()
            if first_page_layout is not None:
                first_page_layout.setSpacing(7)
        except Exception:
            pass

        # The Campaigns window already provides the context and global actions.
        # Remove the template editor's repeated title/subtitle/progress chrome
        # from every embedded rules page and let the actual page content use
        # that vertical space.  The bottom Back / Next / Save row stays fixed.
        try:
            editor.step_label.setVisible(False)
            editor.step_label.setMaximumHeight(0)
            for label in editor.findChildren(QLabel):
                text = label.text().strip()
                if text == "Character Creation Template" or (
                    "save the template" in text.lower()
                ):
                    label.setVisible(False)
                    label.setMaximumHeight(0)
            outer_layout = editor.layout()
            if outer_layout is not None:
                outer_layout.setContentsMargins(16, 4, 16, 10)
                outer_layout.setSpacing(4)
        except Exception:
            pass

        for label in editor.findChildren(QLabel):
            if label.text() == "Character Creation Template":
                label.setText("Campaign Creation Rules")
            elif "save the template" in label.text().lower():
                label.setText("Set the character-creation rules for this campaign.")
            elif mode == "new" and label.text() == "Template":
                label.setText("Campaign")
            elif mode == "new" and label.text() == "Template Name":
                label.setText("Campaign Name")
            elif mode == "new" and label.text().startswith("Name this character-creation setup"):
                label.setText("Name the campaign and set the rules players will use when creating characters.")
        if mode == "new" and hasattr(editor, "name_input"):
            editor.name_input.setPlaceholderText("Campaign name")
            editor.name_input.setMaxLength(CAMPAIGN_NAME_MAX_LENGTH)
            editor.name_input.setToolTip(
                f"Campaign names can contain up to {CAMPAIGN_NAME_MAX_LENGTH} characters."
            )

        self._polish_inline_rules_starting_page(editor)
        self._inline_rules_editor = editor
        self._inline_rules_context = {"mode": mode, "campaign_name": campaign_name}
        self.dm_tab_btn.setEnabled(False)
        self.player_tab_btn.setEnabled(False)
        # Tabs cannot be switched during rule editing; hiding them also
        # removes a redundant row above the embedded editor.
        self.dm_tab_btn.setVisible(False)
        self.player_tab_btn.setVisible(False)
        self.help_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        # These actions cannot be used while editing.  Don't show disabled
        # blocks in the toolbar or spend width on unavailable controls.
        self.help_btn.setVisible(False)
        self.refresh_btn.setVisible(False)
        self.rules_back_campaign_btn.setVisible(True)
        self.rules_back_campaign_btn.setEnabled(True)
        self.rules_load_btn.setVisible(True)
        self.rules_load_btn.setEnabled(True)
        self._campaign_actions_host.setVisible(True)
        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):
            button.setVisible(False)
        self.role_pages.addWidget(editor)
        self.role_pages.setCurrentWidget(editor)
        editor.accepted.connect(self._inline_rules_saved)
        editor.rejected.connect(self._inline_rules_cancelled)
        editor.show()

    def _load_inline_rules(self):
        editor = getattr(self, "_inline_rules_editor", None)
        if editor is None:
            return
        try:
            editor.load_template_from_ui()
        except Exception as error:
            QMessageBox.warning(self, "Load Rules", str(error))

    def _close_inline_rules_editor(self):
        editor = getattr(self, "_inline_rules_editor", None)
        if editor is None:
            return
        self.role_pages.setCurrentIndex(0)
        self.role_pages.removeWidget(editor)
        editor.setParent(None)
        editor.deleteLater()
        self._inline_rules_editor = None
        self._inline_rules_context = None
        self.rules_back_campaign_btn.setVisible(False)
        self.rules_load_btn.setVisible(False)
        self.dm_tab_btn.setEnabled(True)
        self.player_tab_btn.setEnabled(True)
        self.dm_tab_btn.setVisible(True)
        self.player_tab_btn.setVisible(True)
        self.help_btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.help_btn.setVisible(True)
        self.refresh_btn.setVisible(True)
        self._show_role_page(0)

    def _inline_rules_cancelled(self):
        self._close_inline_rules_editor()

    def _inline_rules_saved(self):
        editor = getattr(self, "_inline_rules_editor", None)
        context = dict(getattr(self, "_inline_rules_context", None) or {})
        if editor is None or self.service is None or getattr(self, "_rules_save_in_flight", False):
            return
        if context.get("mode") != "new" and not self.current_dm_campaign:
            return
        # Template is ordinary dataclass data. Snapshot it while the UI is
        # on the Qt thread; never let a worker inspect live Qt widgets.
        template = copy.deepcopy(editor.template)
        service = self.service
        campaign_id = str((self.current_dm_campaign or {}).get("id") or "")
        campaign_name = str(context.get("campaign_name") or getattr(template, "name", "")).strip()
        self._rules_save_in_flight = True
        editor.setEnabled(False)
        self._hub_rules_epoch += 1
        generation = self._hub_rules_epoch
        def save_remote():
            if context.get("mode") == "new":
                return "new", service.create_campaign(campaign_name, template)
            return "edit", service.update_campaign_template(campaign_id, template)
        self._submit_hub_job("rules_save", generation, save_remote)

    def _finish_inline_rules_save(self, payload, error):
        self._rules_save_in_flight = False
        editor = getattr(self, "_inline_rules_editor", None)
        if editor is not None:
            editor.setEnabled(True)
        if error:
            QMessageBox.warning(self, "Campaign Rules", str(error))
            return  # Leave edits open for correction and retry.
        if not payload:
            return
        mode, result = payload
        if mode == "new":
            created_id = str(result.get("id") or "")
            self._close_inline_rules_editor()
            self.reload_campaigns(select_dm_id=created_id)
        else:
            updated_id = str(result.get("id") or "")
            if self.current_dm_campaign and str(self.current_dm_campaign.get("id") or "") == updated_id:
                self.current_dm_campaign.update(result)
            self._close_inline_rules_editor()
            self._refresh_dm_rules()

    def new_campaign(self):
        if self.service is None:
            return
        self._open_inline_rules_editor(
            CharacterTemplate(name=""),
            mode="new",
            campaign_name=None,
        )

    def edit_dm_rules(self):
        if not self.current_dm_campaign or self.service is None:
            return
        self._open_inline_rules_editor(
            campaign_template(self.current_dm_campaign),
            mode="edit",
        )

    def delete_dm_campaign(self):
        campaign = self.current_dm_campaign
        if not campaign or self.client is None or getattr(self, "_dm_delete_in_flight", False):
            return
        name = str(campaign.get("name") or "this campaign")
        if not _confirm_campaign_delete(self, name):
            return
        campaign_id = str(campaign.get("id") or "")
        self._dm_delete_in_flight = True
        self.delete_campaign_btn.setEnabled(False)
        self._hub_delete_epoch += 1
        generation = self._hub_delete_epoch
        client = self.client
        def delete_remote():
            rows = client._request_json(
                "DELETE", "/rest/v1/campaigns",
                query={"id": f"eq.{campaign_id}",
                       "owner_user_id": f"eq.{client.user_id}", "select": "id"},
                prefer="return=representation",
            )
            if isinstance(rows, list) and not rows:
                raise RuntimeError("The campaign was not deleted. Only its DM can delete it.")
            return campaign_id
        self._submit_hub_job("dm_delete", generation, delete_remote)

    def _finish_dm_campaign_delete(self, campaign_id, error):
        self._dm_delete_in_flight = False
        self.delete_campaign_btn.setEnabled(bool(self.current_dm_campaign))
        if error:
            QMessageBox.warning(self, "Delete Campaign Failed", str(error))
            return
        if not campaign_id:
            return
        # Remove old Discord routes only after confirmed server deletion.
        try:
            config = load_discord_config()
            save_discord_config(remove_discord_binding(config, str(campaign_id)))
        except Exception:
            pass  # Discord bot additionally prunes stale campaign IDs.
        if str((self.current_dm_campaign or {}).get("id") or "") == str(campaign_id):
            self.current_dm_campaign = None
        # The server has confirmed deletion. Forget only links to that exact
        # campaign; never remove saved .didchar files or other campaign links.
        links = getattr(self.client, "links", None)
        if links is not None:
            for character_id, link in list(links.all_links().items()):
                if isinstance(link, dict) and str(link.get("campaign_id") or "") == str(campaign_id):
                    self.client.unlink_local_character(character_id)
        restore_campaign_connection(self.window)
        self.reload_campaigns()

    def remove_dm_character(self, campaign_character_id, display_name):
        if self.client is None or getattr(self, "_dm_remove_in_flight", False):
            return
        if not _confirm_character_removal(self, display_name):
            return
        campaign_id = str((self.current_dm_campaign or {}).get("id") or "")
        self._dm_remove_in_flight = True
        self._hub_remove_epoch += 1
        generation = self._hub_remove_epoch
        client = self.client
        def remove_remote():
            result = client._request_json(
                "POST", "/rest/v1/rpc/did_remove_campaign_character",
                body={"p_campaign_character_id": str(campaign_character_id)},
            )
            if result is False:
                raise RuntimeError("The character could not be removed.")
            return campaign_id
        self._submit_hub_job("dm_remove", generation, remove_remote)

    def _finish_dm_character_remove(self, campaign_id, error):
        self._dm_remove_in_flight = False
        if error:
            QMessageBox.warning(self, "Remove Character Failed", str(error))
        if str((self.current_dm_campaign or {}).get("id") or "") == str(campaign_id):
            self._refresh_dm_characters()  # May have changed even after timeout.

    def join_campaign(self):
        self._show_player_join_form()

    def open_player_campaign(self):
        self._show_role_page(1)
        self._show_player_overview()

    def open_dm_dashboard(self):
        if not self.current_dm_campaign or self.client is None:
            return
        try:
            launch_dm_dashboard(self.client, self.current_dm_campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open DM Dashboard Failed", str(error))

    def open_party_dashboard(self):
        is_player = self.role_pages.currentIndex() == 1
        campaign = self.current_player_campaign if is_player else self.current_dm_campaign
        if not campaign or self.client is None:
            return
        if is_player and not self._player_has_approved_character():
            QMessageBox.information(self, "Character Approval Required",
                "The Party Dashboard is available after the DM approves your campaign character.")
            return
        try:
            launch_party_dashboard(self.client, campaign["id"], app_dir=Path(__file__).resolve().parent)
        except Exception as error:
            QMessageBox.warning(self, "Open Party Dashboard Failed", str(error))

    def open_discord_settings(self):
        campaign = self.current_dm_campaign
        if not campaign:
            return
        dialog = DiscordIntegrationDialog(
            self,
            campaign_id=campaign.get("id"),
            campaign_name=campaign.get("name") or "Campaign",
            app_dir=Path(__file__).resolve().parent,
            campaign_client=self.client,
        )
        dialog.exec()
        self._refresh_discord_action_label()

    def copy_invite_code(self):
        """Show the two useful copy actions directly from the invite code."""
        campaign = self.current_dm_campaign
        if not campaign:
            return
        code = str(campaign.get("invite_code") or "").strip()
        if not code:
            return

        menu = QMenu(self)
        set_themed_stylesheet(menu, ROLE_QSS)
        copy_code_action = menu.addAction("Copy invite code")
        copy_invitation_action = menu.addAction("Copy invitation")
        chosen = menu.exec(
            self.dm_invite_code.mapToGlobal(self.dm_invite_code.rect().bottomLeft())
        )
        if chosen is copy_code_action:
            _copy_text_silent(code)
        elif chosen is copy_invitation_action:
            self.copy_full_invite()

    def copy_full_invite(self):
        text = _campaign_invite_text(self.current_dm_campaign)
        if text:
            _copy_text_silent(text)

def open_campaigns(window):
    dialog = CampaignsHubDialog(window)
    dialog.exec()
    return dialog

def open_dm_campaign_manager(window):
    dialog = DMCampaignManagerDialog(window)
    dialog.exec()
    return dialog


def open_player_campaigns(window):
    dialog = PlayerCampaignsDialog(window)
    dialog.exec()
    return dialog

# Phase 8 player campaign info integration
from phase8_player_ui import apply_phase8_player_ui as _apply_phase8_player_ui
_apply_phase8_player_ui(PlayerCampaignsDialog)



# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_BEGIN
def _did_1013_align_help_refresh(dialog):
    """Use the current compact Campaigns toolbar sizing on first paint."""
    resize = getattr(dialog, "_resize_campaign_tabs", None)
    if callable(resize):
        resize()


def _did_1013_reveal_embedded_page(dialog, attribute):
    """QStackedWidget.removeWidget hides its former page; reveal on entry."""
    page = getattr(dialog, attribute, None)
    if page is None:
        return
    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
    page.setVisible(True)
    page.raise_()
    page.updateGeometry()
# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_END
