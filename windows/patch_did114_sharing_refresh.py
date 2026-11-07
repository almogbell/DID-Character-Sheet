#!/usr/bin/env python3
"""Minimal, guarded 1.0.14 UI + campaign/dashboard refresh repair.

Makes backups, validates every edited file before writing, and never modifies
characters, saved campaign data, or Supabase tables.
"""
from __future__ import annotations
import ast
import datetime
import pathlib
import re
import shutil
import sys

MARK = 'DID114_SHARING_AUTO_REFRESH_V1'

class StopPatch(Exception): pass

def replace_once(src: str, old: str, new: str, what: str) -> str:
    n = src.count(old)
    if n != 1:
        raise StopPatch(f'{what}: expected one insertion point; found {n}')
    return src.replace(old, new, 1)

def patch_role(s: str) -> str:
    if MARK in s:
        return s
    if 'class CampaignsHubDialog(' not in s or '_prepare_sharing_checkbox' not in s:
        raise StopPatch('campaign_role_ui.py does not match the 1.0.14 campaign UI')
    # The selected role tab should use the same fill, with a more visible edge.
    s, n = re.subn(
        r'(QPushButton#CampaignRoleTab:checked\s*\{\s*)background\s*:\s*#d8edf7\s*;([^}]*?)border-color\s*:\s*#c79a3b\s*;',
        r'\1background:#fffdf7;\2border:2px solid #b98322;', s, count=1)
    if n != 1:
        raise StopPatch('selected campaign tab styling not found')
    # Checkbox selection and sizing: use a bright outline in dark palettes,
    # preserve the native checked indicator so the check mark is still visible.
    m = re.search(r'(?m)^def _prepare_sharing_checkbox\(box, \*, locked=False\):.*?(?=^def |^class |\Z)', s, re.S|re.M)
    if not m:
        raise StopPatch('_prepare_sharing_checkbox helper not found')
    replacement = '''def _prepare_sharing_checkbox(box, *, locked=False):
    # DID114_SHARING_AUTO_REFRESH_V1: palette-aware contrast & safe click target.
    box.setFixedSize(34, 32)
    dark = QApplication.palette().window().color().lightness() < 145
    edge = "#ffffff" if dark else "#93702b"
    fill = "#18222e" if dark else "#fffdf7"
    box.setStyleSheet(
        "QCheckBox { padding:0px 0px 0px 3px; margin:0px; min-height:30px; }"
        "QCheckBox::indicator { width:20px; height:20px; }"
        f"QCheckBox::indicator:unchecked {{ border:2px solid {edge}; border-radius:5px; background:{fill}; }}"
    )
    if locked:
        box.setChecked(True)
        box.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    else:
        box.setCursor(Qt.CursorShape.PointingHandCursor)
    return box

'''
    s = s[:m.start()] + replacement + s[m.end():]
    # Leave more clearance on the left side of the sharing table.
    s = replace_once(s, 'grid.setContentsMargins(14, 10, 14, 10)', 'grid.setContentsMargins(24, 12, 18, 12)', 'sharing table margins')
    s = replace_once(s, 'grid.addWidget(QLabel("Session dice rolls"), row, 0)',
        'grid.addWidget(QLabel("Session dice rolls (shared)"), row, 0)', 'roll sharing label')
    # The server currently only has one share_session_rolls boolean, so both
    # checkboxes must mirror one another. Allow a local selection while unlinked.
    for line in ('self.roll_share_box.setEnabled(bool(link))','self.party_roll_share_box.setEnabled(bool(link))'):
        s = replace_once(s, line, line.replace('bool(link)', 'True'), 'enable roll toggle')
    s = replace_once(s,
        '''        else:
            checked = False
        self.roll_share_box.setChecked(checked)''',
        '''        else:
            pending_key = (str((self.current_campaign or {}).get("id") or ""),
                           str(getattr(character, "id", "") or ""))
            checked = (bool(getattr(self, "_did114_pending_roll_share", False))
                       if getattr(self, "_did114_pending_roll_key", None) == pending_key else False)
        self.roll_share_box.setChecked(checked)''', 'unlinked roll default')
    # Append a safe attempt to apply a staged value when an active character
    # link appears. Never change a DM setting without the character being linked.
    s = replace_once(s,
        '''        self.party_roll_share_box.blockSignals(False)
        self._load_sharing_preferences()''',
        '''        self.party_roll_share_box.blockSignals(False)
        pending_key = (str((self.current_campaign or {}).get("id") or ""),
                       str(getattr(character, "id", "") or ""))
        if (link and getattr(self, "_did114_pending_roll_key", None) == pending_key
                and getattr(self, "_did114_pending_roll_share", None) is not None):
            self._set_roll_sharing_from_ui(self._did114_pending_roll_share)
        self._load_sharing_preferences()''', 'pending roll apply')
    m = re.search(r'(?m)^    def _set_roll_sharing_from_ui\(self, enabled\):.*?(?=^    def |^class |\Z)', s, re.S|re.M)
    if not m:
        raise StopPatch('roll sharing setter not found')
    replacement = '''    def _set_roll_sharing_from_ui(self, enabled):
        # DID114_SHARING_AUTO_REFRESH_V1: one server setting for DM + Party.
        enabled = bool(enabled)
        link = self._current_link()
        if not link or self.session_service is None:
            self._did114_pending_roll_share = enabled
            character = getattr(self.window, "character", None)
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

'''
    s = s[:m.start()] + replacement + s[m.end():]
    # Two controls are currently mirrored by the server. Tooltips explain
    # this instead of suggesting that DM/Party can be configured separately.
    s = replace_once(s, 'self.roll_share_box.toggled.connect(self._roll_sharing_changed)',
        '''self.roll_share_box.setToolTip("DM and Party rolls share one setting. If not linked, this is a temporary choice until linking.")
        self.party_roll_share_box.setToolTip("DM and Party rolls share one setting. If not linked, this is a temporary choice until linking.")
        self.roll_share_box.toggled.connect(self._roll_sharing_changed)''', 'roll sharing tooltip')
    # Fix the actual unlinked-state assertion from the uploaded 1.0.14 test log.
    # Only touches the player overview, not the local character file.
    if 'def _refresh_player_details(self):' in s and 'No character added to this campaign' not in s:
        hit = re.search(r'(?m)^    def _refresh_player_details\(self\):.*?(?=^    def |^class |\Z)', s, re.S | re.M)
        if not hit or '        summaries = {' not in hit.group(0):
            raise StopPatch('Cannot locate unlinked player overview safely')
        part = hit.group(0)
        part = replace_once(part, '        summaries = {', """        # DID114_SHARING_AUTO_REFRESH_V1: show Add Character when unlinked.
        if not link and not locals().get("pending_approval"):
            self.player_character_name.setText("No character added to this campaign")
            self.player_character_status.setText("Create a character or add an existing one to this campaign.")
            self.player_add_character_btn.setVisible(True)
            if hasattr(self, "player_effects_section"):
                self.player_effects_section.setVisible(False)
        else:
            self.player_add_character_btn.setVisible(False)

        summaries = {""", 'unlinked player overview')
        s = s[:hit.start()] + part + s[hit.end():]
    # Update the visible overview immediately after server-confirmed removal.
    # The older path displayed "Removed from campaign" indefinitely.
    check_method = re.search(r'(?m)^    def _finish_player_link_check\(self, payload, error\):.*?(?=^    def |^class |\Z)', s, re.S | re.M)
    if check_method and "if check.status == 'removed':" in check_method.group(0):
        method = check_method.group(0)
        if 'self.player_add_character_btn.setVisible(True)' not in method:
            call = re.search(r'(?m)^(?P<indent>[ ]+)helper\._refresh_character_page\(\)[ ]*$', method)
            if not call:
                raise StopPatch('Confirmed-removal callback changed; cannot update Add Character state safely')
            outer = call.group('indent')[:-4]
            lines = [
                'self.player_character_name.setText("No character added to this campaign")',
                'self.player_character_status.setText("Removed by the DM. Your local character remains saved.")',
                'self.player_add_character_btn.setVisible(True)',
                'if hasattr(self, "player_effects_section"):',
                '    self.player_effects_section.setVisible(False)',
            ]
            inserted = ''.join('\n'+outer+line for line in lines)
            method = method[:call.end()] + inserted + method[call.end():]
            s = s[:check_method.start()] + method + s[check_method.end():]

    # Silent, low-overhead polling for the non-editable campaign list.
    # The existing hub runs all Supabase jobs on QThreadPool workers.
    if 'def _submit_hub_job(' in s and 'def _drain_hub_results(' in s:
        s = replace_once(s,
            '        self._hub_poll_timer.start()',
            '''        self._hub_poll_timer.start()
        self._did114_auto_epoch = 0
        self._did114_auto_pending = False
        self._did114_auto_timer = QTimer(self)
        self._did114_auto_timer.setInterval(20000)
        self._did114_auto_timer.timeout.connect(self._did114_poll_campaigns)
        self._did114_auto_timer.start()''', 'automatic campaign timer')
        # Existing async hub dispatch: add a new guarded result branch.
        dispatch = re.search(r'(?m)^\s*elif kind == "player_link" and generation == self\._hub_player_link_epoch:\s*\n\s*self\._finish_player_link_check\(payload, error\)', s)
        if not dispatch:
            raise StopPatch('async campaign result dispatcher changed; cannot safely enable auto refresh')
        eol = dispatch.group(0)
        indent = re.search(r'^([ \t]*)elif', eol, re.M).group(1)
        s = s[:dispatch.end()] + f'\n{indent}elif kind == "did114_auto" and generation == self._did114_auto_epoch:\n{indent}    self._did114_apply_campaign_poll(payload, error)' + s[dispatch.end():]
        if 'self._hub_poll_timer.stop()' in s:
            s = replace_once(s, 'self._hub_poll_timer.stop()',
                'self._hub_poll_timer.stop()\n        self._did114_auto_timer.stop()', 'stop periodic poll on close')
        # Caller uses worker-thread-safe network reads only, never QWidget.
        auto_methods = '''    # DID114_SHARING_AUTO_REFRESH_V1: silent, read-only campaign refresh.
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
                self.player_effects_section.setVisible(bool(revealed[1]))

'''
        s = replace_once(s, '    def _submit_hub_job(self, kind, generation, operation):',
            auto_methods + '    def _submit_hub_job(self, kind, generation, operation):', 'campaign hub auto poll methods')
    else:
        # Old source variant: do not inject network requests on the GUI thread.
        # Player can still refresh with the existing button.
        pass
    ast.parse(s)
    return s

