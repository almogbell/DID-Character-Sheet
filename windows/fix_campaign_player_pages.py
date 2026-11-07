#!/usr/bin/env python3
"""Small guarded patch for Campaigns hub UI.

Runs against the user's CURRENT campaign_role_ui.py; it does not replace the
module with an older copy. Backs up the original before changing it. All
replacements are checked before writing.
"""
from __future__ import annotations
import ast
from datetime import datetime
from pathlib import Path
import shutil
import sys

FILE = Path('campaign_role_ui.py')
START = '# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_BEGIN'
END = '# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_END'

HELPER = '''\n# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_BEGIN\ndef _did_1013_align_help_refresh(dialog):\n    """Keep Help and Refresh identical size even after responsive reflow."""\n    help_buttons = [\n        b for b in dialog.findChildren(QPushButton)\n        if b.text().strip() in ("How to Use / Help", "How to Use /Help", "How to Use / Help ")\n    ]\n    refresh = getattr(dialog, "refresh_btn", None)\n    if refresh is None or not help_buttons:\n        return\n    help_button = help_buttons[0]\n    width = max(help_button.sizeHint().width(), refresh.sizeHint().width(), 120)\n    height = max(help_button.sizeHint().height(), refresh.sizeHint().height(), 34)\n    help_button.setFixedSize(width, height)\n    refresh.setFixedSize(width, height)\n\n\ndef _did_1013_reveal_embedded_page(dialog, attribute):\n    """QStackedWidget.removeWidget hides its former page; reveal on entry."""\n    page = getattr(dialog, attribute, None)\n    if page is None:\n        return\n    page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)\n    page.setVisible(True)\n    page.raise_()\n    page.updateGeometry()\n# DID_1013_PLAYER_SUBPAGES_AND_EQUAL_BUTTONS_END\n'''

def patch(src: str) -> str:
    if START in src:
        print('Previously patched; no changes made.')
        return src
    if 'class CampaignsHubDialog(' not in src:
        raise ValueError('CampaignsHubDialog not found; refusing to patch the wrong version')
    if src.count('self.player_detail_stack.setCurrentIndex(1)') != 1:
        raise ValueError('Expected one Character & Sharing page switch')
    if src.count('self.player_detail_stack.setCurrentIndex(index)') != 1:
        raise ValueError('Expected one Campaign Info page switch')
    if src.count('self.player_helper.pages.removeWidget(character_page)') != 1:
        raise ValueError('Expected one embedded character page')
    if src.count('self.player_helper.pages.removeWidget(info_page)') != 1:
        raise ValueError('Expected one embedded campaign info page')
    # Save explicit references to the detached wizard pages and reparent them.
    src = src.replace(
        '        self.player_helper.pages.removeWidget(character_page)\n',
        '        self.player_helper.pages.removeWidget(character_page)\n'
        '        self._did_1013_character_content = character_page\n',
        1,
    )
    src = src.replace(
        '        character_host_layout.addWidget(character_page, 1)\n',
        '        character_page.setParent(character_host)\n'
        '        character_host_layout.addWidget(character_page, 1)\n',
        1,
    )
    src = src.replace(
        '            self.player_helper.pages.removeWidget(info_page)\n',
        '            self.player_helper.pages.removeWidget(info_page)\n'
        '            self._did_1013_info_content = info_page\n',
        1,
    )
    src = src.replace(
        '            info_host_layout.addWidget(info_page, 1)\n',
        '            info_page.setParent(info_host)\n'
        '            info_host_layout.addWidget(info_page, 1)\n',
        1,
    )
    src = src.replace(
        '        self.player_detail_stack.setCurrentIndex(1)\n',
        '        self.player_detail_stack.setCurrentIndex(1)\n'
        '        _did_1013_reveal_embedded_page(self, "_did_1013_character_content")\n',
        1,
    )
    src = src.replace(
        '            self.player_detail_stack.setCurrentIndex(index)\n',
        '            self.player_detail_stack.setCurrentIndex(index)\n'
        '            _did_1013_reveal_embedded_page(self, "_did_1013_info_content")\n',
        1,
    )
    # Insert at the end of CampaignsHubDialog.__init__, not into another dialog
    # or at some random occurrence of reload_campaigns().
    tree = ast.parse(src)
    hub = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignsHubDialog')
    initializer = next(n for n in hub.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == '__init__')
    lines = src.splitlines(keepends=True)
    lines.insert(initializer.end_lineno, '        QTimer.singleShot(0, lambda: _did_1013_align_help_refresh(self))\n')
    src = ''.join(lines)
    # The helper can be declared after the class; names resolve at call time.
    src += '\n' + HELPER
    ast.parse(src)
    return src

def main():
    if not FILE.exists():
        print('ERROR: Run this from the DID Windows project folder containing campaign_role_ui.py')
        return 1
    old = FILE.read_text(encoding='utf-8')
    try:
        new = patch(old)
    except (ValueError, SyntaxError) as exc:
        print('No files changed:', exc)
        return 1
    if new == old:
        return 0
    backup = FILE.with_suffix(FILE.suffix + '.backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(FILE, backup)
    FILE.write_text(new, encoding='utf-8')
    print('Campaigns UI patch applied; backup:', backup)
    print('No database, character files, or Supabase data modified.')
    return 0

if __name__ == '__main__':
    sys.exit(main())
