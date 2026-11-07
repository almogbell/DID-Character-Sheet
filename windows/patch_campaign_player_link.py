"""Guarded 1.0.13 patch for async player-side stale link reconciliation.

Edits local campaign_role_ui.py with a timestamped backup, never overwrites the
file from an older ZIP. Fails closed if expected Problem 17 structure changed.
"""
from pathlib import Path
from datetime import datetime
import shutil, sys

P=Path('campaign_role_ui.py')

def replace_once(s,old,new):
    if s.count(old)!=1:
        raise ValueError(f'Expected one anchor but found {s.count(old)}: {old[:90]!r}')
    return s.replace(old,new,1)

def main():
    if not P.is_file():
        print('Run this from your current code folder (campaign_role_ui.py missing).')
        return 1
    s=P.read_text('utf8')
    if 'DID_PLAYER_LINK_CHECK_V1' in s:
        print('Player link reconciliation is already patched; no changes made.')
        return 0
    if '_hub_results' not in s or '_submit_hub_job' not in s:
        print('This file is not the expected 1.0.13 Problem 17 UI. No changes made.')
        return 1
    s=replace_once(s,
'''        self._hub_discord_epoch = 0
        self._hub_closed = False''',
'''        self._hub_discord_epoch = 0
        self._hub_player_link_epoch = 0
        self._hub_player_link_token = None
        self._hub_closed = False''')
    s=replace_once(s,
'''        self._hub_discord_epoch += 1
        self._hub_poll_timer.stop()''',
'''        self._hub_discord_epoch += 1
        self._hub_player_link_epoch += 1
        self._hub_poll_timer.stop()''')
    s=replace_once(s,
'''            elif kind == "discord" and generation == self._hub_discord_epoch:
                self._finish_discord_label(payload, error)''',
'''            elif kind == "discord" and generation == self._hub_discord_epoch:
                self._finish_discord_label(payload, error)
            elif kind == "player_link" and generation == self._hub_player_link_epoch:
                self._finish_player_link_check(payload, error)''')
    s=replace_once(s,
'''        self._hub_target_dm_id = str(select_dm_id or "")
        self._hub_target_player_id = str(select_player_id or "")''',
'''        self._hub_player_link_token = None
        self._hub_player_link_epoch += 1
        self._hub_target_dm_id = str(select_dm_id or "")
        self._hub_target_player_id = str(select_player_id or "")''')
    s=replace_once(s,
'''    def _player_selection_changed(self, row):
        self.current_player_campaign = self.player_campaigns[row]''',
'''    def _player_selection_changed(self, row):
        self._hub_player_link_token = None
        self._hub_player_link_epoch += 1
        self.current_player_campaign = self.player_campaigns[row]''')
    idx=s.index('    def _clear_layout(self, layout):',s.index('class CampaignsHubDialog(QDialog):'))
    s=s[:idx]+"        self._schedule_player_link_check(campaign, character, link)\n\n"+s[idx:]
    idx=s.index('    def _clear_layout(self, layout):',s.index('class CampaignsHubDialog(QDialog):'))
    snippet='''    # DID_PLAYER_LINK_CHECK_V1 — asynchronous server-verified link reconciliation.
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
        elif check.status == 'offline':
            self.player_character_status.setToolTip(check.message)
        elif check.status == 'active':
            self.player_character_status.setToolTip('Character is active in this campaign.')

'''
    s=s[:idx]+snippet+s[idx:]
    # A single guarded and backed-up write; py_compile syntax check BEFORE replacement.
    compile(s,str(P),'exec')
    backup=P.with_name('campaign_role_ui.py.backup_before_player_link_'+datetime.now().strftime('%Y%m%d_%H%M%S'))
    shutil.copy2(P,backup)
    P.write_text(s,'utf8')
    print('Applied asynchronous player campaign-link verification to',P)
    print('Backup:',backup)
    return 0

if __name__=='__main__':sys.exit(main())
