from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_privacy.py",
    "campaign_privacy_ui.py",
    "test_campaign_privacy.py",
    "campaign_privacy_smoke_test.py",
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
            and (root / "campaign_session.py").is_file()
            and (root / "dm_dashboard" / "app.js").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 5 DID project. Copy the Phase 6 folder into "
        "your current code folder and run this installer from there."
    )


def backup_once(path, suffix=".before_phase6"):
    backup = path.with_name(path.name + suffix)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
        return backup
    return None


def copy_if_needed(source, target):
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: expected exactly one matching block, found {count}."
        )
    return text.replace(needle, replacement, 1)


def patch_campaign_runtime(path):
    original = path.read_text(encoding="utf-8")
    text = original

    if "from campaign_privacy import build_window_shared_state" not in text:
        needle = "from campaign_cloud import CampaignCloudClient, CampaignCloudError\n"
        replacement = needle + "from campaign_privacy import build_window_shared_state\n"
        text = replace_once(text, needle, replacement, "campaign runtime privacy import")

    old_state = "        state = window.build_dm_shared_character_state()\n"
    new_state = "        state = build_window_shared_state(window, link=link)\n"
    if new_state not in text:
        text = replace_once(
            text,
            old_state,
            new_state,
            "privacy-filtered automatic state sync",
        )

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_campaign_ui(path):
    original = path.read_text(encoding="utf-8")
    text = original

    privacy_import = '''from campaign_privacy import (
    build_window_shared_state,
    privacy_store_for_window,
    sharing_summary,
)
from campaign_privacy_ui import open_sharing_privacy_dialog
'''
    if "from campaign_privacy import (" not in text:
        if "from campaign_session import CampaignSessionService\n" in text:
            needle = "from campaign_session import CampaignSessionService\n"
            text = replace_once(
                text,
                needle,
                needle + privacy_import,
                "campaign UI privacy imports",
            )
        else:
            needle = "from campaign_runtime import (\n"
            text = replace_once(
                text,
                needle,
                privacy_import + needle,
                "campaign UI privacy imports",
            )

    store_line = "        self.privacy_store = privacy_store_for_window(window)\n"
    if store_line not in text:
        session_line = (
            "        self.session_service = CampaignSessionService(self.client) if self.client else None\n"
        )
        if session_line in text:
            text = replace_once(
                text,
                session_line,
                session_line + store_line,
                "privacy store initialization",
            )
        else:
            service_line = "        self.service = CampaignTemplateService(self.client) if self.client else None\n"
            text = replace_once(
                text,
                service_line,
                service_line + store_line,
                "privacy store initialization",
            )

    if 'QPushButton("Sharing & Privacy...")' not in text:
        needle = "        root.addWidget(self.roll_share_checkbox)\n\n        first_row = QHBoxLayout()\n"
        replacement = '''        root.addWidget(self.roll_share_checkbox)

        privacy_row = QHBoxLayout()
        self.privacy_summary_label = QLabel("")
        self.privacy_summary_label.setWordWrap(True)
        self.privacy_summary_label.setStyleSheet(
            "color:#7c6a52; font-family:Georgia; font-size:11px;"
        )
        self.privacy_btn = QPushButton("Sharing & Privacy...")
        self.privacy_btn.clicked.connect(self.open_sharing_privacy)
        privacy_row.addWidget(self.privacy_summary_label, 1)
        privacy_row.addWidget(self.privacy_btn)
        root.addLayout(privacy_row)

        first_row = QHBoxLayout()
'''
        text = replace_once(text, needle, replacement, "Sharing & Privacy controls")

    update_block = (
        "        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))\n"
        "        self._refresh_roll_share_checkbox()\n"
    )
    if "        self._refresh_privacy_controls()\n" not in text:
        text = replace_once(
            text,
            update_block,
            update_block + "        self._refresh_privacy_controls()\n",
            "privacy controls refresh",
        )

    if "    def _refresh_privacy_controls(self):\n" not in text:
        needle = "    def open_dm_dashboard(self):\n"
        methods = '''    def _refresh_privacy_controls(self):
        button = getattr(self, "privacy_btn", None)
        label = getattr(self, "privacy_summary_label", None)
        if button is None or label is None:
            return

        link = self._current_campaign_character_link()
        visible = isinstance(link, dict) and isinstance(self.current_campaign, dict)
        button.setVisible(visible)
        label.setVisible(visible)
        if not visible:
            label.setText("")
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        preferences = self.privacy_store.get(campaign_id, character_id)
        label.setText(sharing_summary(preferences))

    def open_sharing_privacy(self):
        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or not isinstance(self.current_campaign, dict):
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        if not campaign_id or not character_id:
            return

        current = self.privacy_store.get(campaign_id, character_id)
        updated = open_sharing_privacy_dialog(
            self,
            self.window.character,
            current,
        )
        if updated is None:
            return

        try:
            self.privacy_store.set(campaign_id, character_id, updated)
            sync_current_character_now(self.window)
        except Exception as error:
            self._show_error("Update Sharing & Privacy Failed", error)
            return

        self._refresh_privacy_controls()

    def open_dm_dashboard(self):
'''
        text = replace_once(text, needle, methods, "Sharing & Privacy methods")

    old_initial_state = "            state = self.window.build_dm_shared_character_state()\n"
    new_initial_state = (
        "            state = build_window_shared_state(\n"
        "                self.window,\n"
        "                campaign_id=self.current_campaign[\"id\"],\n"
        "            )\n"
    )
    if new_initial_state not in text:
        text = replace_once(
            text,
            old_initial_state,
            new_initial_state,
            "privacy-filtered initial character share",
        )

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_dashboard_app(path):
    original = path.read_text(encoding="utf-8")
    text = original

    helper_marker = "  function portraitSource(state) {\n"
    if helper_marker not in text:
        needle = '''  function initials(name) {
    const words = String(name || "?").trim().split(/\\s+/).filter(Boolean);
    if (!words.length) return "?";
    return words.slice(0, 2).map(word => word[0].toUpperCase()).join("");
  }

'''
        helpers = needle + '''  function portraitSource(state) {
    const portrait = state && state.portrait && typeof state.portrait === "object"
      ? state.portrait
      : {};
    if (!portrait.shared || !portrait.data) return "";
    const raw = String(portrait.data || "").trim();
    if (!raw) return "";
    if (raw.startsWith("data:image/")) return raw;
    if (/^[A-Za-z0-9+/=\\s]+$/.test(raw)) {
      return `data:image/png;base64,${raw.replace(/\\s+/g, "")}`;
    }
    return "";
  }

  function renderAvatar(state, name) {
    const source = portraitSource(state);
    if (!source) {
      return `<div class="avatar">${escapeHtml(initials(name))}</div>`;
    }
    return `<div class="avatar portrait-avatar"><img src="${escapeHtml(source)}" alt=""></div>`;
  }

  function sharedExtrasHtml(state) {
    state = state || {};
    const sharing = state.sharing && typeof state.sharing === "object" ? state.sharing : {};
    const sections = [];

    if (sharing.backstory === true) {
      const text = String(state.backstory || "").trim();
      sections.push(`
        <section class="shared-section">
          <h3>Backstory</h3>
          <div class="shared-text">${text ? escapeHtml(text) : "No backstory entered."}</div>
        </section>`);
    }

    if (sharing.inventory === true) {
      const items = Array.isArray(state.inventory) ? state.inventory : [];
      const body = items.length
        ? `<ul class="shared-list">${items.map(item => {
            const quantity = Number(item.quantity) || 0;
            const qty = quantity !== 1 ? ` ×${quantity}` : "";
            const description = String(item.description || "").trim();
            return `<li><b>${escapeHtml(item.name || "Item")}${escapeHtml(qty)}</b>${description ? `<div>${escapeHtml(description)}</div>` : ""}</li>`;
          }).join("")}</ul>`
        : '<div class="shared-empty">No inventory items selected for sharing.</div>';
      sections.push(`<section class="shared-section"><h3>Shared Inventory</h3>${body}</section>`);
    }

    if (sharing.notes === true) {
      const notes = Array.isArray(state.notes) ? state.notes : [];
      const body = notes.length
        ? `<div class="shared-notes">${notes.map(note => `
            <article class="shared-note">
              <h4>${escapeHtml(note.title || "Untitled note")}</h4>
              <div>${escapeHtml(note.text || "")}</div>
            </article>`).join("")}</div>`
        : '<div class="shared-empty">No notes selected for sharing.</div>';
      sections.push(`<section class="shared-section"><h3>Shared Notes</h3>${body}</section>`);
    }

    if (!state.sharing) return sections.join("");
    const labels = ["Core"];
    if (sharing.improvements) labels.push("Improvements");
    if (sharing.portrait) labels.push("Portrait");
    if (sharing.backstory) labels.push("Backstory");
    if (sharing.inventory) labels.push("Inventory");
    if (sharing.notes) labels.push("Notes");
    sections.push(`<div class="sharing-footnote">Player sharing: ${escapeHtml(labels.join(" • "))}</div>`);
    return sections.join("");
  }

'''
        text = replace_once(text, needle, helpers, "dashboard privacy helpers")

    old_portrait_note = (
        '      const portraitNote = state.portrait && state.portrait.available ? " • portrait on sheet" : "";\n'
    )
    new_portrait_note = (
        '      const portraitNote = state.portrait && state.portrait.shared && state.portrait.available ? " • portrait shared" : "";\n'
    )
    if new_portrait_note not in text:
        text = replace_once(
            text,
            old_portrait_note,
            new_portrait_note,
            "dashboard portrait privacy label",
        )

    old_avatar = '            <div class="avatar">${escapeHtml(initials(name))}</div>\n'
    new_avatar = '            ${renderAvatar(state, name)}\n'
    if new_avatar not in text:
        text = replace_once(text, old_avatar, new_avatar, "dashboard shared portrait")

    old_improvements = '''    const improvements = Array.isArray(state.improvements) ? state.improvements : [];

    const improvementsHtml = improvements.length
      ? `<ul class="improvement-list">${improvements.map(item => {
          const times = Number(item.times_taken) > 1 ? ` ×${Number(item.times_taken)}` : "";
          return `<li>${escapeHtml(item.name || item.catalog_id || "Improvement")}${escapeHtml(times)}</li>`;
        }).join("")}</ul>`
      : "<p>No shared Improvements.</p>";
'''
    new_improvements = '''    const improvements = Array.isArray(state.improvements) ? state.improvements : [];
    const sharing = state.sharing && typeof state.sharing === "object" ? state.sharing : null;
    const improvementsShared = sharing ? sharing.improvements === true : true;

    const improvementsHtml = !improvementsShared
      ? '<p class="shared-empty">Not shared by this player.</p>'
      : improvements.length
        ? `<ul class="improvement-list">${improvements.map(item => {
            const times = Number(item.times_taken) > 1 ? ` ×${Number(item.times_taken)}` : "";
            return `<li>${escapeHtml(item.name || item.catalog_id || "Improvement")}${escapeHtml(times)}</li>`;
          }).join("")}</ul>`
        : "<p>No shared Improvements.</p>";
'''
    if new_improvements not in text:
        text = replace_once(
            text,
            old_improvements,
            new_improvements,
            "dashboard Improvements privacy",
        )

    old_end = '''      <h3 style="margin-top:18px">Improvements</h3>
      ${improvementsHtml}
    `;
'''
    new_end = '''      <h3 style="margin-top:18px">Improvements</h3>
      ${improvementsHtml}
      ${sharedExtrasHtml(state)}
    `;
'''
    if new_end not in text:
        text = replace_once(text, old_end, new_end, "dashboard optional shared sections")

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_dashboard_styles(path):
    original = path.read_text(encoding="utf-8")
    if ".portrait-avatar img" in original:
        return False

    addition = '''

/* Phase 6 — player-controlled optional sharing */
.portrait-avatar { overflow: hidden; padding: 0; }
.portrait-avatar img { width: 100%; height: 100%; object-fit: cover; display: block; }
.shared-section { margin-top: 18px; padding-top: 14px; border-top: 1px solid #e0cfaa; }
.shared-section h3 { margin-bottom: 8px; }
.shared-text { white-space: pre-wrap; line-height: 1.45; color: var(--ink); }
.shared-list { margin: 0; padding-left: 20px; }
.shared-list li { margin-bottom: 8px; }
.shared-list li div { margin-top: 2px; color: var(--muted); white-space: pre-wrap; }
.shared-notes { display: grid; gap: 8px; }
.shared-note { border: 1px solid #dfcca5; border-radius: 10px; padding: 9px; background: #fffdf7; }
.shared-note h4 { margin: 0 0 5px; }
.shared-note div { white-space: pre-wrap; line-height: 1.4; }
.shared-empty { color: var(--muted); font-style: italic; }
.sharing-footnote { margin-top: 18px; color: var(--muted); font-size: 11px; }
'''
    backup_once(path)
    path.write_text(original.rstrip() + addition + "\n", encoding="utf-8")
    return True


