"""Incremental 1.0.14 campaign UI repair. No Supabase or character data writes.
Safe to rerun; backs up existing source and validates syntax before modifying it.
"""
from __future__ import annotations
import ast
import os
from datetime import datetime
from pathlib import Path
import re
import shutil
import sys

MARKER = 'DID114_CAMPAIGN_UI_POLISH_V2'
DUP_MARKER = 'DID114_OVERVIEW_HOOK_DEDUP_V3'


def _once(s, old, new, label, optional=False):
    n=s.count(old)
    if n==0 and new in s:
        return s
    if n==0 and optional:
        return s
    if n!=1:
        raise RuntimeError(f'{label}: expected 1 matching block, found {n}. No files changed.')
    return s.replace(old,new,1)


def patch_role(original: str) -> str:
    nl='\r\n' if '\r\n' in original else '\n'
    src=original.replace('\r\n','\n')
    if 'class CampaignsHubDialog(QDialog):' not in src:
        raise RuntimeError('CampaignsHubDialog not found; this is not a recognized 1.0.14 source.')
    lead,body=src.split('class CampaignsHubDialog(QDialog):',1)
    if 'self.player_detail_stack' not in body or 'self.player_campaign_info_btn' not in body:
        raise RuntimeError('Player Campaign Info layout not found. No files changed.')
    if 'self.player_shared_hooks = QLabel(' not in body or 'self.player_shared_effects = QLabel(' not in body:
        raise RuntimeError('The 1.0.14 shared-content panel is missing; install the base 1.0.14 patch first. No files changed.')

    # The hooks already appear in Campaign Info; keep the overview card ONLY for
    # character-specific effects. Keep hidden hooks QLabel alive for older refresh
    # code, but do not insert it in the overview's visual layout.
    if 'reveals_title = QLabel("Shared by the DM")' in body:
        if 'self.player_shared_hooks = QLabel(' not in body:
            raise RuntimeError('Shared-by-DM panel has changed; refusing ambiguous edit.')
        body=_once(body,'reveals_title = QLabel("Shared by the DM")',
                   'reveals_title = QLabel("Effects on My Character")', 'Rename overview card')
        for line in ('reveals_layout.addWidget(hooks_title)',
                     'reveals_layout.addWidget(self.player_shared_hooks)',
                     'reveals_layout.addWidget(effects_title)'):
            body=_once(body,'        '+line+'\n',
                       '        # '+DUP_MARKER+': redundant overview element omitted.\n',
                       'Remove duplicate hook/effect headings')
    elif DUP_MARKER not in body and 'self.player_shared_hooks' in body:
        raise RuntimeError('Unrecognized shared-content overview layout. No files changed.')
    # The card may show only effects after the player links a character.
    if 'self.player_shared_effects = QLabel(' in body and 'self.player_effects_section = reveals_section' not in body:
        body=_once(body,
            '        player_content_layout.addWidget(reveals_section)\n',
            '        self.player_effects_section = reveals_section\n'
            '        player_content_layout.addWidget(reveals_section)\n',
            'Effects card reference',optional=True)
    # Avoid displaying empty effect cards for removed/unlinked characters.
    if 'self.player_effects_section = reveals_section' in body and 'self.player_effects_section.setVisible(bool(link))' not in body:
        target='        link = helper._current_link() if helper is not None else None\n'
        # The link assignment occurs once in the hub refresh routine.
        if body.count(target)==1:
            body=body.replace(target,target+'        self.player_effects_section.setVisible(bool(link))\n',1)

    # The older follow-up hides a second rules summary. Preserve that behavior.
    old='        player_content_layout.addWidget(rules_section)\n'
    if old in body and '        rules_section.setVisible(False)' not in body:
        body=_once(body,old,old+'        rules_section.setVisible(False)\n', 'Rules duplication', optional=True)
    elif 'rules_section.setVisible(False)' in body and old not in body:
        # Some earlier variants already hid the rules section and omitted
        # attaching it. Keep its hidden widget in the layout for compatibility.
        body=_once(body, '        rules_section.setVisible(False)\n',
                   old+'        rules_section.setVisible(False)\n',
                   'Keep hidden rules reference')

    # Fix role tabs clipping: a hard-coded 280px tab group cannot fit both labels.
    if 'tabs_host = QWidget()' in body:
        body=body.replace('        tabs_host.setFixedWidth(280)\n', '',1)
        if 'self._campaign_tabs_host = tabs_host' not in body:
            body=_once(body,'        tabs_host = QWidget()\n',
                   '        tabs_host = QWidget()\n        self._campaign_tabs_host = tabs_host\n',
                   'Campaign tabs host')
        if 'def _resize_campaign_tabs(self):' not in body:
            meth='''    # DID114_CAMPAIGN_UI_POLISH_V2: tabs always fit their text at any DPI.
    def _resize_campaign_tabs(self):
        buttons = (self.dm_tab_btn, self.player_tab_btn)
        total = 6
        for button in buttons:
            button.ensurePolished()
            width = max(168, button.fontMetrics().horizontalAdvance(button.text()) + 42)
            button.setMinimumWidth(0)
            button.setMaximumWidth(16777215)
            button.setFixedWidth(width)
            button.setFixedHeight(39)
            total += width
        self._campaign_tabs_host.setFixedWidth(total)

'''
            body=_once(body,'    def _show_role_page(self, index):',meth+'    def _show_role_page(self, index):', 'Tabs resize method')
        if 'self._resize_campaign_tabs()' not in body:
            pat='        self.player_tab_btn.setText(f"Player Campaigns  ({len(self.player_campaigns)})")\n'
            body=_once(body,pat,pat+'        self._resize_campaign_tabs()\n','Tabs resize on count update')
        # Remove Qt QSS caps that override the label-based sizing.
        def fix_css(m):
            chunk=m.group(0)
            chunk=re.sub(r'min-width\s*:\s*\d+px\s*;', 'min-width:0px;',chunk)
            chunk=re.sub(r'max-width\s*:\s*\d+px\s*;', 'max-width:999px;',chunk)
            chunk=re.sub(r'min-height\s*:\s*\d+px\s*;', 'min-height:35px;',chunk)
            chunk=re.sub(r'max-height\s*:\s*\d+px\s*;', 'max-height:43px;',chunk)
            return chunk
        body=re.sub(r'QPushButton#CampaignRoleTab\s*\{[^}]*\}', fix_css, body, count=1)

    # The optional older follow-up test expects a normal Add Character state.
    if 'self.player_add_character_btn' not in body:
        old='''        character_layout.addWidget(self.player_character_status)
        player_content_layout.addWidget(character_section)'''
        new='''        character_layout.addWidget(self.player_character_status)
        self.player_add_character_btn = QPushButton("+ Add Character")
        self.player_add_character_btn.setObjectName("HubPrimary")
        self.player_add_character_btn.clicked.connect(self._show_player_character_page)
        self.player_add_character_btn.setVisible(False)
        character_layout.addWidget(self.player_add_character_btn, 0, Qt.AlignmentFlag.AlignLeft)
        player_content_layout.addWidget(character_section)'''
        body=_once(body,old,new,'Add Character action',optional=True)
    if 'self.player_add_character_btn' in body:
        # Only patch the old single-path state, never duplicate an updated state.
        old='''        self.player_character_name.setText(name)

        helper = getattr(self, "player_helper", None)
        link = helper._current_link() if helper is not None else None
        details = [x for x in (species, f"Level {level}") if x]
        details.append("Connected to this campaign" if link else "Not connected to this campaign")
        self.player_character_status.setText("  •  ".join(details))'''
        new='''        helper = getattr(self, "player_helper", None)
        link = helper._current_link() if helper is not None else None
        if link:
            self.player_character_name.setText(name)
            self.player_character_status.setText("  •  ".join(
                x for x in (species, f"Level {level}", "Connected to this campaign") if x))
            self.player_add_character_btn.setVisible(False)
        else:
            self.player_character_name.setText("No character added to this campaign")
            self.player_character_status.setText("Add a character using the campaign rules, or connect an existing character.")
            self.player_add_character_btn.setVisible(True)'''
        body=_once(body,old,new,'Restore empty character state',optional=True)
        # Initial no-campaign refresh prevents stale button lingering.
        old='''            self.player_character_status.setText("")
            for label in self.player_rule_summary_labels.values():'''
        new='''            self.player_character_status.setText("")
            self.player_add_character_btn.setVisible(False)
            for label in self.player_rule_summary_labels.values():'''
        body=_once(body,old,new,'Clear no-campaign action',optional=True)

    # Keep narrow gold scrollbars, no native Windows arrow buttons.
    if 'DID114_CAMPAIGN_SCROLLBAR' not in lead:
        bar='''
/* DID114_CAMPAIGN_SCROLLBAR: matches the character sheet. */
QScrollBar:vertical { background: transparent; border: none; width: 9px; margin: 0px; }
QScrollBar::handle:vertical { background: #d9bd82; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #c6a15d; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { border: none; height: 0px; width: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
'''
        old='QScrollArea { background: transparent; border: none; }'
        if old in lead:
            lead=lead.replace(old,old+bar,1)

    result=lead+'class CampaignsHubDialog(QDialog):'+body
    ast.parse(result)
    return result.replace('\n',nl)


def main():
    root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parent
    file=root/'campaign_role_ui.py'
    if not file.is_file():
        raise RuntimeError(f'Expected {file}. Extract into the current code project folder.')
    original=file.read_bytes().decode('utf-8-sig')
    updated=patch_role(original)
    if updated==original:
        print('SUCCESS: 1.0.14 UI repair already applied, no changes needed.')
        return
    compile(updated,str(file),'exec')
    backup=file.with_name(file.name+'.before_1_0_14_repair_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.bak')
    shutil.copy2(file,backup)
    temp=file.with_name(file.name+'.did114_repair_tmp')
    try:
        temp.write_text(updated,encoding='utf-8',newline='')
        os.replace(temp,file)
    finally:
        if temp.exists(): temp.unlink()
    print('SUCCESS: 1.0.14 Campaign Manager UI repaired.')
    print('Backup:',backup)
    print('Shared hooks now appear in Campaign Info rather than twice on the overview.')
    print('Character-specific effects remain available on the overview.')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('STOP:',exc,file=sys.stderr)
        sys.exit(1)
