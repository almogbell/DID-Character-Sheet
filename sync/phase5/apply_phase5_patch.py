from __future__ import annotations

import py_compile
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_FILES = (
    "campaign_session.py",
    "campaign_supabase_phase5.sql",
    "test_campaign_session.py",
    "campaign_session_smoke_test.py",
)

WIDGET_IMPORT_NEEDLE = "    QComboBox,\n    QDialog,\n"
WIDGET_IMPORT_REPLACEMENT = "    QCheckBox,\n    QComboBox,\n    QDialog,\n"

SESSION_IMPORT_NEEDLE = "from campaign_runtime import (\n"
SESSION_IMPORT_REPLACEMENT = (
    "from campaign_session import CampaignSessionService\n"
    + SESSION_IMPORT_NEEDLE
)

SERVICE_NEEDLE = (
    "        self.client = campaign_client(window)\n"
    "        self.service = CampaignTemplateService(self.client) if self.client else None\n"
)
SERVICE_REPLACEMENT = (
    SERVICE_NEEDLE
    + "        self.session_service = CampaignSessionService(self.client) if self.client else None\n"
)

CHECKBOX_NEEDLE = (
    "        self.sync_label = QLabel(\"\")\n"
    "        root.addWidget(self.sync_label)\n"
    "\n"
    "        first_row = QHBoxLayout()\n"
)
CHECKBOX_REPLACEMENT = (
    "        self.sync_label = QLabel(\"\")\n"
    "        root.addWidget(self.sync_label)\n"
    "\n"
    "        self.roll_share_checkbox = QCheckBox(\n"
    "            \"Share my dice rolls during active sessions\"\n"
    "        )\n"
    "        self.roll_share_checkbox.setToolTip(\n"
    "            \"When off, rolls made while a campaign session is active are not \"\n"
    "            \"stored in the DM session log. Rolls outside sessions are unchanged.\"\n"
    "        )\n"
    "        self.roll_share_checkbox.setVisible(False)\n"
    "        self.roll_share_checkbox.toggled.connect(\n"
    "            self._session_roll_sharing_changed\n"
    "        )\n"
    "        root.addWidget(self.roll_share_checkbox)\n"
    "\n"
    "        first_row = QHBoxLayout()\n"
)

UPDATE_BUTTONS_NEEDLE = (
    "        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))\n"
)
UPDATE_BUTTONS_REPLACEMENT = (
    UPDATE_BUTTONS_NEEDLE
    + "        self._refresh_roll_share_checkbox()\n"
)

METHOD_NEEDLE = "    def open_dm_dashboard(self):\n"
METHOD_REPLACEMENT = '''    def _current_campaign_character_link(self):
        if self.client is None or not isinstance(self.current_campaign, dict):
            return None

        character_id = str(
            getattr(self.window.character, "id", "") or ""
        ).strip()
        if not character_id:
            return None

        try:
            link = self.client.get_character_link(character_id)
        except Exception:
            return None

        if not isinstance(link, dict):
            return None

        if str(link.get("campaign_id") or "") != str(
            self.current_campaign.get("id") or ""
        ):
            return None

        return link

    def _refresh_roll_share_checkbox(self):
        checkbox = getattr(self, "roll_share_checkbox", None)
        if checkbox is None:
            return

        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or self.session_service is None:
            checkbox.blockSignals(True)
            checkbox.setVisible(False)
            checkbox.blockSignals(False)
            return

        campaign_character_id = str(
            link.get("campaign_character_id") or ""
        ).strip()
        if not campaign_character_id:
            checkbox.setVisible(False)
            return

        checked = True
        try:
            checked = self.session_service.get_roll_sharing(
                campaign_character_id
            )
        except Exception:
            checked = True

        checkbox.blockSignals(True)
        checkbox.setChecked(bool(checked))
        checkbox.setVisible(True)
        checkbox.setEnabled(True)
        checkbox.blockSignals(False)

    def _session_roll_sharing_changed(self, enabled):
        link = self._current_campaign_character_link()
        if not isinstance(link, dict) or self.session_service is None:
            return

        campaign_character_id = str(
            link.get("campaign_character_id") or ""
        ).strip()
        if not campaign_character_id:
            return

        try:
            self.session_service.set_roll_sharing(
                campaign_character_id,
                bool(enabled),
            )
        except Exception as error:
            self._show_error("Update Roll Sharing Failed", error)
            self._refresh_roll_share_checkbox()

    def open_dm_dashboard(self):
'''


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
            and (root / "campaign_dashboard_bridge.py").is_file()
            and (root / "dashboard_server.py").is_file()
            and (root / "dm_dashboard" / "app.js").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 4 DID project. Copy the Phase 5 files into "
        "your current code folder and run this script there."
    )


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Could not safely patch {label}: expected exactly one matching block, found {count}."
        )
    return text.replace(needle, replacement, 1)


