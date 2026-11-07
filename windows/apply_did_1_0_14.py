"""Non-destructive targeted 1.0.14 patch. Run in Windows DID source folder.

Backups are created for every modified source file. Stops on unfamiliar source.
"""
from __future__ import annotations
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = 'DID114_PLAYER_REVEALS'


def replace_exact(text, before, after, label):
    count = text.count(before)
    if count != 1:
        raise RuntimeError(f'{label}: expected exactly one insertion point; found {count}. Source may differ. No files changed.')
    return text.replace(before, after, 1)


def patch_role(text):
    """Apply 1.0.14 UI additions to both the older and already-patched hub.

    This accepts harmless changes in CSS/spacing and optional Problem 18 code,
    but fails closed if the actual campaign structure is unfamiliar.
    """
    import ast

    if MARKER in text and 'def _refresh_player_reveals(self):' in text:
        return text
    if 'class CampaignsHubDialog(' not in text:
        raise RuntimeError('campaign_role_ui.py: CampaignsHubDialog was not found.')
    if 'from campaign_player_reveals import load_player_reveals' not in text:
        found = re.search(r'(?m)^from campaign_party_bridge import open_party_dashboard as launch_party_dashboard\s*$', text)
        if not found:
            raise RuntimeError('campaign_role_ui.py: player reveal import location changed; source not edited.')
        text = text[:found.end()] + ('\nfrom campaign_player_reveals import load_player_reveals, format_entries, format_effects') + text[found.end():]

    # CSS changes are optional: custom themes should not prevent the functional patch.
    css_start = text.find('QPushButton#CampaignRoleTab {')
    if css_start >= 0:
        css_end = text.find('}', css_start)
        if css_end >= 0:
            block = text[css_start:css_end]
            block = re.sub(r'min-width\s*:\s*\d+px\s*;', 'min-width:0px;', block, count=1)
            block = re.sub(r'max-width\s*:\s*\d+px\s*;', 'max-width:300px;', block, count=1)
            text = text[:css_start] + block + text[css_end:]

    if 'tabs_host = QWidget()' not in text:
        # The original role selector is a horizontal layout directly in root.
        pattern = (r'(?m)^([ \t]+)tabs\s*=\s*QHBoxLayout\(\)\s*\n'
                   r'\1tabs\.setContentsMargins\([^\n]*\)\s*\n'
                   r'\1tabs\.setSpacing\([^\n]*\)')
        m = re.search(pattern, text)
        if m is None:
            raise RuntimeError('campaign_role_ui.py: cannot identify campaign tabs layout; no files changed.')
        indent = m.group(1)
        new = (indent + '# 1.0.14: campaign tabs sit together above the list\n'
               + indent + 'tabs_host = QWidget()\n'
               + indent + 'tabs_host.setFixedWidth(280)\n'
               + indent + 'tabs_host.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)\n'
               + indent + 'tabs = QHBoxLayout(tabs_host)\n'
               + indent + 'tabs.setContentsMargins(0, 0, 0, 0)\n'
               + indent + 'tabs.setSpacing(6)')
        text = text[:m.start()] + new + text[m.end():]
        tail_pattern = (r'(?m)^([ \t]+)tabs\.addWidget\(self\.dm_tab_btn\)\s*\n'
                        r'\1tabs\.addWidget\(self\.player_tab_btn\)\s*\n'
                        r'\1tabs\.addStretch\(\)\s*\n'
                        r'\1root\.addLayout\(tabs\)')
        m = re.search(tail_pattern, text)
        if m is None:
            raise RuntimeError('campaign_role_ui.py: cannot identify existing tab-to-root arrangement; no files changed.')
        indent = m.group(1)
        new = (indent + 'tabs.addWidget(self.dm_tab_btn, 1)\n'
               + indent + 'tabs.addWidget(self.player_tab_btn, 1)\n'
               + indent + 'root.addWidget(tabs_host, 0, Qt.AlignmentFlag.AlignLeft)')
        text = text[:m.start()] + new + text[m.end():]
    elif 'root.addWidget(tabs_host' not in text:
        raise RuntimeError('campaign_role_ui.py: a tab host already exists but is not attached to root.')

    if 'self.player_shared_hooks = QLabel(' not in text:
        anchor = re.compile(r'(?m)^([ \t]+)player_content_layout\.addWidget\(rules_section\)\s*\n\1player_content_layout\.addStretch\(1\)')
        m = anchor.search(text)
        if m is None:
            raise RuntimeError('campaign_role_ui.py: cannot locate player rules panel; no files changed.')
        indent=m.group(1)
        block='''# DID114_PLAYER_REVEALS: Read-only content revealed by the DM.
reveals_section = QFrame()
reveals_section.setObjectName("CampaignSection")
reveals_layout = QVBoxLayout(reveals_section)
reveals_layout.setContentsMargins(12, 10, 12, 10)
reveals_layout.setSpacing(6)
reveals_title = QLabel("Shared by the DM")
reveals_title.setStyleSheet("font-size:15px; font-weight:900;")
reveals_layout.addWidget(reveals_title)
hooks_title = QLabel("Hooks, Clues & Quests")
hooks_title.setStyleSheet("font-size:12px; font-weight:900;")
reveals_layout.addWidget(hooks_title)
self.player_shared_hooks = QLabel("Press Refresh to load shared hooks.")
self.player_shared_hooks.setObjectName("Muted")
self.player_shared_hooks.setTextFormat(Qt.TextFormat.PlainText)
self.player_shared_hooks.setWordWrap(True)
reveals_layout.addWidget(self.player_shared_hooks)
effects_title = QLabel("Effects on My Character")
effects_title.setStyleSheet("font-size:12px; font-weight:900;")
reveals_layout.addWidget(effects_title)
self.player_shared_effects = QLabel("No effects loaded.")
self.player_shared_effects.setObjectName("Muted")
self.player_shared_effects.setTextFormat(Qt.TextFormat.PlainText)
self.player_shared_effects.setWordWrap(True)
reveals_layout.addWidget(self.player_shared_effects)
player_content_layout.addWidget(reveals_section)'''
        insert = '\n'.join(indent + line for line in block.splitlines())
        replacement = indent + 'player_content_layout.addWidget(rules_section)\n' + insert + '\n' + indent + 'player_content_layout.addStretch(1)'
        text = text[:m.start()] + replacement + text[m.end():]
    elif MARKER not in text:
        # An earlier experimental version may have the panel but no marker.
        # Don't add duplicate controls; let the AST integration below proceed.
        pass

    if ('self.player_detail_stack.addWidget(overview_page)' in text and
        'overview_scroll.setWidget(overview_page)' not in text):
        text = replace_exact(text,
            '        self.player_detail_stack.addWidget(overview_page)',
            '        # Keep revealed DM messages scrollable on smaller screens.\n'
            '        overview_scroll = QScrollArea()\n'
            '        overview_scroll.setWidgetResizable(True)\n'
            '        overview_scroll.setFrameShape(QFrame.Shape.NoFrame)\n'
            '        overview_scroll.setWidget(overview_page)\n'
            '        self.player_detail_stack.addWidget(overview_scroll)',
            'Scrollable player campaign overview')

    tree = ast.parse(text)
    hub = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignsHubDialog'), None)
    if hub is None:
        raise RuntimeError('Campaign hub class is missing.')
    refresh = next((n for n in hub.body if isinstance(n, ast.FunctionDef) and n.name == '_refresh_player_details'), None)
    if refresh is None:
        raise RuntimeError('campaign_role_ui.py: _refresh_player_details method missing.')
    lines = text.splitlines(keepends=True)
    method_text = ''.join(lines[refresh.lineno-1:refresh.end_lineno])
    if 'self._refresh_player_reveals()' not in method_text:
        # Add to method tail, preserving existing asynchronous link verification.
        lines.insert(refresh.end_lineno, '        self._refresh_player_reveals()\n')
        text = ''.join(lines)

    if 'def _refresh_player_reveals(self):' not in text:
        tree = ast.parse(text)
        hub = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'CampaignsHubDialog')
        refresh = next(n for n in hub.body if isinstance(n, ast.FunctionDef) and n.name == '_refresh_player_details')
        lines = text.splitlines(keepends=True)
        new_method = '''
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
'''
        lines.insert(refresh.end_lineno, new_method)
        text = ''.join(lines)
    ast.parse(text)
    return text

