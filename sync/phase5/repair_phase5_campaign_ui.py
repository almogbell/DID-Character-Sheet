from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


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
        if (root / "frontend_2_8.py").is_file() and (root / "campaign_ui.py").is_file():
            return root
    raise FileNotFoundError("Could not find the DID project folder.")


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        raise RuntimeError(
            f"Could not safely repair {label}: expected exactly one matching block, found {count}."
        )
    return text.replace(needle, replacement, 1)


def main():
    root = find_project_root()
    support_dir = Path(__file__).resolve().parent

    # The UI imports CampaignSessionService. If the original Phase 5 installer
    # stopped before copying support files, repair that first so the app can
    # import campaign_ui.py again.
    session_source = support_dir / "campaign_session.py"
    session_target = root / "campaign_session.py"
    if not session_target.is_file():
        if not session_source.is_file():
            raise FileNotFoundError(
                "campaign_session.py is missing from the Phase 5 folder. "
                "Download the latest Phase 5 ZIP again."
            )
        shutil.copy2(session_source, session_target)
        print("campaign_session.py restored.")

    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original

    # Import QCheckBox if Phase 5 did not install it.
    if "    QCheckBox,\n" not in text:
        text = replace_once(
            text,
            "    QComboBox,\n    QDialog,\n",
            "    QCheckBox,\n    QComboBox,\n    QDialog,\n",
            "QCheckBox import",
        )

    # Import the session service.
    if "from campaign_session import CampaignSessionService\n" not in text:
        text = replace_once(
            text,
            "from campaign_runtime import (\n",
            "from campaign_session import CampaignSessionService\nfrom campaign_runtime import (\n",
            "CampaignSessionService import",
        )

    # Create the service on the Campaign dialog.
    service_line = "        self.service = CampaignTemplateService(self.client) if self.client else None\n"
    session_line = "        self.session_service = CampaignSessionService(self.client) if self.client else None\n"
    if session_line not in text:
        text = replace_once(
            text,
            service_line,
            service_line + session_line,
            "CampaignSessionService initialization",
        )

    # Insert the visible checkbox exactly below the sync-status label.
    checkbox_marker = '"Share my dice rolls during active sessions"'
    if checkbox_marker not in text:
        needle = (
            "        self.sync_label = QLabel(\"\")\n"
            "        root.addWidget(self.sync_label)\n"
            "\n"
            "        first_row = QHBoxLayout()\n"
        )
        replacement = (
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
        text = replace_once(text, needle, replacement, "roll-sharing checkbox")

    # Add the helper methods if missing.
    if "    def _current_campaign_character_link(self):\n" not in text:
        method_needle = "    def open_dm_dashboard(self):\n"
        methods = '''    def _current_campaign_character_link(self):
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
            checked = self.session_service.get_roll_sharing(campaign_character_id)
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
        text = replace_once(text, method_needle, methods, "session roll-sharing methods")

    refresh_line = "        self.unlink_btn.setEnabled(bool(restore_campaign_connection(self.window)))\n"
    refresh_call = "        self._refresh_roll_share_checkbox()\n"
    if refresh_line + refresh_call not in text:
        text = replace_once(
            text,
            refresh_line,
            refresh_line + refresh_call,
            "checkbox refresh",
        )

    if text != original:
        backup = path.with_name(path.name + ".before_phase5_checkbox_repair")
        if not backup.exists():
            shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        print("campaign_ui.py repaired.")
    else:
        print("campaign_ui.py already contains the Phase 5 checkbox code.")

    py_compile.compile(str(session_target), doraise=True)
    py_compile.compile(str(path), doraise=True)
    print("Compile: PASS")
    print("Close every running DID window, then restart frontend_2_8.py.")


if __name__ == "__main__":
    main()
