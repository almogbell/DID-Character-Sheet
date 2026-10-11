from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_role_ui.py",
    "campaign_party.py",
    "campaign_party_bridge.py",
    "party_dashboard_server.py",
    "campaign_supabase_phase7.sql",
    "test_phase7.py",
)


def find_project_root():
    candidates = [Path.cwd(), Path(__file__).resolve().parent]
    for candidate in list(candidates):
        candidates.extend(candidate.parents[:4])
    seen = set()
    for root in candidates:
        root = root.resolve()
        if root in seen:
            continue
        seen.add(root)
        if (
            (root / "frontend_2_8.py").is_file()
            and (root / "campaign_ui.py").is_file()
            and (root / "campaign_runtime.py").is_file()
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root
    raise FileNotFoundError(
        "Could not find the current DID project. Put the phase7 folder inside "
        "your current code folder and run this installer from there."
    )


def backup_once(path: Path, suffix=".before_phase7"):
    backup = path.with_name(path.name + suffix)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
        return backup
    return None


def copy_if_needed(source: Path, target: Path):
    if source.resolve() == target.resolve():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() == source.read_bytes():
        return False
    shutil.copy2(source, target)
    return True


def patch_frontend(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    import_line = "from campaign_ui import open_campaign_manager\n"
    role_import = "from campaign_role_ui import open_player_campaigns\n"
    if role_import not in text:
        if import_line not in text:
            raise RuntimeError("Could not find the Campaign UI import in frontend_2_8.py")
        text = text.replace(import_line, import_line + role_import, 1)

    old = '''        campaign_action = campaign_menu.addAction(
            "Campaign..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaign_manager(self)
        )

        campaign_menu.addSeparator()
'''
    new = '''        campaign_action = campaign_menu.addAction(
            "Campaign Manager..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaign_manager(self)
        )

        player_campaign_action = campaign_menu.addAction(
            "My Campaigns..."
        )
        player_campaign_action.triggered.connect(
            lambda _checked=False: open_player_campaigns(self)
        )

        campaign_menu.addSeparator()
'''
    if new not in text:
        if old not in text:
            # A few local copies may already have the label changed. Patch the
            # same callback block without relying on the old label.
            old_alt = old.replace('"Campaign..."', '"Campaign Manager..."')
            if old_alt not in text:
                raise RuntimeError("Could not safely locate the Campaign menu block.")
            text = text.replace(old_alt, new, 1)
        else:
            text = text.replace(old, new, 1)

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_campaign_ui_delegate(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original
    old = '''def open_campaign_manager(window):
    dialog = CampaignManagerDialog(window)
    dialog.exec()
    return dialog
'''
    new = '''def open_campaign_manager(window):
    # Phase 7 separates DM campaign management from the player experience.
    from campaign_role_ui import open_dm_campaign_manager
    return open_dm_campaign_manager(window)
'''
    if new not in text:
        if old not in text:
            raise RuntimeError("Could not safely locate open_campaign_manager in campaign_ui.py")
        text = text.replace(old, new, 1)
    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_privacy_model(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    # There is no Backstory field in the actual sheet.  Stop advertising or
    # serializing a category that the application does not own.
    text = text.replace('    "share_backstory": False,\n', "")
    text = text.replace('            "share_backstory",\n', "")
    text = text.replace('        "backstory": bool(prefs["share_backstory"]),\n', "")
    block = '''    if prefs["share_backstory"]:
        state["backstory"] = str(data.get("backstory") or "")[:100000]
    else:
        state.pop("backstory", None)

'''
    text = text.replace(block, "")
    text = text.replace('    if prefs["share_backstory"]:\n        parts.append("Backstory")\n', "")

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_runtime_for_party(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    import_line = "from campaign_privacy import build_window_shared_state\n"
    party_import = "from campaign_party import build_window_party_state, upload_party_state\n"
    if party_import not in text:
        if import_line not in text:
            raise RuntimeError(
                "Phase 6 privacy runtime hook is missing. Run the Phase 6 installer first."
            )
        text = text.replace(import_line, import_line + party_import, 1)

    old_state = '''    try:
        state = build_window_shared_state(window, link=link)
    except Exception as error:
'''
    new_state = '''    try:
        state = build_window_shared_state(window, link=link)
        party_state = build_window_party_state(window, link=link)
    except Exception as error:
'''
    if new_state not in text:
        if old_state not in text:
            raise RuntimeError("Could not find the Phase 6 state builder in campaign_runtime.py")
        text = text.replace(old_state, new_state, 1)

    old_upload = '''            client.upload_character_state(campaign_character_id, state)
            window._campaign_sync_status = "Synced"
'''
    new_upload = '''            client.upload_character_state(campaign_character_id, state)
            try:
                upload_party_state(
                    client,
                    link.get("campaign_id"),
                    campaign_character_id,
                    party_state,
                )
            except Exception:
                # Party sharing is supplemental. A removed/inactive character
                # must not break the ordinary DM-safe character sync.
                pass
            window._campaign_sync_status = "Synced"
'''
    if new_upload not in text:
        if old_upload not in text:
            raise RuntimeError("Could not find the campaign state upload in campaign_runtime.py")
        text = text.replace(old_upload, new_upload, 1)

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_dm_dashboard_app(path: Path):
    original = path.read_text(encoding="utf-8")
    text = original

    if "function sanitizeRichNoteHtml" not in text:
        needle = '''  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

'''
        helper = needle + '''  function sanitizeRichNoteHtml(value) {
    const raw = String(value || "");
    if (!raw) return "";
    const doc = new DOMParser().parseFromString(`<div>${raw}</div>`, "text/html");
    const root = doc.body.firstElementChild;
    if (!root) return escapeHtml(raw);
    const allowed = new Set(["B", "STRONG", "I", "EM", "U", "BR", "P", "DIV", "UL", "OL", "LI", "SPAN"]);
    const walk = node => {
      for (const child of [...node.children]) {
        if (!allowed.has(child.tagName)) {
          child.replaceWith(...child.childNodes);
          continue;
        }
        [...child.attributes].forEach(attr => child.removeAttribute(attr.name));
        walk(child);
      }
    };
    walk(root);
    return root.innerHTML;
  }

'''
        if needle not in text:
            raise RuntimeError("Could not locate escapeHtml in DM dashboard app.js")
        text = text.replace(needle, helper, 1)

    # Render the note's safe formatting instead of showing literal <b>/<br>.
    text = text.replace(
        '<div>${escapeHtml(note.text || "")}</div>',
        '<div class="note-rich-text">${sanitizeRichNoteHtml(note.text || "")}</div>',
    )

    # Remove the nonexistent Backstory category from the old Phase 6 renderer.
    start = text.find('    if (sharing.backstory === true) {')
    if start >= 0:
        end = text.find('    if (sharing.inventory === true) {', start)
        if end > start:
            text = text[:start] + text[end:]
    text = text.replace('    if (sharing.backstory) labels.push("Backstory");\n', "")

    # Dashboard terminology is HP, not Hearts.  HP is stored internally in
    # quarter-heart units, so max HP is max_hearts * 4.
    if "const maxHp = maxHearts * 4;" not in text:
        text = text.replace(
            "    const maxHearts = Math.max(0, Number(hearts.max) || 0);\n",
            "    const maxHearts = Math.max(0, Number(hearts.max) || 0);\n    const maxHp = maxHearts * 4;\n",
            1,
        )
        text = text.replace("      maxHearts,\n", "      maxHearts,\n      maxHp,\n", 1)

    text = text.replace('<div class="resource-label">Hearts</div>', '<div class="resource-label">HP</div>')
    text = text.replace('♥ ${escapeHtml(formatQuarterHearts(metrics.currentHp))} / ${metrics.maxHearts}', '${metrics.currentHp} / ${metrics.maxHp}')
    text = text.replace('escapeHtml(formatQuarterHearts(metrics.currentHp))} / ${metrics.maxHearts}', 'metrics.currentHp} / ${metrics.maxHp}')
    text = text.replace('percent(metrics.currentHp, heartMaxHp)', 'percent(metrics.currentHp, metrics.maxHp)')

    # Match the character sheet's ability identity colors.
    text = text.replace('class="ability">\n          <div class="ability-name">${escapeHtml(ability.name)}</div>', 'class="ability ${escapeHtml(ability.name)}">\n          <div class="ability-name">${escapeHtml(ability.name)}</div>')
    text = text.replace('class="ability"><div class="ability-name">${escapeHtml(a.name)}</div>', 'class="ability ${escapeHtml(a.name)}"><div class="ability-name">${escapeHtml(a.name)}</div>')

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_dm_dashboard_css(path: Path):
    original = path.read_text(encoding="utf-8")
    if "Phase 7 — HP and ability identity colors" in original:
        return False
    addition = '''

/* Phase 7 — HP and ability identity colors */
.resource-box.hp, .detail-block.hp { border-color:#c98882; background:#fff6f3; }
.ability.agility { border-color:#b8c78f; background:#f7faee; }
.ability.strength { border-color:#d8aaa4; background:#fff5f3; }
.ability.finesse { border-color:#a9c7e3; background:#f3f8fd; }
.ability.instinct { border-color:#c0b2dc; background:#f8f5fc; }
.ability.presence { border-color:#a9d0d4; background:#f2fafa; }
.ability.knowledge { border-color:#d9bf91; background:#fcf7ed; }
.note-rich-text { white-space: normal; line-height: 1.45; }
'''
    backup_once(path)
    path.write_text(original.rstrip() + addition + "\n", encoding="utf-8")
    return True


def main():
    root = find_project_root()
    support = Path(__file__).resolve().parent
    missing = [name for name in REQUIRED_FILES if not (support / name).is_file()]
    for asset in ("index.html", "app.js", "styles.css"):
        if not (support / "party_dashboard" / asset).is_file():
            missing.append(f"party_dashboard/{asset}")
    if missing:
        raise FileNotFoundError("Keep the Phase 7 files together. Missing: " + ", ".join(missing))

    print(f"Project:  {root}")
    print("Installing Phase 7: DM / Player split + Party Dashboard...")

    for name in REQUIRED_FILES:
        copy_if_needed(support / name, root / name)
    party_target = root / "party_dashboard"
    party_target.mkdir(parents=True, exist_ok=True)
    for asset in ("index.html", "app.js", "styles.css"):
        copy_if_needed(support / "party_dashboard" / asset, party_target / asset)

    frontend_changed = patch_frontend(root / "frontend_2_8.py")
    delegate_changed = patch_campaign_ui_delegate(root / "campaign_ui.py")
    privacy_changed = patch_privacy_model(root / "campaign_privacy.py")
    runtime_changed = patch_runtime_for_party(root / "campaign_runtime.py")
    dashboard_changed = patch_dm_dashboard_app(root / "dm_dashboard" / "app.js")
    dashboard_css_changed = patch_dm_dashboard_css(root / "dm_dashboard" / "styles.css")

    for path in (
        root / "frontend_2_8.py",
        root / "campaign_ui.py",
        root / "campaign_runtime.py",
        root / "campaign_privacy.py",
        root / "campaign_role_ui.py",
        root / "campaign_party.py",
        root / "campaign_party_bridge.py",
        root / "party_dashboard_server.py",
        root / "test_phase7.py",
    ):
        py_compile.compile(str(path), doraise=True)
    print("Compile: PASS")

    completed = subprocess.run(
        [sys.executable, str(root / "test_phase7.py")],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    print("\nPhase 7 local tests: PASS")
    print(f"Frontend menu split: {'PASS' if frontend_changed else 'already installed'}")
    print(f"DM manager delegate: {'PASS' if delegate_changed else 'already installed'}")
    print(f"Backstory removed: {'PASS' if privacy_changed else 'already installed'}")
    print(f"Party live-state sync: {'PASS' if runtime_changed else 'already installed'}")
    print(f"DM Dashboard rich notes + HP: {'PASS' if dashboard_changed else 'already installed'}")
    print(f"DM Dashboard colors: {'PASS' if dashboard_css_changed else 'already installed'}")
    print("\nNEXT:")
    print("1. Run campaign_supabase_phase7.sql in Supabase SQL Editor.")
    print("2. Restart: python frontend_2_8.py")
    print("3. Tools -> Campaign & Templates -> Campaign Manager... (DM)")
    print("4. Tools -> Campaign & Templates -> My Campaigns... (player)")
    print("5. Test Open Party Dashboard from a joined player campaign.")


if __name__ == "__main__":
    main()