def patch_party_html(text):
    """Add the revealed-hooks section before the existing party display area.

    Do not assume the summary div has the same whitespace/classes across releases.
    """
    if 'id="visibleEntrySection"' in text or "id='visibleEntrySection'" in text:
        return text
    section = (
        '      <section id="visibleEntrySection" aria-label="Hooks and clues shared by the DM">\n'
        '        <h2>Shared Hooks &amp; Clues</h2>\n'
        '        <div id="visibleEntryGrid" class="party-grid"></div>\n'
        '      </section>\n\n'
    )
    for name in ('partySummary', 'partyGrid'):
        anchors = list(re.finditer(
            r'(?m)^[ \t]*<(?:div|section)\b[^>]*\bid\s*=\s*[\"\']'
            + re.escape(name) + r'[\"\'][^>]*>', text
        ))
        if len(anchors) == 1:
            return text[:anchors[0].start()] + section + text[anchors[0].start():]
        if len(anchors) > 1:
            raise RuntimeError('Party dashboard HTML: multiple ' + name + ' sections; source not edited.')
    raise RuntimeError('Party dashboard HTML: cannot find a unique partySummary or partyGrid section; source not edited.')


def _js_function_section(text, function_name):
    """Locate a top-level JS function by indentation, not an exact statement.

    Accept both function declarations and arrow-function assignments. A missing
    function is an explicit compatibility failure, not permission to guess.
    """
    declaration = re.compile(
        r'(?m)^([ \t]*)(?:(?:async\s+)?function\s+' + re.escape(function_name)
        + r'\s*\(|(?:const|let|var)\s+' + re.escape(function_name)
        + r'\s*=\s*(?:async\s*)?\([^\n]*?=>\s*\{)'
    )
    matches = list(declaration.finditer(text))
    if len(matches) != 1:
        raise RuntimeError('Party dashboard app.js: expected exactly one ' + function_name
                           + ' function; found ' + str(len(matches)) + '. No files changed.')
    found = matches[0]
    indent = found.group(1)
    close = re.search(r'(?m)^' + re.escape(indent) + r'\}[ \t]*;?[ \t]*$', text[found.end():])
    if close is None:
        raise RuntimeError('Party dashboard app.js: cannot identify end of ' + function_name
                           + ' without risking adjacent code. No files changed.')
    return found.end(), found.end() + close.start(), indent,