def copy_if_needed(source, target):
    if source.resolve() == target.resolve():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def backup_once(path, suffix=".before_phase5"):
    backup = path.with_name(path.name + suffix)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
        return backup
    return None


def main():
    root = find_project_root()
    support_dir = Path(__file__).resolve().parent

    missing = [name for name in REQUIRED_FILES if not (support_dir / name).is_file()]
    for asset in ("index.html", "app.js", "styles.css"):
        if not (support_dir / "dm_dashboard" / asset).is_file():
            missing.append(f"dm_dashboard/{asset}")
    if missing:
        raise FileNotFoundError(
            "Keep all Phase 5 files together before running the patcher. Missing: "
            + ", ".join(missing)
        )

    campaign_ui = root / "campaign_ui.py"
    original = campaign_ui.read_text(encoding="utf-8")
    text = original

    print(f"Project:  {root}")
    print("Installing Phase 5: Session Mode...")

    if "QCheckBox," not in text:
        text = replace_once(
            text,
            WIDGET_IMPORT_NEEDLE,
            WIDGET_IMPORT_REPLACEMENT,
            "QCheckBox import",
        )

    if "from campaign_session import CampaignSessionService" not in text:
        text = replace_once(
            text,
            SESSION_IMPORT_NEEDLE,
            SESSION_IMPORT_REPLACEMENT,
            "CampaignSessionService import",
        )

    if "self.session_service = CampaignSessionService" not in text:
        text = replace_once(
            text,
            SERVICE_NEEDLE,
            SERVICE_REPLACEMENT,
            "session service initialization",
        )

    if 'QCheckBox(\n            "Share my dice rolls during active sessions"' not in text:
        text = replace_once(
            text,
            CHECKBOX_NEEDLE,
            CHECKBOX_REPLACEMENT,
            "session roll-sharing checkbox",
        )

    if "def _current_campaign_character_link" not in text:
        text = replace_once(
            text,
            METHOD_NEEDLE,
            METHOD_REPLACEMENT,
            "session roll-sharing methods",
        )

    if "self._refresh_roll_share_checkbox()" not in text:
        text = replace_once(
            text,
            UPDATE_BUTTONS_NEEDLE,
            UPDATE_BUTTONS_REPLACEMENT,
            "roll-sharing checkbox refresh",
        )

    if text != original:
        backup = backup_once(campaign_ui)
        if backup:
            print(f"Backup:   {backup.name}")
        campaign_ui.write_text(text, encoding="utf-8")

    copy_if_needed(support_dir / "campaign_session.py", root / "campaign_session.py")
    copy_if_needed(
        support_dir / "campaign_supabase_phase5.sql",
        root / "campaign_supabase_phase5.sql",
    )
    copy_if_needed(
        support_dir / "campaign_session_smoke_test.py",
        root / "campaign_session_smoke_test.py",
    )
    copy_if_needed(
        support_dir / "test_campaign_session.py",
        root / "test_campaign_session.py",
    )

    dashboard_target = root / "dm_dashboard"
    dashboard_target.mkdir(parents=True, exist_ok=True)
    for asset in ("index.html", "app.js", "styles.css"):
        target = dashboard_target / asset
        backup_once(target)
        copy_if_needed(support_dir / "dm_dashboard" / asset, target)

    for path in (
        campaign_ui,
        root / "campaign_session.py",
        root / "test_campaign_session.py",
        root / "campaign_session_smoke_test.py",
    ):
        py_compile.compile(str(path), doraise=True)
    print("Compile:  PASS")

    completed = subprocess.run(
        [sys.executable, str(root / "test_campaign_session.py")],
        cwd=str(root),
        text=True,
        capture_output=True,
    )
    print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="")
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)

    print("\nPhase 5 local tests: PASS")
    print("\nNEXT:")
    print("1. Run campaign_supabase_phase5.sql in your Supabase SQL Editor.")
    print("2. Run: python campaign_session_smoke_test.py")
    print("3. After PASS, launch: python frontend_2_8.py")
    print("4. Open the DM Dashboard and test Start Session / End Session.")
    print("5. In a player Campaign window, toggle session roll sharing and roll a die.")


if __name__ == "__main__":
    main()