def patch_js(s: str, *, dashboard: str) -> str:
    """Add quiet polling without duplicating existing stale-response guards.

    This is deliberately compatible with the EXACT Party/DM files supplied
    in DID114_Debug.zip: both already track a campaignLoadSerial and a
    subscribedCampaignId. Reintroducing them breaks JavaScript and was the
    cause of the repeated source-signature STOP errors.
    """
    if MARK in s:
        return s
    required = (
        'async function loadCurrentCampaign() {',
        '  boot();\n})();',
        'let campaignLoadSerial = 0;',
        'let subscribedCampaignId = "";',
        'if (realtimeChannel && subscribedCampaignId === currentCampaignId) return;',
    )
    for anchor in required:
        if anchor not in s:
            raise StopPatch(f'{dashboard} dashboard missing a required known-safe anchor: {anchor[:70]!r}')
    # The current dashboards already discard stale requests using serial.
    if not re.search(r'\bserial\s*!==\s*campaignLoadSerial', s):
        raise StopPatch(f'{dashboard} has no stale response guard; refusing unsafe polling')
    s = replace_once(s, 'async function loadCurrentCampaign() {',
        'async function loadCurrentCampaign(quiet = false) {', f'{dashboard} quiet loader')
    s = replace_once(s, '    setConnection("Refreshing…", "neutral");',
        '    if (!quiet) setConnection("Refreshing…", "neutral");', f'{dashboard} unobtrusive polling')
    # A new background request must not overwrite the latest campaign.
    # Do not introduce another serial or subscribedCampaignId declaration.
    poll = '''  // DID114_SHARING_AUTO_REFRESH_V1: quiet 20-second fallback to live changes.
  let did114RefreshBusy = false;
  setInterval(async () => {
    if (did114RefreshBusy || document.hidden || !client || !currentCampaignId
        || els.content.classList.contains("hidden")
        || (els.dialog && els.dialog.open)
        || (els.sessionRenameRow && !els.sessionRenameRow.classList.contains("hidden"))) return;
    did114RefreshBusy = true;
    try { await loadCurrentCampaign(true); }
    catch (error) { console.error("Automatic refresh:", error); }
    finally { did114RefreshBusy = false; }
  }, 20000);

'''
    s = replace_once(s, '  boot();\n})();', poll + '  boot();\n})();', f'{dashboard} automatic refresh')
    return s

