from __future__ import annotations

import py_compile
import shutil
from pathlib import Path


HELPER_METHODS = [
    (
        "_current_campaign_character_link",
        r'''    def _current_campaign_character_link(self):
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

''',
    ),
    (
        "_refresh_roll_share_checkbox",
        r'''    def _refresh_roll_share_checkbox(self):
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

''',
    ),
    (
        "_session_roll_sharing_changed",
        r'''    def _session_roll_sharing_changed(self, enabled):
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

''',
    ),
    (
        "_refresh_privacy_controls",
        r'''    def _refresh_privacy_controls(self):
        button = getattr(self, "privacy_btn", None)
        label = getattr(self, "privacy_summary_label", None)
        pane = getattr(self, "privacy_pane", None)
        if button is None or label is None:
            return

        link = self._current_campaign_character_link()
        visible = isinstance(link, dict) and isinstance(self.current_campaign, dict)
        button.setVisible(visible)
        label.setVisible(visible)
        if pane is not None:
            pane.setVisible(visible)
        if not visible:
            label.setText("")
            return

        campaign_id = str(self.current_campaign.get("id") or "").strip()
        character_id = str(getattr(self.window.character, "id", "") or "").strip()
        preferences = self.privacy_store.get(campaign_id, character_id)
        label.setText(sharing_summary(preferences))

''',
    ),
    (
        "open_sharing_privacy",
        r'''    def open_sharing_privacy(self):
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

''',
    ),
    (
        "open_dm_dashboard",
        r'''    def open_dm_dashboard(self):
        if (
            not self.current_campaign
            or self.current_campaign.get("role") != "dm"
            or self.client is None
        ):
            return

        try:
            result = launch_dm_dashboard(
                self.client,
                self.current_campaign["id"],
                app_dir=Path(__file__).resolve().parent,
            )
        except Exception as error:
            self._show_error("Open DM Dashboard Failed", error)
            return

        QMessageBox.information(
            self,
            "DM Dashboard",
            "The live DM dashboard has been opened in your browser.\n\n"
            "If the browser does not connect automatically, enter this one-time "
            f"code within 10 minutes:\n\n{result.get('code', '')}",
        )

''',
    ),
]


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
            and (root / "campaign_privacy.py").is_file()
            and (root / "campaign_session.py").is_file()
        ):
            return root

    raise FileNotFoundError(
        "Could not find the Phase 6 DID project. Put this script in the phase6 "
        "folder inside your current code folder and run it from there."
    )


def main():
    root = find_project_root()
    path = root / "campaign_ui.py"
    original = path.read_text(encoding="utf-8")
    text = original

    # The DM dashboard action needs this import. It existed before v15, but
    # restore it too if an older/repaired copy lost it.
    if "launch_dm_dashboard" not in text:
        needle = "from campaign_cloud import CampaignCloudError\n"
        if needle not in text:
            raise RuntimeError("Could not find campaign_cloud import in campaign_ui.py.")
        text = text.replace(
            needle,
            needle + "from campaign_dashboard_bridge import open_dm_dashboard as launch_dm_dashboard\n",
            1,
        )

    class_marker = "class CampaignManagerDialog(QDialog):\n"
    class_pos = text.find(class_marker)
    if class_pos < 0:
        raise RuntimeError("CampaignManagerDialog was not found.")

    anchor = "    def _choose_rules_for_new_campaign(self, campaign_name):\n"
    anchor_pos = text.find(anchor, class_pos)
    if anchor_pos < 0:
        raise RuntimeError("Could not find the campaign creation method anchor.")

    missing_blocks = []
    restored = []
    for name, body in HELPER_METHODS:
        if f"    def {name}" not in text[class_pos:]:
            missing_blocks.append(body)
            restored.append(name)

    if missing_blocks:
        text = text[:anchor_pos] + "".join(missing_blocks) + text[anchor_pos:]

    required = (
        "    def _current_campaign_character_link",
        "    def _refresh_roll_share_checkbox",
        "    def _session_roll_sharing_changed",
        "    def _refresh_privacy_controls",
        "    def open_sharing_privacy",
        "    def open_dm_dashboard",
        "launch_dm_dashboard",
    )
    missing = [item for item in required if item not in text]
    if missing:
        raise RuntimeError("Repair verification failed. Missing: " + ", ".join(missing))

    if text != original:
        backup = path.with_name(path.name + ".before_campaign_v16_helper_repair")
        if not backup.exists():
            shutil.copy2(path, backup)
            print(f"Backup: {backup.name}")
        path.write_text(text, encoding="utf-8")

    py_compile.compile(str(path), doraise=True)

    if restored:
        print("Restored Campaign helper methods:")
        for name in restored:
            print(f"  {name}: PASS")
    else:
        print("Campaign helper methods: already present")
    print("DM Dashboard action: PASS")
    print("Session roll-sharing helpers: PASS")
    print("Sharing & Privacy helpers: PASS")
    print("Compile: PASS")
    print("Restart frontend_2_8.py and reopen Campaign.")


if __name__ == "__main__":
    main()
