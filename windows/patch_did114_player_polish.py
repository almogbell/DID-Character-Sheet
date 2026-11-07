"""DID Character Sheet 1.0.14 -- targeted campaign UI polish.

Compatible with the source variants used in the 1.0.14 campaign releases.
Changes are validated in-memory, compiled, and committed after automatic backup.
"""
from __future__ import annotations
import ast
from datetime import datetime
from pathlib import Path
import shutil
import sys

MARK = '# DID114_PLAYER_POLISH_7_V1'

class PatchStop(Exception):
    pass


def replace_once(text: str, old: str, new: str, title: str) -> str:
    count = text.count(old)
    if count != 1:
        raise PatchStop(f'{title}: expected one match, found {count}. No files changed.')
    return text.replace(old, new, 1)


def patch_source(source: str) -> str:
    if MARK in source:
        return source

    source = replace_once(source,
        'def _prepare_sharing_checkbox(box, *, locked=False):\n',
        MARK + '\ndef _prepare_sharing_checkbox(box, *, locked=False):\n',
        'Checkbox function')

    # Qt QSS unchecked borders add 4px to width/height on top of indicator
    # dimensions, making outlined checkboxes larger than the native blue ones.
    source = replace_once(source,
        'f"QCheckBox::indicator:unchecked {{ border:2px solid {edge}; border-radius:5px; background:{fill}; }}"',
        'f"QCheckBox::indicator:unchecked {{ width:16px; height:16px; border:2px solid {edge}; border-radius:5px; background:{fill}; }}"',
        'Identical indicator outer sizes')

    # Remove the always-on gold highlight from Character Sharing.
    source = replace_once(source,
        'self.player_character_sharing_btn.setObjectName("HubPrimary")\n',
        '# Match the neighboring Party Dashboard and Campaign Info buttons.\n',
        'Sharing tab color')

    # Delete campaign is not an action when the user has no DM campaigns.
    source = replace_once(source,
        '        self.delete_campaign_btn.clicked.connect(self.delete_dm_campaign)\n'
        '        _fit_button(self.delete_campaign_btn)\n',
        '        self.delete_campaign_btn.clicked.connect(self.delete_dm_campaign)\n'
        '        self.delete_campaign_btn.setVisible(False)  # Hidden until a DM campaign is selected.\n'
        '        _fit_button(self.delete_campaign_btn)\n',
        'Hide DM delete action initially')

    source = replace_once(source,
        'self.delete_campaign_btn.setEnabled(bool(campaign))\n',
        'self.delete_campaign_btn.setEnabled(bool(campaign))\n'
        '        self.delete_campaign_btn.setVisible(bool(campaign))\n',
        'Hide empty DM delete button')

    # Both buttons have the same dimensions at every font scaling/DPI.
    source = replace_once(source,
        '        _fit_button(self.refresh_btn)\n        toolbar.addWidget(self.refresh_btn)\n',
        '        toolbar.addWidget(self.refresh_btn)\n'
        '        # Matching buttons: avoid different content-derived widths.\n'
        '        for button in (self.help_btn, self.refresh_btn):\n'
        '            button.setFixedSize(182, 40)\n',
        'Equal help/refresh sizing')
    source = replace_once(source,
        '    width = max(help_button.sizeHint().width(), refresh.sizeHint().width(), 120)\n'
        '    height = max(help_button.sizeHint().height(), refresh.sizeHint().height(), 34)\n'
        '    help_button.setFixedSize(width, height)\n'
        '    refresh.setFixedSize(width, height)\n',
        '    for button in (help_button, refresh):\n'
        '        button.setFixedSize(182, 40)\n',
        'Persist equal sizing after theme updates')

    source = replace_once(source,
        '        self.refresh_btn.setText("Loading…")\n'
        '        _fit_button(self.refresh_btn)\n',
        '        self.refresh_btn.setText("Loading…")\n'
        '        self.refresh_btn.setFixedSize(182, 40)\n',
        'Keep refresh width while loading')
    source = replace_once(source,
        '        self.refresh_btn.setText("Refresh")\n'
        '        _fit_button(self.refresh_btn)\n',
        '        self.refresh_btn.setText("Refresh")\n'
        '        self.refresh_btn.setFixedSize(182, 40)\n',
        'Keep refresh width after loading')

    # Each inline view stays in the overview's scroll area. The left campaign
    # list and the current campaign header remain visible.
    source = replace_once(source,
        '        player_content_layout.addWidget(actions_section)\n\n        character_section = QFrame()\n',
        '        player_content_layout.addWidget(actions_section)\n'
        '        self.player_inline_section = QFrame()\n'
        '        self.player_inline_section.setObjectName("CampaignSection")\n'
        '        inline_layout = QVBoxLayout(self.player_inline_section)\n'
        '        inline_layout.setContentsMargins(8, 8, 8, 8)\n'
        '        self.player_inline_stack = QStackedWidget()\n'
        '        # A bounded height lets the sharing matrix scroll independently\n'
        '        # without replacing the campaign overview or its left list.\n'
        '        self.player_inline_stack.setFixedHeight(475)\n'
        '        inline_layout.addWidget(self.player_inline_stack)\n'
        '        self.player_inline_section.setVisible(False)\n'
        '        player_content_layout.addWidget(self.player_inline_section)\n\n'
        '        character_section = QFrame()\n',
        'Inline details container')

    # The connected character shown here is the one already open on the main
    # character sheet. Don't search by name: character names aren't unique.
    source = replace_once(source,
        '        self.player_character_name = QLabel("-")\n'
        '        self.player_character_name.setStyleSheet("font-size:14px; font-weight:900;")\n'
        '        character_layout.addWidget(self.player_character_name)\n',
        '        self.player_character_name = _CampaignCharacterOpenLabel("-")\n'
        '        self.player_character_name.setStyleSheet("font-size:14px; font-weight:900;")\n'
        '        self.player_character_name._on_open = self._open_linked_player_character\n'
        '        character_layout.addWidget(self.player_character_name)\n',
        'Character name double click')

    # Keep existing 'Back' callbacks but use an appropriate action title.
    source = replace_once(source,
        '        back_btn = QPushButton("← Back to Campaign")\n'
        '        back_btn.setObjectName("CompactButton")\n',
        '        back_btn = QPushButton("Close Character Sharing")\n'
        '        back_btn.setObjectName("CompactButton")\n',
        'Inline sharing close button')
    source = replace_once(source,
        '        self.player_detail_stack.addWidget(character_host)\n',
        '        self.player_inline_stack.addWidget(character_host)\n',
        'Inline sharing ownership')
    source = replace_once(source,
        '            info_back = QPushButton("← Back to Campaign")\n',
        '            info_back = QPushButton("Close Campaign Info")\n',
        'Inline info close button')
    source = replace_once(source,
        '            self.player_info_stack_index = self.player_detail_stack.addWidget(info_host)\n',
        '            self.player_info_stack_index = self.player_inline_stack.addWidget(info_host)\n',
        'Inline info ownership')

    source = replace_once(source,
        '    def _show_player_character_page(self):\n'
        '        if not self.current_player_campaign:\n'
        '            return\n'
        '        self._ensure_player_helper_current()\n'
        '        self._sync_player_helper()\n'
        '        self.player_detail_stack.setCurrentIndex(1)\n'
        '        _did_1013_reveal_embedded_page(self, "_did_1013_character_content")\n',
        '    def _show_player_character_page(self):\n'
        '        if not self.current_player_campaign:\n'
        '            return\n'
        '        self._ensure_player_helper_current()\n'
        '        self._sync_player_helper()\n'
        '        self.player_detail_stack.setCurrentIndex(0)\n'
        '        self.player_inline_stack.setCurrentIndex(0)\n'
        '        self.player_inline_section.setVisible(True)\n'
        '        _did_1013_reveal_embedded_page(self, "_did_1013_character_content")\n',
        'Inline sharing action')
    source = replace_once(source,
        '    def _show_player_overview(self):\n'
        '        self.player_detail_stack.setCurrentIndex(0)\n'
        '        self._refresh_player_details()\n',
        '    def _show_player_overview(self):\n'
        '        self.player_inline_section.setVisible(False)\n'
        '        self.player_detail_stack.setCurrentIndex(0)\n'
        '        self._refresh_player_details()\n',
        'Closing embedded details')
    source = replace_once(source,
        '        if index is not None:\n'
        '            self.player_detail_stack.setCurrentIndex(index)\n'
        '            _did_1013_reveal_embedded_page(self, "_did_1013_info_content")\n',
        '        if index is not None:\n'
        '            self.player_detail_stack.setCurrentIndex(0)\n'
        '            self.player_inline_stack.setCurrentIndex(index)\n'
        '            self.player_inline_section.setVisible(True)\n'
        '            _did_1013_reveal_embedded_page(self, "_did_1013_info_content")\n',
        'Inline info action')

    source = replace_once(source,
        '    def _show_player_join_form(self):\n'
        '        self._show_role_page(1)\n'
        '        self.player_detail_stack.setCurrentIndex(0)\n',
        '    def _show_player_join_form(self):\n'
        '        self._show_role_page(1)\n'
        '        self.player_inline_section.setVisible(False)\n'
        '        self.player_detail_stack.setCurrentIndex(0)\n',
        'Close detail for join form')

    source = replace_once(source,
        '        if hasattr(self, "player_detail_stack"):\n'
        '            self.player_detail_stack.setCurrentIndex(0)\n',
        '        if hasattr(self, "player_detail_stack"):\n'
        '            self.player_detail_stack.setCurrentIndex(0)\n'
        '            self.player_inline_section.setVisible(False)\n',
        'Avoid stale details after campaign switching')

    source = replace_once(source,
        '        if link:\n'
        '            self.player_character_name.setText(name)\n'
        '            details = [x for x in (species, f"Level {level}") if x]\n',
        '        self._player_linked_character_id = character_id if link else None\n'
        '        if link:\n'
        '            self.player_character_name.setCursor(Qt.CursorShape.PointingHandCursor)\n'
        '            self.player_character_name.setToolTip("Double-click to return to this character sheet")\n'
        '            self.player_character_name.setText(name)\n'
        '            details = [x for x in (species, f"Level {level}") if x]\n',
        'Set linked character identity')
    source = replace_once(source,
        '        elif pending_approval:\n'
        '            self.player_character_name.setText(name)\n',
        '        elif pending_approval:\n'
        '            self.player_character_name.setCursor(Qt.CursorShape.ArrowCursor)\n'
        '            self.player_character_name.setToolTip("")\n'
        '            self.player_character_name.setText(name)\n',
        'Clear action for pending character')
    source = replace_once(source,
        '        else:\n'
        '            self.player_character_name.setText(\n'
        '                name if name.strip() and name != "Unnamed Character" else "No linked character"\n',
        '        else:\n'
        '            self.player_character_name.setCursor(Qt.CursorShape.ArrowCursor)\n'
        '            self.player_character_name.setToolTip("")\n'
        '            self.player_character_name.setText(\n'
        '                name if name.strip() and name != "Unnamed Character" else "No linked character"\n',
        'Clear action for unlinked character')
    source = replace_once(source,
        '            self.player_character_name.setText("No character added to this campaign")\n'
        '            self.player_character_status.setText("Create a character or add an existing one to this campaign.")\n',
        '            self.player_character_name.setText("No character added to this campaign")\n'
        '            self.player_character_name.setCursor(Qt.CursorShape.ArrowCursor)\n'
        '            self.player_character_name.setToolTip("")\n'
        '            self.player_character_status.setText("Create a character or add an existing one to this campaign.")\n',
        'Unlinked add character state')

    # Double click returns to the *already loaded* character; no file lookup
    # or overwriting unsaved changes. Other names must never be guessed.
    source = replace_once(source,
        '    def _show_player_join_form(self):\n',
        '    def _open_linked_player_character(self):\n'
        '        campaign = self.current_player_campaign\n'
        '        character = getattr(self.window, "character", None)\n'
        '        current_id = str(getattr(character, "id", "") or "")\n'
        '        if (not campaign or not current_id or\n'
        '                current_id != str(getattr(self, "_player_linked_character_id", "") or "")):\n'
        '            return\n'
        '        # The card displays the open sheet, not an arbitrary remote character.\n'
        '        self.accept()\n'
        '        self.window.show()\n'
        '        self.window.raise_()\n'
        '        self.window.activateWindow()\n\n'
        '    def _show_player_join_form(self):\n',
        'Returning to linked character')

    # Subclass doesn't change font, geometry or stylesheet; just makes an
    # explicit named-character double click accessible and safe.
    source = replace_once(source,
        'class CampaignsHubDialog(QDialog):\n',
        'class _CampaignCharacterOpenLabel(QLabel):\n'
        '    """Double-click a verified linked name to return to its open sheet."""\n'
        '    _on_open = None\n\n'
        '    def mouseDoubleClickEvent(self, event):\n'
        '        if event.button() == Qt.MouseButton.LeftButton and callable(self._on_open):\n'
        '            self._on_open()\n'
        '            event.accept()\n'
        '            return\n'
        '        super().mouseDoubleClickEvent(event)\n\n\n'
        'class CampaignsHubDialog(QDialog):\n',
        'Safe character double-click label')

    # Structural checks: no accidental dialog stack switching.
    if 'self.player_detail_stack.setCurrentIndex(1)' in source or 'self.player_detail_stack.setCurrentIndex(index)' in source:
        raise PatchStop('Separate player detail page still referenced; no files changed.')
    ast.parse(source, filename='campaign_role_ui.py')
    return source


def main():
    root = Path(__file__).resolve().parent
    path = root / 'campaign_role_ui.py'
    if not path.is_file():
        print('STOP: campaign_role_ui.py missing. No files changed.')
        return 1
    try:
        before = path.read_text(encoding='utf-8')
        after = patch_source(before)
        if after == before:
            print('Already applied: player polish patch is present.')
            return 0
        ast.parse(after)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = path.with_name(path.name + f'.before_player_polish_{stamp}.bak')
        shutil.copy2(path, backup)
        path.write_text(after, encoding='utf-8')
        print(f'Applied 1.0.14 player UI polish. Backup: {backup.name}')
        return 0
    except (PatchStop, SyntaxError, OSError) as exc:
        print(f'STOP: {exc}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