def apply(root: pathlib.Path) -> list[str]:
    role = root/'campaign_role_ui.py'
    party = root/'party_dashboard'/'app.js'
    dm = root/'dm_dashboard'/'app.js'
    if not role.exists():
        raise StopPatch(f'Missing {role}')
    if not party.exists() or not dm.exists():
        raise StopPatch('Both party_dashboard/app.js and dm_dashboard/app.js are needed. No files changed.')
    source = {role: role.read_text(encoding='utf-8-sig'), party: party.read_text(encoding='utf-8-sig'), dm: dm.read_text(encoding='utf-8-sig')}
    patched = {role: patch_role(source[role]), party: patch_js(source[party],dashboard='party'), dm: patch_js(source[dm],dashboard='dm')}
    # All validation happens before the first write.
    ast.parse(patched[role],filename=str(role))
    if shutil.which('node'):
        import subprocess, tempfile
        for dest in (party,dm):
            with tempfile.NamedTemporaryFile(suffix='.js',mode='w',encoding='utf8',delete=False) as t:
                t.write(patched[dest]);tmp=pathlib.Path(t.name)
            try:
                check=subprocess.run(['node','--check',str(tmp)],capture_output=True,text=True)
                if check.returncode: raise StopPatch(f'{dest.name} JavaScript syntax: {check.stderr[:600]}')
            finally:tmp.unlink(missing_ok=True)
    changed=[]
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    for path, new in patched.items():
        if new == source[path]:continue
        backup=path.with_name(f'{path.name}.before_did114_refresh_{stamp}.bak')
        shutil.copy2(path,backup)
        path.write_text(new,encoding='utf-8')
        changed.append(str(path.relative_to(root)))
    return changed

if __name__ == '__main__':
    root=pathlib.Path(__file__).resolve().parent
    try:
        changed=apply(root)
        print('PATCH OK:', ', '.join(changed) if changed else 'already applied')
    except (StopPatch, SyntaxError) as e:
        print(f'STOP: {e} — no installer built.',file=sys.stderr)
        sys.exit(1)