def patch_party_js(text):
    """Add hook loading to every refresh and realtime notifications if supported.

    A previous patch required the literal `await loadVisibleNPCs();` immediately
    before `subscribeRealtime();`. That misses newer refresh structures.
    """
    function_signature = re.compile(r'\b(?:async\s+)?function\s+loadVisibleEntries\s*\(')
    if not function_signature.search(text):
        # Insert before the realtime setup function, not inside it.
        _js_function_section(text, 'subscribeRealtime')
        match = re.search(
            r'(?m)^([ \t]*)(?:(?:async\s+)?function\s+subscribeRealtime\s*\('
            r'|(?:const|let|var)\s+subscribeRealtime\s*=)', text)
        if not match:
            raise RuntimeError('Party dashboard app.js: cannot insert shared hooks loader safely.')
        indent = match.group(1)
        # Keep a single row formatter: all untrusted fields must pass escapeHtml.
        loader = """// DID114_PLAYER_REVEALS: RLS restricts results to DM-shared entries.
async function loadVisibleEntries() {
  const section = document.getElementById("visibleEntrySection");
  const grid = document.getElementById("visibleEntryGrid");
  if (!section || !grid || !currentCampaignId) return;
  section.classList.remove("hidden");
  grid.textContent = "Loading shared hooks...";
  const response = await client
    .from("campaign_entries")
    .select("id,entry_type,title,body,status,visible_to_players")
    .eq("campaign_id", currentCampaignId)
    .eq("visible_to_players", true)
    .order("updated_at", { ascending: false });
  if (response.error) {
    console.error("Player-visible hooks:", response.error);
    grid.textContent = "Shared hooks could not be loaded: " + response.error.message;
    return;
  }
  const entries = response.data || [];
  if (!entries.length) {
    grid.textContent = "The DM has not shared any hooks or clues yet.";
    return;
  }
  grid.innerHTML = entries.map(entry => `
    <article class="character-card">
      <div class="card-head">
        <div class="card-title">
          <div class="card-subtitle">${escapeHtml(entry.entry_type || "Hook")}${entry.status ? " · " + escapeHtml(entry.status) : ""}</div>
          <h3>${escapeHtml(entry.title || "Untitled")}</h3>
        </div>
      </div>
      <div class="summary-text">${escapeHtml(entry.body || "")}</div>
    </article>
  `).join("");
}

"""
        text = text[:match.start()] + ''.join(indent + line if line.strip() else line for line in loader.splitlines(keepends=True)) + text[match.start():]

    # Locate the refresh function independently from its internal NPC call.
    start, end, indent = _js_function_section(text, 'loadCurrentCampaign')
    body = text[start:end]
    if not re.search(r'\bloadVisibleEntries\s*\(', body):
        # Use a nearby load operation where possible, but do not insist on
        # exact semicolons/indentation or adjacent subscribeRealtime() calls.
        candidates = [
            r'(?m)^[ \t]*(?:await\s+)?loadVisibleNPCs\s*\([^\n]*\)[ \t]*;?[ \t]*$',
            r'(?m)^[ \t]*(?:await\s+)?renderParty\s*\([^\n]*\)[ \t]*;?[ \t]*$',
        ]
        anchor = None
        for pattern in candidates:
            occurrences = list(re.finditer(pattern, body))
            if len(occurrences) == 1:
                anchor = occurrences[0].end()
                break
        if anchor is None:
            # Fallback to the beginning of subscription/connection-ready line.
            for pattern in (
                r'(?m)^[ \t]*subscribeRealtime\s*\([^\n]*\)',
                r'(?m)^[ \t]*setConnection\s*\([^\n]*\)',
            ):
                occurrences = list(re.finditer(pattern, body))
                if len(occurrences) == 1:
                    anchor = occurrences[0].start()
                    break
        if anchor is None:
            raise RuntimeError('Party dashboard load shared hooks: cannot locate a safe refresh '
                               'point in loadCurrentCampaign(). No files changed. '
                               'Please share party_dashboard/app.js to support this version.')
        async_refresh = bool(re.search(r'(?:async\s+function\s+loadCurrentCampaign\s*\(|'
                                       r'loadCurrentCampaign\s*=\s*async\s*\()', text[max(0, start-150):start]))
        # Most supported versions are async functions. For sync variants avoid
        # syntax errors by using the promise form.
        call = 'await loadVisibleEntries();' if async_refresh else 'loadVisibleEntries().catch(error => console.error(error));'
        line_indent = indent + '  '
        body = body[:anchor] + '\n' + line_indent + call + body[anchor:]
        text = text[:start] + body + text[end:]

    # Realtime is a bonus, not the only way to get hooks: refresh always loads
    # the entry list. This routine must not inject twice after rerunning.
    start, end, indent = _js_function_section(text, 'subscribeRealtime')
    body = text[start:end]
    if not re.search(r'table\s*:\s*[\"\']campaign_entries[\"\']', body):
        subscriptions = list(re.finditer(r'(?m)^[ \t]*\.subscribe\s*\(', body))
        if len(subscriptions) == 1:
            at = subscriptions[0].start()
            lead = re.match(r'[ \t]*', body[at:]).group(0)
            snippet = (
                lead + '.on("postgres_changes", { event: "*", schema: "public", table: "campaign_entries", filter: `campaign_id=eq.${currentCampaignId}` }, () => {\n'
                + lead + '  loadVisibleEntries().catch(error => console.error(error));\n'
                + lead + '})\n'
            )
            body = body[:at] + snippet + body[at:]
            text = text[:start] + body + text[end:]
        # If the dashboard has a different subscription model, do not modify
        # it blindly. Refresh and campaign switching still load shared entries.
    return text


