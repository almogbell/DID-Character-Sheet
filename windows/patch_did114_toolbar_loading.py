"""DID Character Sheet 1.0.14: compact campaigns toolbar, matching help tabs, compact loading notice.

Works on the current campaign hub from DID114_Debug.zip and the subsequent player-polish variant.
Applies both files atomically after validation and backs up originals.
"""
from __future__ import annotations
import ast
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

HUB_MARK = "# DID114_COMPACT_CAMPAIGN_TOOLBAR_V1"
LOADING_MARK = "# DID114_COMPACT_LOADING_NOTICE_V1"

class StopPatch(RuntimeError):
    pass

def once(s, old, new, label):
    count = s.count(old)
    if count != 1:
        raise StopPatch(f"{label}: expected one insertion point, found {count}. No files changed.")
    return s.replace(old, new, 1)

def patch_hub(source: str) -> str:
    if HUB_MARK in source:
        return source
    if "class CampaignsHubDialog(QDialog):" not in source:
        raise StopPatch("CampaignsHubDialog was not found in campaign_role_ui.py")

    # One button family for all four controls, with an outlined active campaign.
    source = once(source,
        '        QPushButton#CampaignRoleTab {\n',
        '        QPushButton#CampaignRoleTab, QPushButton#CampaignToolbarButton {\n',
        'Campaign toolbar stylesheet')
    source = once(source,
        '        QPushButton#CampaignRoleTab:hover { background:#fff4df; border-color:#a87824; }',
        '        QPushButton#CampaignRoleTab:hover, QPushButton#CampaignToolbarButton:hover { background:#fff4df; border-color:#a87824; }',
        'Campaign hover stylesheet')
    # Earlier 1.0.14 fixes already changed the active role tab to a white
    # fill and a gold 2px border. Match the CSS *rule* rather than one exact
    # declaration string; otherwise the older fix makes this patch stop.
    active_rule = re.compile(
        r'(?m)^        QPushButton#CampaignRoleTab:checked\s*\{\s*[^{}]*?^        \}'
    )
    active_matches = list(active_rule.finditer(source))
    if len(active_matches) != 1:
        raise StopPatch(
            'Active campaign button styling: expected one CSS rule, '
            f'found {len(active_matches)}. No files changed.'
        )
    active_css = active_matches[0].group()
    # Keep the selected state visually distinct without a colored fill.
    # Do not duplicate the selected rule if previous patch already did it.
    normalized_active = (
        '        QPushButton#CampaignRoleTab:checked {\n'
        '            background:#fffdf7; color:#25190f; border:2px solid #b98322;\n'
        '        }'
    )
    source = source[:active_matches[0].start()] + normalized_active + source[active_matches[0].end():]

    # DM-only actions belong on their own row; otherwise a small window would
    # crush the four controls in the requested single Campaigns toolbar row.
    source = once(source,
        '        toolbar = QHBoxLayout()\n        toolbar.setSpacing(6)\n',
        '        toolbar = QHBoxLayout()\n        toolbar.setSpacing(6)\n'
        '        self._campaign_actions_host = QWidget()\n'
        '        self._campaign_actions_host.setVisible(False)\n'
        '        self._campaign_actions_layout = QHBoxLayout(self._campaign_actions_host)\n'
        '        self._campaign_actions_layout.setContentsMargins(0, 0, 0, 0)\n'
        '        self._campaign_actions_layout.setSpacing(6)\n'
        '        self._campaign_actions_layout.addStretch(1)\n',
        'Extra DM toolbar row')
    source = once(source,
        '        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):\n'
        '            button.setVisible(False)\n'
        '            _fit_button(button)\n'
        '            toolbar.addWidget(button)\n',
        '        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):\n'
        '            button.setVisible(False)\n'
        '            _fit_button(button)\n'
        '            self._campaign_actions_layout.addWidget(button)\n',
        'DM controls stay accessible in narrow windows')
    source = once(source, '        toolbar.addWidget(self.rules_back_campaign_btn)\n',
                  '        self._campaign_actions_layout.addWidget(self.rules_back_campaign_btn)\n',
                  'Rules back button placement')
    source = once(source, '        toolbar.addWidget(self.rules_load_btn)\n',
                  '        self._campaign_actions_layout.addWidget(self.rules_load_btn)\n',
                  'Rules load button placement')

    source = once(source,
        '        self.help_btn.setObjectName("CompactButton")\n',
        '        self.help_btn.setObjectName("CampaignToolbarButton")\n',
        'Help button style')
    source = once(source,
        '        self.refresh_btn.setObjectName("CompactButton")\n',
        '        self.refresh_btn.setObjectName("CampaignToolbarButton")\n',
        'Refresh button style')
    source = once(source,
        '        root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)\n        root.addSpacing(4)\n',
        '        # DM/Player tabs and Help/Refresh now share one compact toolbar.\n'
        '        toolbar.insertWidget(0, tabs_host)\n'
        '        root.addWidget(self._campaign_actions_host, 0, Qt.AlignmentFlag.AlignRight)\n'
        '        root.addSpacing(4)\n',
        'Move the tabs above campaign contents')
    source = once(source,
        '        root.addLayout(header)\n        root.addSpacing(4)\n        root.addLayout(toolbar)\n        root.addSpacing(6)\n',
        '        root.addLayout(header)\n        root.addSpacing(6)\n        root.addLayout(toolbar)\n',
        'Trim the gap above the campaign content')

    # Preserve the method name used by every existing reload/refresh callback.
    pattern = r'(?ms)^    # DID114_CAMPAIGN_UI_POLISH_V2:.*?^    def _resize_campaign_tabs\(self\):\n.*?(?=^    def _show_role_page\(self, index\):)'
    replacement = '''    # DID114_COMPACT_CAMPAIGN_TOOLBAR_V1: consistent sizing at Windows DPI scales.
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

'''
    source, count = re.subn(pattern, replacement, source, count=1)
    if count != 1:
        # Support older source without the marker comment.
        pattern2 = r'(?ms)^    def _resize_campaign_tabs\(self\):\n.*?(?=^    def _show_role_page\(self, index\):)'
        source, count = re.subn(pattern2, replacement, source, count=1)
    if count != 1:
        raise StopPatch("Campaign tab resizing function could not be found")
    source = once(source,
        '        self.help_btn.setText("← Back to Campaign")\n',
        '        self.help_btn.setText("← Back")\n',
        'Compact help return label')
    source = once(source,
        '        self.help_btn.setText("How to Use / Help")\n        self._update_header_actions()\n',
        '        self.help_btn.setText("How to Use / Help")\n'
        '        self._resize_campaign_tabs()\n'
        '        self._update_header_actions()\n',
        'Resize toolbar on page changes')

    # Place the contextual DM actions in their own row only when needed.
    source = once(source,
        '                button.setVisible(show_dm_actions)\n                button.setEnabled(show_dm_actions)\n',
        '                button.setVisible(show_dm_actions)\n                button.setEnabled(show_dm_actions)\n'
        '        self._campaign_actions_host.setVisible(\n'
        '            show_dm_actions or getattr(self, "_inline_rules_editor", None) is not None\n'
        '        )\n',
        'Toggle the DM-only toolbar')
    source = once(source,
        '        self.rules_load_btn.setEnabled(True)\n        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):\n',
        '        self.rules_load_btn.setEnabled(True)\n'
        '        self._campaign_actions_host.setVisible(True)\n'
        '        for button in (self.dm_dashboard_btn, self.party_dashboard_dm_btn, self.discord_settings_btn):\n',
        'Keep rules actions visible')

    # Help tabs become themed, rounded Campaign-style buttons rather than flat system tabs.
    source = once(source,
        '        tabs = QTabWidget(frame)\n        tabs.setDocumentMode(True)\n',
        '        tabs = QTabWidget(frame)\n'
        '        tabs.setDocumentMode(False)\n'
        '        tabs.tabBar().setExpanding(False)\n'
        '        set_themed_stylesheet(tabs.tabBar(), """\n'
        '            QTabBar::tab { background:#fffdf7; color:#25190f; border:1px solid #c79a3b;\n'
        '                border-radius:9px; padding:8px 19px; min-height:28px; min-width:94px;\n'
        '                margin-right:7px; font-family:Georgia; font-size:12px; font-weight:900; }\n'
        '            QTabBar::tab:selected { background:#fff1d6; border:2px solid #b98322; }\n'
        '            QTabBar::tab:hover { background:#fff4df; }\n'
        '        """)\n',
        'Help tab styling')

    # Old and polished variants each resized the Refresh button on every
    # network request. Replace both with the compact, stable-size rule.
    source, progress_count = re.subn(
        r'(?m)^        self.refresh_btn.setText\("Loading…"\)\n'
        r'        (?:_fit_button\(self.refresh_btn\)|self.refresh_btn.setFixedSize\(182, 40\))\n',
        '        self.refresh_btn.setText("Refresh")\n'
        '        self.refresh_btn.setToolTip("Checking campaigns…")\n'
        '        self._resize_campaign_tabs()\n',
        source, count=1)
    if progress_count != 1:
        raise StopPatch("Refresh progress state is unfamiliar")
    source, finished_count = re.subn(
        r'(?m)^        self.refresh_btn.setText\("Refresh"\)\n'
        r'        (?:_fit_button\(self.refresh_btn\)|self.refresh_btn.setFixedSize\(182, 40\))\n'
        r'(?=        if error:)',
        '        self.refresh_btn.setText("Refresh")\n'
        '        self._resize_campaign_tabs()\n',
        source, count=1)
    if finished_count != 1:
        raise StopPatch("Refresh completion state is unfamiliar")
    # A late 1.0.14 polish gave these buttons fixed 182px widths at startup.
    # No extra first-paint sizing should override the compact toolbar.
    old_big = ('        for button in (self.help_btn, self.refresh_btn):\n'
               '            button.setFixedSize(182, 40)\n')
    if old_big in source:
        source = once(source, old_big,
            '        # Campaign toolbar dimensions are managed by _resize_campaign_tabs.\n',
            'Remove old oversized initial buttons')
    source = once(source,
        '            item.setFlags(Qt.ItemFlag.NoItemFlags)\n            widget.addItem(item)\n',
        '            item.setFlags(Qt.ItemFlag.NoItemFlags)\n'
        '            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)\n'
        '            widget.addItem(item)\n',
        'Centered loading placeholder')

    # This old size equalizer runs after the widget is built. Forward to the
    # new compact sizing rule so the old timer cannot restore giant buttons.
    source, n = re.subn(
        r'(?ms)^def _did_1013_align_help_refresh\(dialog\):\n.*?(?=^def _did_1013_reveal_embedded_page\(dialog, attribute\):)',
        'def _did_1013_align_help_refresh(dialog):\n'
        '    """Use the current compact Campaigns toolbar sizing on first paint."""\n'
        '    resize = getattr(dialog, "_resize_campaign_tabs", None)\n'
        '    if callable(resize):\n'
        '        resize()\n\n\n',
        source, count=1)
    if n != 1:
        raise StopPatch("Legacy Help/Refresh sizing helper not found")

    # Explicit visible height comes only from the one toolbar plus contextual
    # DM controls. No tab row is left between the toolbar and campaign list.
    ast.parse(source, filename="campaign_role_ui.py")
    return source