def main():
    root = find_project_root()
    support_dir = Path(__file__).resolve().parent

    missing = [name for name in REQUIRED_FILES if not (support_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            "Keep all Phase 6 files together before running the installer. Missing: "
            + ", ".join(missing)
        )

    print(f"Project:  {root}")
    print("Installing Phase 6: Privacy & Sharing Controls...")

    for name in REQUIRED_FILES:
        copy_if_needed(support_dir / name, root / name)

    runtime_changed = patch_campaign_runtime(root / "campaign_runtime.py")
    ui_changed = patch_campaign_ui(root / "campaign_ui.py")
    app_changed = patch_dashboard_app(root / "dm_dashboard" / "app.js")
    css_changed = patch_dashboard_styles(root / "dm_dashboard" / "styles.css")

    for path in (
        root / "campaign_runtime.py",
        root / "campaign_ui.py",
        root / "campaign_privacy.py",
        root / "campaign_privacy_ui.py",
        root / "test_campaign_privacy.py",
        root / "campaign_privacy_smoke_test.py",
    ):
        py_compile.compile(str(path), doraise=True)
    print("Compile:  PASS")

    completed = subprocess.run(
        [sys.executable, str(root / "test_campaign_privacy.py")],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    print("\nPhase 6 local tests: PASS")
    print(
        "Patched: "
        f"runtime={'yes' if runtime_changed else 'already'}, "
        f"campaign UI={'yes' if ui_changed else 'already'}, "
        f"dashboard={'yes' if app_changed else 'already'}, "
        f"styles={'yes' if css_changed else 'already'}"
    )
    print("\nNo Supabase SQL migration is required for Phase 6.")
    print("NEXT:")
    print("1. Run: python campaign_privacy_smoke_test.py")
    print("2. After PASS, launch: python frontend_2_8.py")
    print("3. Campaign... -> Sharing & Privacy... on a linked character")
    print("4. Change sharing choices and verify the DM dashboard updates.")


if __name__ == "__main__":
    main()