def patch_spec(text):
    """Ensure the compiled EXE includes the web dashboard assets for 1.0.14."""
    additions = []
    for source, destination in (
        ('dm_dashboard', 'dm_dashboard'),
        ('party_dashboard', 'party_dashboard'),
        ('dashboard_server.py', '.'),
    ):
        # Inspect the source component so similarly named comments do not
        # accidentally hide a missing PyInstaller data-file entry.
        if not re.search(r"\([\s]*['\"]" + re.escape(source) + r"['\"]\s*,", text):
            additions.append(f"        ({source!r}, {destination!r}),")
    if not additions:
        return text
    if '    datas=[' not in text:
        raise RuntimeError('PyInstaller spec has an unfamiliar datas block; dashboard assets cannot be verified.')
    return replace_exact(
        text, '    datas=[',
        '    datas=[\n' + '\n'.join(additions),
        'Embed dashboard resources in PyInstaller spec',
    )


def patch_version(text, kind):
    if kind == 'iss':
        if 'AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}' not in text:
            raise RuntimeError('Inno Setup AppId differs. Refusing to make a potentially incompatible installer.')
        pattern = r'(?m)^(#define MyAppVersion ")(1\.0\.(?:12|13|14))("\s*)$'
    else:
        pattern = r'(?m)^(APP_VERSION\s*=\s*")(1\.0\.(?:12|13|14))(")$'
    output, count = re.subn(pattern, lambda m: m.group(1) + '1.0.14' + m.group(3), text)
    if count != 1:
        raise RuntimeError(f'Cannot locate {kind} version constant (1.0.12 - 1.0.14) exactly once.')
    return output