def patch_loading(source: str) -> str:
    if LOADING_MARK in source:
        return source
    if 'class BusyNotice(QDialog):' not in source:
        raise StopPatch("BusyNotice not found in ui_feedback.py")
    source = once(source,
        'from PySide6.QtWidgets import QWidget, QDialog, QHBoxLayout, QLabel\n',
        'from PySide6.QtWidgets import QWidget, QDialog, QHBoxLayout, QLabel, QApplication, QLayout\n',
        'Compact loading widget imports')
    source = once(source,
        'class BusyNotice(QDialog):\n',
        LOADING_MARK + '\nclass BusyNotice(QDialog):\n',
        'Loading patch marker')
    source = once(source,
        '        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)\n        self.done_loading = False\n',
        '        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)\n'
        '        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)\n'
        '        self.done_loading = False\n',
        'Styled loader background')
    source = once(source,
        '        layout = QHBoxLayout(self)\n        layout.setContentsMargins(16, 12, 20, 12)\n        layout.addWidget(LoadingRing(self))\n        layout.addWidget(QLabel(text, self))\n',
        '        layout = QHBoxLayout(self)\n'
        '        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)\n'
        '        layout.setContentsMargins(18, 14, 20, 14)\n'
        '        layout.setSpacing(12)\n'
        '        layout.addWidget(LoadingRing(self), 0, Qt.AlignmentFlag.AlignVCenter)\n'
        '        self.status_label = QLabel(str(text), self)\n'
        '        self.status_label.setWordWrap(True)\n'
        '        self.status_label.setMaximumWidth(360)\n'
        '        self.status_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)\n'
        '        layout.addWidget(self.status_label, 1)\n',
        'Loading notice layout')
    source = once(source,
        '        self.adjustSize()\n        owner = self.parentWidget()\n        center = owner.mapToGlobal(owner.rect().center())\n        self.move(center.x()-self.width()//2, center.y()-self.height()//2)\n        self.show()\n        self.raise_()\n',
        '        self.adjustSize()\n'
        '        owner = self.parentWidget()\n'
        '        center = owner.mapToGlobal(owner.rect().center()) if owner else None\n'
        '        if center is not None:\n'
        '            x = center.x() - self.width() // 2\n'
        '            y = center.y() - self.height() // 2\n'
        '            screen = owner.screen() or QApplication.primaryScreen()\n'
        '            if screen is not None:\n'
        '                bounds = screen.availableGeometry()\n'
        '                x = max(bounds.left(), min(x, bounds.right() - self.width() + 1))\n'
        '                y = max(bounds.top(), min(y, bounds.bottom() - self.height() + 1))\n'
        '            self.move(x, y)\n'
        '        self.show()\n        self.raise_()\n',
        'Center the loading notice without clipping')
    ast.parse(source, filename="ui_feedback.py")
    return source


def main() -> int:
    root = Path(__file__).resolve().parent
    files = [root / "campaign_role_ui.py", root / "ui_feedback.py"]
    try:
        if any(not x.is_file() for x in files):
            raise StopPatch("Expected campaign_role_ui.py and ui_feedback.py beside this script")
        before = [x.read_text(encoding="utf-8") for x in files]
        after = [patch_hub(before[0]), patch_loading(before[1])]
        if before == after:
            print("Already applied: DID 1.0.14 compact toolbar/loading fix.")
            return 0
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        for file, old, new in zip(files, before, after):
            if old == new:
                continue
            backup = file.with_name(file.name + f".before_toolbar_{stamp}.bak")
            shutil.copy2(file, backup)
            temp = file.with_name(file.name + ".did114new")
            temp.write_text(new, encoding="utf-8")
            temp.replace(file)
            print(f"Patched {file.name}; backup: {backup.name}")
        print("SUCCESS: DID Character Sheet 1.0.14 compact toolbar and loading notice patch applied.")
        return 0
    except (StopPatch, SyntaxError, OSError) as exc:
        print(f"STOP: {exc}. No unsupported source transformations applied.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