def main(root):
    modifications = [
        ('campaign_role_ui.py', patch_role),
        ('party_dashboard/index.html', patch_party_html),
        ('party_dashboard/app.js', patch_party_js),
        ('DID_Character_Sheet.spec', patch_spec),
        ('frontend_2_8.py', lambda s: patch_version(s, 'py')),
        ('DID_Character_Sheet_Installer_with_icon.iss', lambda s: patch_version(s, 'iss')),
    ]
    # Precompute every update before touching anything on disk.
    planned = []
    for name, transform in modifications:
        target = root / name
        if not target.is_file():
            raise RuntimeError(f'Required file missing: {target}')
        with target.open('r', encoding='utf-8', newline='') as stream:
            original = stream.read()
        newline = '\r\n' if '\r\n' in original else '\n'
        updated = transform(original.replace('\r\n', '\n'))
        updated = updated.replace('\n', newline)
        if updated != original:
            planned.append((target, original, updated))
    support = root / 'campaign_player_reveals.py'
    supplied = HERE / 'campaign_player_reveals.py'
    if support.exists():
        if support.read_bytes() != supplied.read_bytes():
            raise RuntimeError('campaign_player_reveals.py already exists with different content; review manually.')
    else:
        planned.append((support, None, supplied.read_bytes()))
    if not planned:
        print('DID 1.0.14 campaign patch is already installed. No files changed.')
        return
    backup_dir = root / ('DID_1.0.14_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    backup_dir.mkdir()
    for target, original, updated in planned:
        if original is not None:
            dest = backup_dir / target.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(original.encode('utf-8'))
        payload = updated if isinstance(updated, bytes) else updated.encode('utf-8')
        target.write_bytes(payload)
        print('Updated:', target.relative_to(root))
    print('Original files saved in:', backup_dir)
    print('Windows DID Character Sheet now targets version 1.0.14.')

if __name__ == '__main__':
    try:
        main(Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else HERE)
    except Exception as exc:
        print('STOP: ', exc, file=sys.stderr)
        sys.exit(1)
